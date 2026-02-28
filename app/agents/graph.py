"""LangGraph: NLU -> supervisor -> workers (scraper|analytics|timeseries|charts|news|portfolio)."""
from __future__ import annotations

import inspect
import logging
import time
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Callable, Literal

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

logger = logging.getLogger(__name__)
from langgraph.graph import StateGraph

import config
from app.models.llm import get_default_model, get_llm
from langgraph.checkpoint.memory import MemorySaver

from app.agents.state import AgentState, NextWorker, WorkerName

CHAT_MEMORY_DB = Path(__file__).resolve().parent.parent / "data" / "chat_memory.db"
from app.agents.utils import get_time_prefix
from app.agents.analytics_agent import create_analytics_agent, get_analytics_agent_system
from app.agents.charts_agent import create_charts_agent, _extract_image_path_from_messages, get_charts_agent_system
from app.agents.news_agent import create_news_agent, get_news_agent_system
from app.agents.nlu_agent import create_nlu_node
from app.agents.scraper_agent import create_scraper_agent, get_scraper_agent_system
from app.agents.timeseries_agent import create_timeseries_agent, get_timeseries_agent_system
from app.agents.portfolio_agent import create_portfolio_agent, get_portfolio_agent_system

MEMORY_SUMMARY_THRESHOLD = 26
MEMORY_KEEP_RECENT = 12

# region agent log
DEBUG_LOG_PATH = Path("debug-ce8ad8.log").resolve()


def _agent_debug_log(
    hypothesis_id: str,
    location: str,
    message: str,
    data: dict | None = None,
    run_id: str = "pre-fix",
) -> None:
    """Append a single NDJSON debug log line for this debug session."""
    try:
        payload = {
            "sessionId": "ce8ad8",
            "id": f"log_{int(time.time() * 1000)}_{hypothesis_id}",
            "timestamp": int(time.time() * 1000),
            "location": location,
            "message": message,
            "data": data or {},
            "runId": run_id,
            "hypothesisId": hypothesis_id,
        }
        with DEBUG_LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception:
        # Debug logging must never break the agent
        pass


# endregion

SUPERVISOR_SYSTEM_TEMPLATE = """BRVM router. Output one label only. {time_line}

**Rule:** Last message is worker response (data/chart/news) → output FINISH. Do not chain workers.

**Workers:**
- SCRAPER — Fetch raw data (palmarès, variation, CSV)
- ANALYTICS — Prices, compare, stats, market overview (numbers, no plots)
- TIMESERIES — CSV maintenance only: list/update CSVs. Use ONLY when the user explicitly asks to update timeseries files or check their status. Never route normal price/metrics/compare/chart/news questions here.
- CHARTS — Plot/graph of stock price
- NEWS — Actualités, communiqués, dividends, predictions
- PORTFOLIO — My portfolio, tracking list, price alerts
- FINISH — Done, greeting, or off-topic

**Output:** SCRAPER | ANALYTICS | TIMESERIES | CHARTS | NEWS | PORTFOLIO | FINISH
(For multi: ANALYTICS,NEWS or SCRAPER|CHARTS — do NOT include TIMESERIES in multi.)"""


def _get_supervisor_system() -> str:
    return SUPERVISOR_SYSTEM_TEMPLATE.format(time_line=get_time_prefix())


def _parse_next(response: str) -> tuple[NextWorker, list[WorkerName], bool]:
    """
    Parse supervisor output. Returns (next, multi_workers, multi_parallel).
    - If multi_workers non-empty: use those; multi_parallel=True for comma, False for pipe.
    - Else: next is the single worker or FINISH.
    """
    text = (response or "").strip().upper()
    # Sequential: WORKER1|WORKER2
    if "|" in text:
        parts = [p.strip() for p in text.split("|") if p.strip()]
        workers: list[WorkerName] = []
        for p in parts:
            w = _label_to_worker(p)
            # TIMESERIES should not be auto-chained with other workers; it is for explicit CSV maintenance only.
            if w and w != "FINISH" and w != "timeseries":
                workers.append(w)
        if workers:
            return "FINISH", workers, False  # sequential
    # Parallel: WORKER1,WORKER2
    if "," in text:
        parts = [p.strip() for p in text.split(",") if p.strip()]
        workers = []
        for p in parts:
            w = _label_to_worker(p)
            # TIMESERIES should not be auto-chained with other workers; it is for explicit CSV maintenance only.
            if w and w != "FINISH" and w != "timeseries":
                workers.append(w)
        if workers:
            return "FINISH", workers, True  # parallel
    # Single
    w = _label_to_worker(text)
    return (w or "FINISH"), [], False


