"""Scraper worker: Sika Finance, Rich Bourse, BRVM."""
from __future__ import annotations

from langgraph.prebuilt import create_react_agent

from agents.llm import get_llm
from agents.utils import get_time_prefix
from ..tools.stock_tools import (
    scrape_brvm,
    scrape_richbourse,
    scrape_richbourse_timeseries,
    scrape_sikafinance,
)


def get_scraper_agent_system() -> str:
    """System prompt for the scraper worker."""
    return f"""You are the BRVM data-fetch worker. You call tools to retrieve raw data from BRVM sources. Do not compute metrics or charts—only fetch and report what the tools return.

**{get_time_prefix()}**

**Tools:** scrape_sikafinance (palmarès), scrape_richbourse (variation), scrape_richbourse_timeseries (symbol, date range → CSV), scrape_brvm (BRVM official site). Use the tool that matches the user request. Report results clearly; do not mention file paths or internal details in the final answer. All amounts are in F CFA."""


SCRAPER_TOOLS = [
    scrape_sikafinance,
    scrape_richbourse,
    scrape_richbourse_timeseries,
    scrape_brvm,
]


def create_scraper_agent(model: str = "glm-5:cloud"):
    llm = get_llm(model=model, temperature=0)
    return create_react_agent(llm, SCRAPER_TOOLS)
