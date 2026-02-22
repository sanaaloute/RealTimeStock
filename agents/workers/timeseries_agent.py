"""Timeseries CSV worker: ensure company CSVs exist and are up to date; run daily updates."""

from __future__ import annotations

from langchain_ollama import ChatOllama
from langgraph.prebuilt import create_react_agent

import config
from ..tools.stock_tools import (
    ensure_all_timeseries_tool,
    ensure_timeseries_tool,
    list_timeseries_status_tool,
)

TIMESERIES_TOOLS = [
    list_timeseries_status_tool,
    ensure_timeseries_tool,
    ensure_all_timeseries_tool,
]


def create_timeseries_agent(model: str = "gpt-oss"):
    """Build ReAct agent for checking/updating company time series CSVs (daily job)."""
    kwargs = {"model": model, "temperature": 0}
    if config.OLLAMA_BASE_URL:
        kwargs["base_url"] = config.OLLAMA_BASE_URL
    llm = ChatOllama(**kwargs)
    return create_react_agent(llm, TIMESERIES_TOOLS)
