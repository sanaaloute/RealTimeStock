"""Analytics worker: metrics, timeseries, comparison, BRVM basics."""
from __future__ import annotations

from langgraph.prebuilt import create_react_agent

from app.models.llm import get_llm
from app.agents.utils import get_time_prefix
from app.tools.stock_tools import (
    compare_stocks_tool,
    compute_metrics_tool,
    get_brvm_basics_tool,
    get_company_info_tool,
    get_market_overview_tool,
    get_stock_metrics_tool,
    get_timeseries_tool,
)


def get_analytics_agent_system() -> str:
    return f"""BRVM analytics. Answer from tools only. {get_time_prefix()} F CFA.

**CRITICAL:** Use the symbol from NLU entities for tool calls. The user's CURRENT question is the last HumanMessage. Do NOT use symbols from previous bot responses.

**Tools:** get_market_overview (rankings) | get_stock_metrics (price/volume) | get_timeseries | compare_stocks | compute_metrics (avg/min/max) | get_brvm_basics (FAQ) | get_company_info (name/sector)

**Rule:** Use get_company_info for company names. No invented data. No tool names in reply."""


ANALYTICS_TOOLS = [
    get_market_overview_tool,
    get_stock_metrics_tool,
    get_timeseries_tool,
    compare_stocks_tool,
    compute_metrics_tool,
    get_brvm_basics_tool,
    get_company_info_tool,
]


def create_analytics_agent(model: str = "glm-5:cloud"):
    llm = get_llm(model=model)
    return create_react_agent(llm, ANALYTICS_TOOLS)
