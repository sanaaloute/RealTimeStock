"""Charts worker: plot company price over a period (line/area); returns image path for supervisor."""

from __future__ import annotations

import json

from langchain_core.messages import ToolMessage
from langchain_ollama import ChatOllama
from langgraph.prebuilt import create_react_agent

import config
from ..tools.stock_tools import get_timeseries_tool, plot_company_chart_tool

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


def create_charts_agent(model: str = "gpt-oss"):
    """Build ReAct agent with get_timeseries and plot_company_chart (returns image path in tool result)."""
    kwargs = {"model": model, "temperature": 0}
    if config.OLLAMA_BASE_URL:
        kwargs["base_url"] = config.OLLAMA_BASE_URL
    llm = ChatOllama(**kwargs)
    return create_react_agent(llm, CHARTS_TOOLS)