def _label_to_worker(label: str) -> WorkerName | Literal["FINISH"] | None:
    label = (label or "").strip().upper()
    if "SCRAPER" in label:
        return "scraper"
    if "ANALYTICS" in label:
        return "analytics"
    if "TIMESERIES" in label:
        return "timeseries"
    if "CHARTS" in label:
        return "charts"
    if "NEWS" in label:
        return "news"
    if "PORTFOLIO" in label:
        return "portfolio"
    if "FINISH" in label or not label:
        return "FINISH"
    return None


def _summarize_messages(messages: list, model: str) -> str:
    if not messages:
        return ""
    from langchain_core.messages.utils import get_buffer_string
    llm = get_llm(model=model)
    text = get_buffer_string(messages)[:8000]
    prompt = f"""Summarize this BRVM stock market conversation in 2–4 short sentences. Include: stock symbols mentioned (e.g. NTLC, SLBC), what the user asked for, and key facts (prices, dates, comparisons). Omit tool names, file paths, and internal implementation details.

Conversation:
{text}

Summary:"""
    try:
        out = llm.invoke([HumanMessage(content=prompt)])
        return (getattr(out, "content", None) or str(out)).strip() or "Previous conversation."
    except Exception:
        return "Previous conversation."


def _build_supervisor_node(model: str):
    llm = get_llm(model=model)

    def supervisor(state: AgentState) -> dict:
        logger.info("[GRAPH] node=supervisor start")
        messages = state.get("messages") or []
        summary = state.get("conversation_summary") or ""
        structured_data = state.get("structured_data")

        if len(messages) > MEMORY_SUMMARY_THRESHOLD:
            to_summarize = messages[:-MEMORY_KEEP_RECENT]
            new_summary = _summarize_messages(to_summarize, model)
            summary = f"{summary}\n{new_summary}".strip() if summary else new_summary
            messages = list(messages[-MEMORY_KEEP_RECENT:])
        if not messages:
            return {
                "messages": messages,
                "next": "FINISH",
                "conversation_summary": summary,
                "multi_workers": [],
                "multi_parallel": False,
            }

        last_msg = messages[-1]
        last_content = (last_msg.content if hasattr(last_msg, "content") else "") or ""
        # If last message is worker response (not NLU), finish—avoid endless loops
        if isinstance(last_msg, AIMessage) and "[NLU]" not in str(last_content) and len(str(last_content).strip()) > 20:
            out_finish: dict = {
                "messages": messages,
                "next": "FINISH",
                "multi_workers": [],
                "multi_parallel": False,
            }
            if summary:
                out_finish["conversation_summary"] = summary
            return out_finish
        if structured_data and "[NLU]" in str(last_content):
            suggested = (structured_data.get("suggested_worker") or "").strip().lower()
            if suggested in ("scraper", "analytics", "timeseries", "charts", "news", "portfolio"):
                out: dict = {
                    "messages": messages,
                    "next": suggested,
                    "multi_workers": [],
                    "multi_parallel": False,
                }
                if summary:
                    out["conversation_summary"] = summary
                return out

        time_system = _get_supervisor_system()
        system_content = time_system
        if summary:
            system_content = f"{time_system}\n\nConversation summary (context):\n{summary}"
        to_send = [SystemMessage(content=system_content)] + list(messages)
        reply = llm.invoke(to_send)
        content = reply.content if hasattr(reply, "content") else str(reply)
        next_worker, multi_workers, multi_parallel = _parse_next(content)
        logger.info("[GRAPH] supervisor -> next=%s multi=%s", next_worker, multi_workers or None)
        # region agent log
        _agent_debug_log(
            "H2",
            "graph.supervisor",
            "Supervisor routing decision",
            {
                "next": next_worker,
                "multi_workers": multi_workers,
                "multi_parallel": multi_parallel,
                "has_structured_data": bool(structured_data),
            },
        )
        # endregion
        out: dict = {
            "messages": messages,
            "next": next_worker,
            "multi_workers": [],
            "multi_parallel": False,
        }
        if multi_workers:
            out["multi_workers"] = multi_workers
            out["multi_parallel"] = multi_parallel
        if summary:
            out["conversation_summary"] = summary
        return out

    return supervisor


