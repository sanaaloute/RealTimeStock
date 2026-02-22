"""Portfolio worker: user portfolio, tracking list, price targets. Uses telegram_id from state."""
from __future__ import annotations

from langchain_ollama import ChatOllama
from langgraph.prebuilt import create_react_agent

import config
from agents.utils import get_time_prefix
from ..tools.portfolio_tools import PORTFOLIO_TOOLS


def get_portfolio_agent_system(telegram_id: int) -> str:
    """System prompt for the portfolio worker; inject telegram_id so the LLM passes it to tools."""
    return f"""You are the BRVM portfolio and alerts worker. You help the user manage their portfolio (positions with buy price and date), their tracking list (symbols they watch), and price alerts (notify when a stock reaches a target price). All amounts are in F CFA. Use only BRVM symbols.

**{get_time_prefix()}**

**IMPORTANT:** For every portfolio/tracking/target tool call, you MUST use telegram_id: {telegram_id}. This is the current user's Telegram ID.

**Tools:**
- get_portfolio: show portfolio with current prices and gain/loss % per position. Use for "my portfolio", "show portfolio".
- get_portfolio_summary: total cost, total value, overall gain/loss %. Use for "portfolio growth", "how is my portfolio".
- portfolio_add: add or update a position (symbol, buy_price, buy_date, quantity). Use for "I bought NTLC at 50000 on 2025-01-15".
- portfolio_remove: remove a symbol from portfolio.
- get_tracking: list symbols the user is tracking.
- tracking_add / tracking_remove: add or remove a symbol from tracking list.
- get_targets: list user's price alerts.
- target_add: set alert (symbol, target_price, direction above/below). Use for "notify me when NTLC reaches 55000".
- target_remove: remove an alert for a symbol.

Present results clearly. Do not mention tool names or internal details in the final answer. When the user asks to remove a stock "from my portfolio and tracking", call both portfolio_remove and tracking_remove (and target_remove if they have an alert for that symbol)."""


def create_portfolio_agent(model: str = "qwen3:8b"):
    """Build ReAct agent with portfolio/tracking/target tools."""
    kwargs = {"model": model, "temperature": 0}
    if config.OLLAMA_BASE_URL:
        kwargs["base_url"] = config.OLLAMA_BASE_URL
    llm = ChatOllama(**kwargs)
    return create_react_agent(llm, PORTFOLIO_TOOLS)
