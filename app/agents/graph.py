"""LangGraph: NLU -> supervisor -> workers (scraper|analytics|timeseries|charts|news|portfolio)."""
from __future__ import annotations

import inspect
import time
from pathlib import Path
from typing import Any, Callable, Literal

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import StateGraph

import config
from app.agents.llm import get_llm
from langgraph.checkpoint.memory import MemorySaver

from app.agents.state import AgentState, NextWorker

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

SUPERVISOR_SYSTEM_TEMPLATE = """BRVM routing coordinator. Output exactly one label—no explanation. All amounts in F CFA.

**{time_line}**

**Input:** Last message may contain "[NLU] intent=..., suggested_worker=...". Use it to choose next step.

**Workers (one):**
- **SCRAPER** — Fetch/refresh raw data (palmarès, variation, CSV, BRVM site). Not for computed metrics or charts.
- **ANALYTICS** — Market overview, price/volume, compare stocks, stats (avg/median/min/max), BRVM FAQ. Numeric/tabular—not plots.
- **TIMESERIES** — Check/update CSV files, list CSVs, daily update. CSV ops only—not price questions.
- **CHARTS** — Chart/graph/plot of stock price. Visual requested.
- **NEWS** — News, actualités, announcements about BRVM.
- **PORTFOLIO** — Portfolio, tracking list, price alerts (my portfolio, add NTLC, track SLBC, notify when NTLC hits 55000).
- **FINISH** — Question answered, or greeting/thanks/off-topic.

**Output:** SCRAPER | ANALYTICS | TIMESERIES | CHARTS | NEWS | PORTFOLIO | FINISH"""


def _get_supervisor_system() -> str:
    return SUPERVISOR_SYSTEM_TEMPLATE.format(time_line=get_time_prefix())


def _parse_next(response: str) -> NextWorker:
    text = (response or "").strip().upper()
    if "SCRAPER" in text:
        return "scraper"
    if "ANALYTICS" in text:
        return "analytics"
    if "TIMESERIES" in text:
        return "timeseries"
    if "CHARTS" in text:
        return "charts"
    if "NEWS" in text:
        return "news"
    if "PORTFOLIO" in text:
        return "portfolio"
    return "FINISH"


def _summarize_messages(messages: list, model: str) -> str:
    if not messages:
        return ""
    from langchain_core.messages.utils import get_buffer_string
    llm = get_llm(model=model, temperature=0)
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
    llm = get_llm(model=model, temperature=0)

    def supervisor(state: AgentState) -> dict:
        messages = state.get("messages") or []
        summary = state.get("conversation_summary") or ""
        structured_data = state.get("structured_data")

        if len(messages) > MEMORY_SUMMARY_THRESHOLD:
            to_summarize = messages[:-MEMORY_KEEP_RECENT]
            new_summary = _summarize_messages(to_summarize, model)
            summary = f"{summary}\n{new_summary}".strip() if summary else new_summary
            messages = list(messages[-MEMORY_KEEP_RECENT:])
        if not messages:
            return {"messages": messages, "next": "FINISH", "conversation_summary": summary}

        last_content = (messages[-1].content if hasattr(messages[-1], "content") else "") or ""
        if structured_data and "[NLU]" in str(last_content):
            suggested = (structured_data.get("suggested_worker") or "").strip().lower()
            if suggested in ("scraper", "analytics", "timeseries", "charts", "news", "portfolio"):
                out: dict = {"messages": messages, "next": suggested}
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
        next_worker = _parse_next(content)
        out: dict = {"messages": messages, "next": next_worker}
        if summary:
            out["conversation_summary"] = summary
        return out

    return supervisor


def _entities_hint(structured_data: dict | None) -> str:
    if not structured_data or not isinstance(structured_data.get("entities"), dict):
        return ""
    ent = structured_data["entities"]
    if not ent:
        return ""
    parts = [f"{k}={v}" for k, v in ent.items() if v]
    if not parts:
        return ""
    return f"\n**NLU entities (use these in tool calls):** {', '.join(parts)}"


def _build_worker_node(
    agent_builder,
    model: str,
    extract_image_path: bool = False,
    prepend_system: str | None | Callable[[], str] = None,
):
    agent = agent_builder(model=model)

    def node(state: AgentState) -> dict:
        messages = state.get("messages") or []
        summary = state.get("conversation_summary") or ""
        structured_data = state.get("structured_data")
        time_line = get_time_prefix()
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
) -> Literal["scraper", "analytics", "timeseries", "charts", "news", "portfolio", "__end__"]:
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


def create_master_graph(model: str | None = None, checkpointer: Any | None = None) -> "CompiledStateGraph":
    model = model or config.OLLAMA_MODEL
    builder = StateGraph(AgentState)

    builder.add_node("nlu", create_nlu_node(model))
    builder.add_node("supervisor", _build_supervisor_node(model))
    builder.add_node("scraper", _build_worker_node(create_scraper_agent, model, prepend_system=get_scraper_agent_system))
    builder.add_node("analytics", _build_worker_node(create_analytics_agent, model, prepend_system=get_analytics_agent_system))
    builder.add_node("timeseries", _build_worker_node(create_timeseries_agent, model, prepend_system=get_timeseries_agent_system))
    builder.add_node("charts", _build_worker_node(create_charts_agent, model, extract_image_path=True, prepend_system=get_charts_agent_system))
    builder.add_node("news", _build_worker_node(create_news_agent, model, prepend_system=get_news_agent_system))

    def _portfolio_system(state: AgentState) -> str:
        return get_portfolio_agent_system(state.get("telegram_user_id") or 0)
    builder.add_node("portfolio", _build_worker_node(create_portfolio_agent, model, prepend_system=_portfolio_system))

    builder.set_entry_point("nlu")
    builder.add_conditional_edges("nlu", route_after_nlu)
    builder.add_conditional_edges("supervisor", route_after_supervisor)
    builder.add_edge("scraper", "supervisor")
    builder.add_edge("analytics", "supervisor")
    builder.add_edge("timeseries", "supervisor")
    builder.add_edge("charts", "supervisor")
    builder.add_edge("news", "supervisor")
    builder.add_edge("portfolio", "supervisor")

    cp = checkpointer if checkpointer is not None else MemorySaver()
    return builder.compile(checkpointer=cp)


def run_agent(
    query: str,
    model: str | None = None,
    thread_id: str | None = None,
    telegram_user_id: int | None = None,
    checkpointer: Any | None = None,
) -> dict:
    model = model or config.OLLAMA_MODEL
    graph = create_master_graph(model=model, checkpointer=checkpointer)
    run_config = {"configurable": {"thread_id": thread_id or "default"}}
    current = graph.get_state(run_config)
    existing = (current.values or {}).get("messages") or []
    messages = list(existing) + [HumanMessage(content=query)]
    initial: AgentState = {"messages": messages}
    if telegram_user_id is not None:
        initial["telegram_user_id"] = telegram_user_id

    last_error: BaseException | None = None
    for attempt in range(3):
        try:
            return graph.invoke(initial, config=run_config)
        except Exception as e:
            last_error = e
            err_str = str(e).lower()
            is_retryable = (
                "ssl" in err_str
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
