"""LangGraph: NLU -> supervisor -> (scraper | analytics | timeseries | charts | portfolio); workers -> supervisor."""
from __future__ import annotations

import inspect
from pathlib import Path
from typing import Any, Callable, Literal

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import StateGraph

from agents.llm import get_llm
from langgraph.checkpoint.memory import MemorySaver

from agents.state import AgentState, NextWorker

# Path for persistent chat memory (user + AI messages across sessions)
CHAT_MEMORY_DB = Path(__file__).resolve().parent.parent / "data" / "chat_memory.db"
from agents.utils import get_time_prefix
from agents.workers.analytics_agent import create_analytics_agent, get_analytics_agent_system
from agents.workers.charts_agent import create_charts_agent, _extract_image_path_from_messages, get_charts_agent_system
from agents.workers.news_agent import create_news_agent, get_news_agent_system
from agents.workers.nlu_agent import create_nlu_node
from agents.workers.scraper_agent import create_scraper_agent, get_scraper_agent_system
from agents.workers.timeseries_agent import create_timeseries_agent, get_timeseries_agent_system
from agents.workers.portfolio_agent import create_portfolio_agent, get_portfolio_agent_system

# When message count exceeds this, we summarize older messages and keep recent ones
MEMORY_SUMMARY_THRESHOLD = 26
MEMORY_KEEP_RECENT = 12

SUPERVISOR_SYSTEM_TEMPLATE = """You are the routing coordinator for the BRVM (Bourse Régionale des Valeurs Mobilières) assistant. This assistant covers only BRVM—do not refer to or route questions about other stock exchanges. All monetary values are in F CFA. Your only task is to output exactly one label from the list below—no explanation, no other text.

**{time_line}**

**Input:** The last assistant message may contain "[NLU] intent=..., entities=..., suggested_worker=...". Use it and the conversation to choose the next step.

**Workers (choose exactly one):**

- **SCRAPER** — User explicitly asks to fetch, refresh, or pull raw data from BRVM sources: Sika Finance palmarès, Rich Bourse variation, Rich Bourse time series CSV, or BRVM official site. Use only when the request is about obtaining/refreshing source data, not when asking for a computed metric or chart.
- **ANALYTICS** — User asks for: market overview (most traded stock, top by volume, top gainers/losers); current or historical price, volume, variation; comparison of two or more stocks; statistics (average, median, min, max) over a period; time series numbers without a chart; or what is BRVM / how to invest on BRVM. Use when the answer is numeric, tabular, or FAQ about BRVM—not a plot.
- **TIMESERIES** — User asks to check, update, or refresh company CSV files; list which CSVs exist; or run the "daily update" for time series data. Use only for CSV lifecycle operations, not for answering a price or comparison question.
- **CHARTS** — User asks for a chart, graph, or plot of a stock's price over a period (line or area). Use when a visual (image) is requested; the worker returns an image you must pass to the user with a short explanation.
- **NEWS** — User asks for news, actualités, announcements, or latest information about a BRVM company or the BRVM market. Use for any news-like request; the worker fetches from Rich Bourse, Sika Finance, and BRVM official announcements.
- **PORTFOLIO** — User asks about or wants to change their portfolio (show portfolio, add/remove position, portfolio growth/loss), their tracking list (add/remove symbol), or price alerts (set target, list/remove alerts). Use for "my portfolio", "add NTLC to portfolio", "track SLBC", "notify me when NTLC hits 55000", "remove NTLC from portfolio".
- **FINISH** — The user's question has been fully answered by a previous worker reply, or the message is a greeting/thanks/off-topic and no tool is needed.

**Output rule:** Reply with exactly one word: SCRAPER | ANALYTICS | TIMESERIES | CHARTS | NEWS | PORTFOLIO | FINISH."""


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
    """Condense a list of messages into a short summary for memory."""
    if not messages:
        return ""
    from langchain_core.messages import messages_to_str
    llm = get_llm(model=model, temperature=0)
    text = messages_to_str(messages)[:8000]
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
        # Summarize memory: if too many messages, condense older part and keep recent
        if len(messages) > MEMORY_SUMMARY_THRESHOLD:
            to_summarize = messages[:-MEMORY_KEEP_RECENT]
            new_summary = _summarize_messages(to_summarize, model)
            summary = f"{summary}\n{new_summary}".strip() if summary else new_summary
            messages = list(messages[-MEMORY_KEEP_RECENT:])
        if not messages:
            return {"messages": messages, "next": "FINISH", "conversation_summary": summary}
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
            messages = [SystemMessage(content=system_content)] + list(messages)
        else:
            # Workers without their own system prompt still get current time (and optional summary)
            prefix = time_line
            if summary:
                prefix = f"Conversation summary:\n{summary}\n\n{prefix}"
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
    """If NLU asked for clarification, end; else go to supervisor."""
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


def create_master_graph(
    model: str = "qwen3:8b",
    checkpointer: Any | None = None,
) -> "CompiledStateGraph":
    """Build the graph: NLU (entry) -> supervisor -> (scraper | analytics | timeseries | charts | END); workers -> supervisor.
    If checkpointer is provided (e.g. SqliteSaver), chat memory persists across restarts."""
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
    model: str = "qwen3:8b",
    thread_id: str | None = None,
    telegram_user_id: int | None = None,
    checkpointer: Any | None = None,
) -> dict:
    """Run the master agent on a user query. Returns final state with messages.
    If thread_id is set, conversation is persisted (summarize memory) across calls.
    If checkpointer is provided (e.g. SqliteSaver), user+AI chat history persists across restarts.
    telegram_user_id is passed to portfolio/tracking/target tools when the user manages portfolio or alerts."""
    graph = create_master_graph(model=model, checkpointer=checkpointer)
    run_config = {"configurable": {"thread_id": thread_id or "default"}}
    # Append new message to existing conversation when using memory
    current = graph.get_state(run_config)
    existing = (current.values or {}).get("messages") or []
    messages = list(existing) + [HumanMessage(content=query)]
    initial: AgentState = {"messages": messages}
    if telegram_user_id is not None:
        initial["telegram_user_id"] = telegram_user_id
    return graph.invoke(initial, config=run_config)
