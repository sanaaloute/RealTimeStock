"""Scraper worker agent: fetches data from Sika Finance, Rich Bourse, BRVM."""
from __future__ import annotations

from langchain_ollama import ChatOllama
from langgraph.prebuilt import create_react_agent

import config
from ..tools.stock_tools import (
    scrape_brvm,
    scrape_richbourse,
    scrape_richbourse_timeseries,
    scrape_sikafinance,
)

SCRAPER_TOOLS = [
    scrape_sikafinance,
    scrape_richbourse,
    scrape_richbourse_timeseries,
    scrape_brvm,
]


def create_scraper_agent(model: str = "gpt-oss"):
    """Build ReAct agent with scraper tools. Use for: fetch palmarès, variation, timeseries CSV, BRVM."""
    kwargs = {"model": model, "temperature": 0}
    if config.OLLAMA_BASE_URL:
        kwargs["base_url"] = config.OLLAMA_BASE_URL
    llm = ChatOllama(**kwargs)
    return create_react_agent(llm, SCRAPER_TOOLS)
