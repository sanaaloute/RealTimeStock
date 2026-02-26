"""Timeseries CSV worker: ensure CSVs exist, daily updates."""

from __future__ import annotations

from langgraph.prebuilt import create_react_agent

from agents.llm import get_llm
from agents.utils import get_time_prefix
from ..tools.stock_tools import (
    ensure_all_timeseries_tool,
    ensure_timeseries_tool,
    list_timeseries_status_tool,
)


def get_timeseries_agent_system() -> str:
    """System prompt for the timeseries CSV worker."""
    return f"""You are the BRVM time series CSV worker. You check and update company CSV files used for charts and analytics. Do not answer price or comparison questions—only report CSV status and update results.

**{get_time_prefix()}**

**Tools:** list_timeseries_status_tool (list or check CSVs for symbols), ensure_timeseries_tool (ensure/update CSV for one symbol), ensure_all_timeseries_tool (update all configured symbols). Call the appropriate tool and report outcome (e.g. created/updated, already up to date, or error). Do not mention file paths in the final answer."""


TIMESERIES_TOOLS = [
    list_timeseries_status_tool,
    ensure_timeseries_tool,
    ensure_all_timeseries_tool,
]


def create_timeseries_agent(model: str = "glm-5:cloud"):
    llm = get_llm(model=model, temperature=0)
    return create_react_agent(llm, TIMESERIES_TOOLS)
