"""Analytics worker agent: metrics, time series, comparison, stats."""
from __future__ import annotations

from langchain_ollama import ChatOllama
from langgraph.prebuilt import create_react_agent

import config
from ..tools.stock_tools import (
    compare_stocks_tool,
    compute_metrics_tool,
    get_stock_metrics_tool,
    get_timeseries_tool,
)

ANALYTICS_TOOLS = [
    get_stock_metrics_tool,
    get_timeseries_tool,
    compare_stocks_tool,
    compute_metrics_tool,
]


def create_analytics_agent(model: str = "gpt-oss"):
    """Build ReAct agent with analytics tools. Use for: price/volume/growth, series, compare, average/median."""
    kwargs = {"model": model, "temperature": 0}
    if config.OLLAMA_BASE_URL:
        kwargs["base_url"] = config.OLLAMA_BASE_URL
    llm = ChatOllama(**kwargs)
    return create_react_agent(llm, ANALYTICS_TOOLS)
