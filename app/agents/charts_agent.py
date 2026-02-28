"""Charts worker: plot stock price (line/area), returns image path."""

from __future__ import annotations

import json

from langchain_core.messages import ToolMessage
from langgraph.prebuilt import create_react_agent

from app.models.llm import get_llm
from app.agents.utils import get_time_prefix
from app.tools.stock_tools import get_timeseries_tool, plot_company_chart_tool


def get_charts_agent_system() -> str:
    return f"""BRVM charts. Produce price chart (line/area). {get_time_prefix()} F CFA.

**CRITICAL:** Use the symbol from NLU entities. Do NOT use symbols from previous messages.

**Tools:** get_timeseries (symbol, dates) → plot_company_chart (symbol, start_date, end_date, chart_type=line|area)

**Rule:** Call both tools. Do not mention image path. Confirm chart and briefly describe."""


CHARTS_TOOLS = [
    get_timeseries_tool,
    plot_company_chart_tool,
]


def _extract_image_path_from_messages(messages: list) -> str | None:
    for m in reversed(messages):
        if isinstance(m, ToolMessage) and m.name == "plot_company_chart" and m.content:
            try:
                data = json.loads(m.content) if isinstance(m.content, str) else m.content
                path = data.get("image_path") if isinstance(data, dict) else None
                if path and isinstance(path, str):
                    return path
            except (json.JSONDecodeError, TypeError):
                pass
            s = str(m.content).strip()
            if s.endswith(".png") and "/" in s:
                return s
    return None


def create_charts_agent(model: str = "glm-5:cloud"):
    llm = get_llm(model=model)
    return create_react_agent(llm, CHARTS_TOOLS)
