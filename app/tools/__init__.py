"""LangChain tools for scrapers and services (agent stack: langchain, ollama, chromadb, RAG)."""
from langchain_core.tools import BaseTool

from .stock_tools import (
    compare_stocks_tool,
    compute_metrics_tool,
    fetch_sgi_data_tool,
    fetch_sgi_url_tool,
    get_sgi_data_tool,
    get_stock_metrics_tool,
    get_timeseries_tool,
    scrape_brvm,
    scrape_richbourse,
    scrape_richbourse_timeseries,
    scrape_sikafinance,
)

TOOLS: list[BaseTool] = [
    scrape_sikafinance,
    scrape_richbourse,
    scrape_richbourse_timeseries,
    scrape_brvm,
    get_stock_metrics_tool,
    get_timeseries_tool,
    compare_stocks_tool,
    compute_metrics_tool,
    get_sgi_data_tool,
    fetch_sgi_data_tool,
    fetch_sgi_url_tool,
]


def get_all_tools() -> list[BaseTool]:
    """Return all agent tools (scrapers + services)."""
    return list(TOOLS)


__all__ = [
    "TOOLS",
    "get_all_tools",
    "scrape_sikafinance",
    "scrape_richbourse",
    "scrape_richbourse_timeseries",
    "scrape_brvm",
    "get_stock_metrics_tool",
    "get_timeseries_tool",
    "compare_stocks_tool",
    "compute_metrics_tool",
    "get_sgi_data_tool",
    "fetch_sgi_data_tool",
    "fetch_sgi_url_tool",
]