def _log_tools_from_messages(messages: list, agent_name: str) -> None:
    """Log tool calls found in messages for debugging."""
    for m in messages:
        if isinstance(m, ToolMessage) and getattr(m, "name", None):
            logger.info("[GRAPH] agent=%s tool=%s", agent_name, m.name)
        if isinstance(m, AIMessage) and getattr(m, "tool_calls", None):
            for tc in m.tool_calls:
                name = tc.get("name", "?") if isinstance(tc, dict) else getattr(tc, "name", "?")
                logger.info("[GRAPH] agent=%s tool_call=%s", agent_name, name)


def _entities_hint(structured_data: dict | None) -> str:
    if not structured_data or not isinstance(structured_data.get("entities"), dict):
        return ""
    ent = structured_data["entities"]
    if not ent:
        return ""
    parts = [f"{k}={v}" for k, v in ent.items() if v]
    if not parts:
        return ""
    return f"\n**CRITICAL - Use these for the CURRENT question (do NOT use symbols from previous messages):** {', '.join(parts)}"


def _build_worker_node(
    agent_builder,
    model: str,
    *,
    worker_name: str = "worker",
    extract_image_path: bool = False,
    prepend_system: str | None | Callable[[], str] = None,
):
    agent = agent_builder(model=model)

    def node(state: AgentState) -> dict:
        logger.info("[GRAPH] node=%s start", worker_name)
        messages = state.get("messages") or []
        summary = state.get("conversation_summary") or ""
        structured_data = state.get("structured_data")
        time_line = get_time_prefix()
        # region agent log
        _agent_debug_log(
            "H3",
            f"graph.worker.{worker_name}",
            "Worker node start",
            {
                "worker": worker_name,
                "message_count": len(messages),
            },
        )
        # endregion
        if prepend_system:
            if callable(prepend_system):
                try:
                    sig = inspect.signature(prepend_system)
                    if len(sig.parameters) >= 1:
                        system_content = prepend_system(state)
                    else:
                        system_content = prepend_system()
                except Exception:
                    system_content = prepend_system()
            else:
                system_content = prepend_system
            if summary:
                system_content = f"Conversation summary (context):\n{summary}\n\n{system_content}"
            entities_hint = _entities_hint(structured_data)
            if entities_hint:
                system_content = system_content.rstrip() + entities_hint
            messages = [SystemMessage(content=system_content)] + list(messages)
        else:
            prefix = time_line
            if summary:
                prefix = f"Conversation summary:\n{summary}\n\n{prefix}"
            entities_hint = _entities_hint(structured_data)
            if entities_hint:
                prefix = prefix.rstrip() + entities_hint
            messages = [SystemMessage(content=prefix)] + list(messages)
        result = agent.invoke({"messages": messages})
        out_messages = result.get("messages", messages)
        _log_tools_from_messages(out_messages, worker_name)
        out: dict = {"messages": out_messages, "next": "FINISH"}
        if extract_image_path:
            path = _extract_image_path_from_messages(out_messages)
            if path:
                out["image_path"] = path
        return out

    return node


