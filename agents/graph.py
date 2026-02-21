"""LangGraph: master agent coordinates scraper and analytics workers."""
from __future__ import annotations

from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama
from langgraph.graph import StateGraph

import config
from agents.state import AgentState, NextWorker
from agents.workers.scraper_agent import create_scraper_agent
from agents.workers.analytics_agent import create_analytics_agent

SUPERVISOR_SYSTEM = """You are the coordinator for the BRVM market (Bourse Régionale des Valeurs Mobilières). All data is in F CFA (Franc CFA). You have two workers:

- scraper: fetches raw data for BRVM (Sika Finance palmarès, Rich Bourse variation, Rich Bourse time series CSV, BRVM official site).
- analytics: answers questions using already-fetched or cached BRVM data (current/historical price in F CFA, volume, growth, loss, time series, compare two stocks, average/median/min/max over a period).

Given the user message and any conversation so far, reply with exactly one word:
- SCRAPER when the user wants to fetch or refresh BRVM data from websites.
- ANALYTICS when the user wants BRVM metrics, comparison, stats, price, time series, or to compare stocks (no new scrape).
- FINISH when the question is fully answered or no tool is needed.

Reply only: SCRAPER or ANALYTICS or FINISH."""


def _parse_next(response: str) -> NextWorker:
    text = (response or "").strip().upper()
    if "SCRAPER" in text:
        return "scraper"
    if "ANALYTICS" in text:
        return "analytics"
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


def _build_worker_node(agent_builder, model: str):
    agent = agent_builder(model=model)

    def node(state: AgentState) -> dict:
        messages = state.get("messages") or []
        result = agent.invoke({"messages": messages})
        out_messages = result.get("messages", messages)
        return {"messages": out_messages, "next": "FINISH"}

    return node


def route_after_supervisor(state: AgentState) -> Literal["scraper", "analytics", "__end__"]:
    next_ = state.get("next") or "FINISH"
    if next_ == "scraper":
        return "scraper"
    if next_ == "analytics":
        return "analytics"
    return "__end__"


def create_master_graph(model: str = "gpt-oss") -> "CompiledStateGraph":
    """Build the graph: supervisor -> (scraper | analytics | END); scraper/analytics -> supervisor."""
    builder = StateGraph(AgentState)

    builder.add_node("supervisor", _build_supervisor_node(model))
    builder.add_node("scraper", _build_worker_node(create_scraper_agent, model))
    builder.add_node("analytics", _build_worker_node(create_analytics_agent, model))

    builder.set_entry_point("supervisor")
    builder.add_conditional_edges("supervisor", route_after_supervisor)
    builder.add_edge("scraper", "supervisor")
    builder.add_edge("analytics", "supervisor")

    return builder.compile()


def run_agent(query: str, model: str = "gpt-oss") -> dict:
    """Run the master agent on a user query. Returns final state with messages."""
    graph = create_master_graph(model=model)
    initial: AgentState = {"messages": [HumanMessage(content=query)]}
    return graph.invoke(initial)
