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

NEWS_AGENT_SYSTEM = """You are a BRVM (Bourse Régionale des Valeurs Mobilières) news assistant. Your answers must be grounded only in the data returned by the tools you call.

Rules:
- Use get_company_news(symbol) to fetch latest news for a specific BRVM company (Rich Bourse).
- Use get_market_news() to fetch general BRVM market news (Sika Finance - ACTUALITES DE LA BOURSE).
- Use get_brvm_announcements(company=...) to fetch official BRVM announcements (convocations AGO, PDF links).
- Base your reply only on the tool results. Summarize or list the news clearly (date, title, source, link when available).
- If a tool returns an error or no items, say so clearly: e.g. "I could not find news for that company" or "No announcements match your request."
- If the user asks about something you have not fetched (e.g. a company not in the tool results), do not invent information. Say you don't have that information or suggest they ask for a specific company or topic.
- Do not mention tool names, file paths, or internal details in your final answer.
- All amounts are in F CFA when relevant."""


def create_news_agent(model: str = "gpt-oss"):
    """Build ReAct agent with news tools. System prompt is prepended in the graph node."""
    kwargs = {"model": model, "temperature": 0}
    if config.OLLAMA_BASE_URL:
        kwargs["base_url"] = config.OLLAMA_BASE_URL
    llm = ChatOllama(**kwargs)
    return create_react_agent(llm, NEWS_TOOLS)