def route_after_nlu(state: AgentState) -> Literal["supervisor", "__end__"]:
    if state.get("clarification"):
        return "__end__"
    return "supervisor"


def route_after_supervisor(
    state: AgentState,
) -> Literal["scraper", "analytics", "timeseries", "charts", "news", "portfolio", "multi_worker", "__end__"]:
    multi = state.get("multi_workers") or []
    if multi:
        return "multi_worker"
    next_ = state.get("next") or "FINISH"
    if next_ == "scraper":
        return "scraper"
    if next_ == "analytics":
        return "analytics"
    if next_ == "timeseries":
        return "timeseries"
    if next_ == "charts":
        return "charts"
    if next_ == "news":
        return "news"
    if next_ == "portfolio":
        return "portfolio"
    return "__end__"


def _build_multi_worker_node(
    worker_nodes: dict[WorkerName, Callable[[AgentState], dict]],
    model: str,
) -> Callable[[AgentState], dict]:
    """Run multiple workers in parallel or sequential, merge results."""

    def multi_worker(state: AgentState) -> dict:
        workers = state.get("multi_workers") or []
        logger.info("[GRAPH] node=multi_worker workers=%s parallel=%s", workers, state.get("multi_parallel", False))
        parallel = state.get("multi_parallel", False)
        if not workers:
            return {
                "messages": state.get("messages", []),
                "next": "FINISH",
                "multi_workers": [],
                "multi_parallel": False,
            }

        messages = list(state.get("messages") or [])
        image_path = state.get("image_path")
        valid = {"scraper", "analytics", "timeseries", "charts", "news", "portfolio"}
        workers = [w for w in workers if w in valid and w in worker_nodes]

        # region agent log
        _agent_debug_log(
            "H4",
            "graph.multi_worker",
            "Multi worker dispatch",
            {
                "workers": workers,
                "parallel": parallel,
            },
        )
        # endregion

        if parallel:
            # Run all workers with same input state, merge new AIMessages (preserve worker order)
            base_len = len(messages)
            worker_results: dict[WorkerName, dict] = {}
            with ThreadPoolExecutor(max_workers=len(workers)) as ex:
                futures = {ex.submit(worker_nodes[w], state): w for w in workers}
                for fut in as_completed(futures):
                    try:
                        res = fut.result()
                        wn = futures[fut]
                        worker_results[wn] = res
                    except Exception:
                        pass
            all_new: list = []
            for wn in workers:
                res = worker_results.get(wn)
                if not res:
                    continue
                msgs = res.get("messages") or []
                for m in msgs[base_len:]:
                    if isinstance(m, AIMessage):
                        all_new.append(m)
                if res.get("image_path") and not image_path:
                    image_path = res.get("image_path")
            out_messages = messages + all_new
        else:
            # Sequential: run each worker, pass accumulated state to next
            current: AgentState = dict(state)
            for wn in workers:
                result = worker_nodes[wn](current)
                current = dict(result)
                if "messages" in result:
                    current["messages"] = result["messages"]
                if result.get("image_path"):
                    current["image_path"] = result["image_path"]
            out_messages = current.get("messages") or messages

        out: dict = {
            "messages": out_messages,
            "next": "FINISH",
            "multi_workers": [],
            "multi_parallel": False,
        }
        if image_path:
            out["image_path"] = image_path
        return out

    return multi_worker


