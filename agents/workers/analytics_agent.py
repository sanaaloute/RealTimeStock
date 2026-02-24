"""Analytics worker: metrics, timeseries, comparison, BRVM basics."""
from __future__ import annotations

from langgraph.prebuilt import create_react_agent

from agents.llm import get_llm
from agents.utils import get_time_prefix
from ..tools.stock_tools import (
    compare_stocks_tool,
    compute_metrics_tool,
    get_brvm_basics_tool,
    get_market_overview_tool,
    get_stock_metrics_tool,
    get_timeseries_tool,
)


def get_analytics_agent_system() -> str:
    return f"""You are the BRVM analytics worker. This assistant covers only the BRVM (Bourse Régionale des Valeurs Mobilières). Do not mention or use data from other stock exchanges (e.g. NYSE, NASDAQ, other African bourses). Answer only from tool results; do not invent numbers or symbols.

**{get_time_prefix()}**

**Tools:**
- get_market_overview: Use for "most traded stock", "highest volume", "top performers", "top gainers/losers". Returns BRVM-only rankings.
- get_stock_metrics_tool: price/volume for one BRVM symbol.
- get_timeseries_tool: time series data for a symbol.
- compare_stocks_tool: compare two BRVM symbols.
- compute_metrics_tool: average/median/min/max over a period.
- get_brvm_basics_tool: what is BRVM, how to invest on BRVM (FAQ).

Use only BRVM symbols from tool results. Present numbers clearly. All amounts in F CFA. Do not mention tool names or file paths in the final answer."""


ANALYTICS_TOOLS = [
    get_market_overview_tool,
    get_stock_metrics_tool,
    get_timeseries_tool,
    compare_stocks_tool,
    compute_metrics_tool,
    get_brvm_basics_tool,
]


def create_analytics_agent(model: str = "qwen3:8b"):
    llm = get_llm(model=model, temperature=0)
    return create_react_agent(llm, ANALYTICS_TOOLS)
