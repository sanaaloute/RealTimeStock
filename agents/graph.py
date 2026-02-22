"""LangGraph: NLU -> supervisor -> (scraper | analytics | timeseries | charts); workers -> supervisor."""
from __future__ import annotations

from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama
from langgraph.graph import StateGraph

import config
from agents.state import AgentState, NextWorker
from agents.workers.analytics_agent import create_analytics_agent
from agents.workers.charts_agent import create_charts_agent, _extract_image_path_from_messages
from agents.workers.news_agent import NEWS_AGENT_SYSTEM, create_news_agent
from agents.workers.nlu_agent import create_nlu_node
from agents.workers.scraper_agent import create_scraper_agent
from agents.workers.timeseries_agent import create_timeseries_agent

SUPERVISOR_SYSTEM = """You are the coordinator for the BRVM market (Bourse Régionale des Valeurs Mobilières). All data is in F CFA (Franc CFA).

The user message has been analyzed by NLU. The last message may be "[NLU] intent=..., entities=..., suggested_worker=...". Use that to help route.

You have five workers:

- scraper: fetches raw data (Sika Finance palmarès, Rich Bourse variation, Rich Bourse time series CSV, BRVM official site).
- analytics: BRVM metrics, comparison, stats, price, time series data, compare stocks, average/median/min/max over a period.
- timeseries: check if company CSVs exist and are up to date; update one or all company time series CSVs (daily job).
- charts: plot a company's price over a date range (line or area chart). Returns an image; you must return that image with your explanation.
- news: latest news about a BRVM company or BRVM market (Rich Bourse, Sika Finance, BRVM official announcements). Ground truth only.

Given the user message and any conversation so far, reply with exactly one word:
- SCRAPER when the user wants to fetch or refresh BRVM data from websites.
- ANALYTICS when the user wants metrics, comparison, stats, price, or time series (no chart image).
- TIMESERIES when the user wants to check/update company CSV files or run the daily CSV update.
- CHARTS when the user wants a chart/graph/plot of a company's price over a period (return image + explanation).
- NEWS when the user wants news, actualités, announcements, or latest information about a company or the BRVM market.
- FINISH when the question is fully answered or no tool is needed.

Reply only: SCRAPER or ANALYTICS or TIMESERIES or CHARTS or NEWS or FINISH."""


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
    return "FINISH"


def _build_supervisor_node(model: str):
    kwargs = {"model": model, "temperature": 0}
    if config.OLLAMA_BASE_URL:
        kwargs["base_url"] = config.OLLAMA_BASE_URL
    llm = ChatOllama(**kwargs)

    def supervisor(state: AgentState) -> dict:
        messages = state.get("messages") or []
        if not messages:
            return {"messages": messages, "next": "FINISH"}
        prompt = (
            SystemMessage(content=SUPERVISOR_SYSTEM)
            if not any(isinstance(m, SystemMessage) for m in messages)
            else None
        )
        to_send = ([prompt] if prompt else []) + list(messages)
        reply = llm.invoke(to_send)
        content = reply.content if hasattr(reply, "content") else str(reply)
        next_worker = _parse_next(content)
        return {"messages": messages, "next": next_worker}

    return supervisor


def _build_worker_node(agent_builder, model: str, extract_image_path: bool = False, prepend_system: str | None = None):
    agent = agent_builder(model=model)

    def node(state: AgentState) -> dict:
        messages = state.get("messages") or []
        if prepend_system:
            messages = [SystemMessage(content=prepend_system)] + list(messages)
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
) -> Literal["scraper", "analytics", "timeseries", "charts", "news", "__end__"]:
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
    return "__end__"


def create_master_graph(model: str = "gpt-oss") -> "CompiledStateGraph":
    """Build the graph: NLU (entry) -> supervisor -> (scraper | analytics | timeseries | charts | END); workers -> supervisor."""
    builder = StateGraph(AgentState)

    builder.add_node("nlu", create_nlu_node(model))
    builder.add_node("supervisor", _build_supervisor_node(model))
    builder.add_node("scraper", _build_worker_node(create_scraper_agent, model))
    builder.add_node("analytics", _build_worker_node(create_analytics_agent, model))
    builder.add_node("timeseries", _build_worker_node(create_timeseries_agent, model))
    builder.add_node("charts", _build_worker_node(create_charts_agent, model, extract_image_path=True))
    builder.add_node("news", _build_worker_node(create_news_agent, model, prepend_system=NEWS_AGENT_SYSTEM))

    builder.set_entry_point("nlu")
    builder.add_conditional_edges("nlu", route_after_nlu)
    builder.add_conditional_edges("supervisor", route_after_supervisor)
    builder.add_edge("scraper", "supervisor")
    builder.add_edge("analytics", "supervisor")
    builder.add_edge("timeseries", "supervisor")
    builder.add_edge("charts", "supervisor")
    builder.add_edge("news", "supervisor")

    return builder.compile()


def run_agent(query: str, model: str = "gpt-oss") -> dict:
    """Run the master agent on a user query. Returns final state with messages."""
    graph = create_master_graph(model=model)
    initial: AgentState = {"messages": [HumanMessage(content=query)]}
    return graph.invoke(initial)