def create_master_graph(model: str | None = None, checkpointer: Any | None = None) -> Any:
    model = model or get_default_model()
    builder = StateGraph(AgentState)

    builder.add_node("nlu", create_nlu_node(model))
    builder.add_node("supervisor", _build_supervisor_node(model))

    worker_nodes_map: dict[WorkerName, Callable[[AgentState], dict]] = {}
    scraper_n = _build_worker_node(create_scraper_agent, model, worker_name="scraper", prepend_system=get_scraper_agent_system)
    analytics_n = _build_worker_node(create_analytics_agent, model, worker_name="analytics", prepend_system=get_analytics_agent_system)
    timeseries_n = _build_worker_node(create_timeseries_agent, model, worker_name="timeseries", prepend_system=get_timeseries_agent_system)
    charts_n = _build_worker_node(create_charts_agent, model, worker_name="charts", extract_image_path=True, prepend_system=get_charts_agent_system)
    news_n = _build_worker_node(create_news_agent, model, worker_name="news", prepend_system=get_news_agent_system)

    def _portfolio_system(state: AgentState) -> str:
        return get_portfolio_agent_system(state.get("telegram_user_id") or 0)
    portfolio_n = _build_worker_node(create_portfolio_agent, model, worker_name="portfolio", prepend_system=_portfolio_system)

    builder.add_node("scraper", scraper_n)
    builder.add_node("analytics", analytics_n)
    builder.add_node("timeseries", timeseries_n)
    builder.add_node("charts", charts_n)
    builder.add_node("news", news_n)
    builder.add_node("portfolio", portfolio_n)

    worker_nodes_map["scraper"] = scraper_n
    worker_nodes_map["analytics"] = analytics_n
    worker_nodes_map["timeseries"] = timeseries_n
    worker_nodes_map["charts"] = charts_n
    worker_nodes_map["news"] = news_n
    worker_nodes_map["portfolio"] = portfolio_n

    builder.add_node("multi_worker", _build_multi_worker_node(worker_nodes_map, model))

    builder.set_entry_point("nlu")
    builder.add_conditional_edges("nlu", route_after_nlu)
    builder.add_conditional_edges("supervisor", route_after_supervisor)
    builder.add_edge("scraper", "supervisor")
    builder.add_edge("analytics", "supervisor")
    builder.add_edge("timeseries", "supervisor")
    builder.add_edge("charts", "supervisor")
    builder.add_edge("news", "supervisor")
    builder.add_edge("portfolio", "supervisor")
    builder.add_edge("multi_worker", "supervisor")

    cp = checkpointer if checkpointer is not None else MemorySaver()
    return builder.compile(checkpointer=cp)


def run_agent(
    query: str,
    model: str | None = None,
    thread_id: str | None = None,
    telegram_user_id: int | None = None,
    checkpointer: Any | None = None,
) -> dict:
    model = model or get_default_model()
    graph = create_master_graph(model=model, checkpointer=checkpointer)
    run_config = {
        "configurable": {"thread_id": thread_id or "default"},
        "recursion_limit": config.RECURSION_LIMIT,
    }
    current = graph.get_state(run_config)
    existing = (current.values or {}).get("messages") or []
    messages = list(existing) + [HumanMessage(content=query)]
    initial: AgentState = {"messages": messages}
    if telegram_user_id is not None:
        initial["telegram_user_id"] = telegram_user_id

    # region agent log
    _agent_debug_log(
        "H1",
        "graph.run_agent:before_invoke",
        "Starting agent run",
        {
            "query_preview": str(query)[:200],
            "thread_id": thread_id,
            "telegram_user_id": telegram_user_id,
            "model": model,
        },
    )
    # endregion

    last_error: BaseException | None = None
    for attempt in range(3):
        try:
            return graph.invoke(initial, config=run_config)
        except Exception as e:
            if "recursion" in str(e).lower() or "GraphRecursionError" in type(e).__name__:
                logger.warning("Graph hit recursion limit, returning partial result: %s", e)
                try:
                    state = graph.get_state(run_config)
                    vals = state.values or {}
                    if vals and vals.get("messages"):
                        return vals
                except Exception as get_err:
                    logger.warning("Could not get partial state: %s", get_err)
            last_error = e
            err_str = str(e).lower()
            is_retryable = (
                "503" in err_str
                or "ssl" in err_str
                or "eof" in err_str
                or "connection" in err_str
                or "connect" in err_str
                or "timeout" in err_str
            )
            if is_retryable and attempt < 2:
                time.sleep(1.5 * (attempt + 1))
                continue
            raise
    raise last_error or RuntimeError("Agent invocation failed")
