"""News worker: fetch BRVM news from Rich Bourse, Sika Finance, BRVM."""
from __future__ import annotations

from langgraph.prebuilt import create_react_agent

from agents.llm import get_llm
from ..tools.stock_tools import (
    get_brvm_announcements_tool,
    get_company_info_tool,
    get_company_news_tool,
    get_market_news_tool,
)

NEWS_TOOLS = [
    get_company_news_tool,
    get_market_news_tool,
    get_brvm_announcements_tool,
    get_company_info_tool,
]

def get_news_agent_system() -> str:
    """News agent system prompt with current time injected."""
    from agents.utils import get_time_prefix
    return f"""You are the BRVM news worker. You answer only from data returned by your tools. Do not invent or assume any fact not present in tool results.

**{get_time_prefix()}**

**Tools:**
- get_company_news(symbol): Rich Bourse news for one BRVM company. Call with the exact symbol (e.g. NTLC, SLBC).
- get_market_news(): Sika Finance — "ACTUALITES DE LA BOURSE" (general BRVM market news).
- get_brvm_announcements(company=...): Official BRVM announcements (convocations, AGO, etc.) with PDF links when available.
- get_company_info(symbol): Get full company name and sector. Use when presenting news to give accurate company context.

**Rules:**
1. Call the relevant tool(s) first. Base your reply strictly on the returned items.
2. When presenting news about a company, use get_company_info to get the accurate full name and sector—do not guess or invent.
3. Present news as a clear list or summary: date, title, source. Include links when the tool provides them.
4. If a tool returns an error or empty list: say so plainly (e.g. "No news found for that company" or "No announcements match your request").
5. If the user asks about a company or topic you did not fetch: do not invent. Say you do not have that information or suggest they ask for a specific company.
6. Do not mention tool names, file paths, or internal implementation in your answer. All amounts in F CFA when relevant."""


def create_news_agent(model: str = "glm-5:cloud"):
    llm = get_llm(model=model, temperature=0)
    return create_react_agent(llm, NEWS_TOOLS)
