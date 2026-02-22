"""News worker: fetch BRVM news from Rich Bourse, Sika Finance, BRVM. Answer only from fetched data; otherwise say you don't know or ask to clarify."""
from __future__ import annotations

from langchain_ollama import ChatOllama
from langgraph.prebuilt import create_react_agent

import config
from ..tools.stock_tools import (
    get_brvm_announcements_tool,
    get_company_news_tool,
    get_market_news_tool,
)

NEWS_TOOLS = [
    get_company_news_tool,
    get_market_news_tool,
    get_brvm_announcements_tool,
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

**Rules:**
1. Call the relevant tool(s) first. Base your reply strictly on the returned items.
2. Present news as a clear list or summary: date, title, source. Include links when the tool provides them.
3. If a tool returns an error or empty list: say so plainly (e.g. "No news found for that company" or "No announcements match your request").
4. If the user asks about a company or topic you did not fetch: do not invent. Say you do not have that information or suggest they ask for a specific company.
5. Do not mention tool names, file paths, or internal implementation in your answer. All amounts in F CFA when relevant."""


def create_news_agent(model: str = "qwen3:8b"):
    """Build ReAct agent with news tools. System prompt is prepended in the graph node."""
    kwargs = {"model": model, "temperature": 0}
    if config.OLLAMA_BASE_URL:
        kwargs["base_url"] = config.OLLAMA_BASE_URL
    llm = ChatOllama(**kwargs)
    return create_react_agent(llm, NEWS_TOOLS)
