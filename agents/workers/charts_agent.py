"""Charts worker: plot company price over a period (line/area); returns image path for supervisor."""

from __future__ import annotations

import json

from langchain_core.messages import ToolMessage
from langgraph.prebuilt import create_react_agent

from agents.llm import get_llm
from agents.utils import get_time_prefix
from ..tools.stock_tools import get_timeseries_tool, plot_company_chart_tool


def get_charts_agent_system() -> str:
    """System prompt for the charts worker."""
    return f"""You are the BRVM charts worker. You produce a price chart (line or area) for a BRVM stock over a date range. You must call get_timeseries_tool if needed, then plot_company_chart_tool to generate the image.

**{get_time_prefix()}**

**Tools:** get_timeseries_tool (fetch time series for symbol and dates), plot_company_chart_tool (symbol, start_date, end_date, chart_type=line|area). Always produce the chart when the user asked for a graph/plot; the tool returns an image path that the system will send to the user. Do not mention the image path or file system in your final reply; just confirm the chart and briefly describe what it shows. All amounts in F CFA."""


CHARTS_TOOLS = [
    get_timeseries_tool,
    plot_company_chart_tool,
]


def _extract_image_path_from_messages(messages: list) -> str | None:
    """Scan tool messages for plot_company_chart result containing image_path."""
    for m in reversed(messages):
        if isinstance(m, ToolMessage) and m.name == "plot_company_chart" and m.content:
            try:
                data = json.loads(m.content) if isinstance(m.content, str) else m.content
                path = data.get("image_path") if isinstance(data, dict) else None
                if path and isinstance(path, str):
                    return path
            except (json.JSONDecodeError, TypeError):
                pass
            # Fallback: content might be path-like
            s = str(m.content).strip()
            if s.endswith(".png") and "/" in s:
                return s
    return None


def create_charts_agent(model: str = "qwen3:8b"):
    """Build ReAct agent with get_timeseries and plot_company_chart (returns image path in tool result)."""
    llm = get_llm(model=model, temperature=0)
    return create_react_agent(llm, CHARTS_TOOLS)
