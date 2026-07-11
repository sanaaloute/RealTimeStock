"""Portfolio, tracking, price targets.

Security: the user identity (telegram_user_id) is injected from the run config
at call time (`config["configurable"]["telegram_user_id"]`, set by run_agent
from the verified chat context). It is NOT a tool argument — the model never
sees it and cannot choose it, so a prompt injection cannot make one user read
or modify another user's portfolio. Config propagates through the nested
worker agent via LangChain's config context, so it reaches the tool unchanged.
"""
from __future__ import annotations

import json
from typing import Annotated

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from pydantic import Field

from app.utils import user_db


def _user_id_from_config(config: RunnableConfig | None) -> int | None:
    uid = ((config or {}).get("configurable") or {}).get("telegram_user_id")
    return uid if isinstance(uid, int) and uid > 0 else None


def _no_user_error() -> str:
    return json.dumps(
        {
            "ok": False,
            "error": "Portfolio, tracking and alerts are only available from a "
            "registered chat account (not available in this context).",
        }
    )


@tool
def portfolio_add(
    symbol: Annotated[str, Field(description="BRVM symbol (e.g. NTLC, SLBC).")],
    buy_price: Annotated[float, Field(description="Buy price in F CFA.")],
    buy_date: Annotated[str, Field(description="Buy date YYYY-MM-DD.")],
    quantity: Annotated[float, Field(description="Number of shares.")] = 1.0,
    config: RunnableConfig = None,
) -> str:
    """Add or update a stock position in the user's portfolio. Use for 'I bought NTLC at 50000 on 2025-01-15'. Optional: quantity (default 1)."""
    uid = _user_id_from_config(config)
    if uid is None:
        return _no_user_error()
    return json.dumps(user_db.portfolio_add(uid, symbol, buy_price, buy_date, quantity), default=str)


@tool
def portfolio_remove(
    symbol: Annotated[str, Field(description="BRVM symbol to remove.")],
    config: RunnableConfig = None,
) -> str:
    """Remove a symbol from the user's portfolio."""
    uid = _user_id_from_config(config)
    if uid is None:
        return _no_user_error()
    return json.dumps(user_db.portfolio_remove(uid, symbol), default=str)


@tool
def get_portfolio(
    config: RunnableConfig = None,
) -> str:
    """Get the user's portfolio with current prices and gain/loss % per position. Use for 'show my portfolio', 'my portfolio'."""
    uid = _user_id_from_config(config)
    if uid is None:
        return _no_user_error()
    return json.dumps(user_db.portfolio_with_prices(uid), default=str)


@tool
def get_portfolio_summary(
    config: RunnableConfig = None,
) -> str:
    """Get portfolio summary: total cost, total value, overall gain/loss %. Use for 'portfolio growth', 'portfolio loss', 'how is my portfolio doing'."""
    uid = _user_id_from_config(config)
    if uid is None:
        return _no_user_error()
    return json.dumps(user_db.portfolio_summary(uid), default=str)


@tool
def tracking_add(
    symbol: Annotated[str, Field(description="BRVM symbol to track.")],
    config: RunnableConfig = None,
) -> str:
    """Add a BRVM symbol to the user's tracking list."""
    uid = _user_id_from_config(config)
    if uid is None:
        return _no_user_error()
    return json.dumps(user_db.tracking_add(uid, symbol), default=str)


@tool
def tracking_remove(
    symbol: Annotated[str, Field(description="BRVM symbol to remove.")],
    config: RunnableConfig = None,
) -> str:
    """Remove a symbol from the user's tracking list."""
    uid = _user_id_from_config(config)
    if uid is None:
        return _no_user_error()
    return json.dumps(user_db.tracking_remove(uid, symbol), default=str)


@tool
def get_tracking(
    config: RunnableConfig = None,
) -> str:
    """List symbols the user is tracking."""
    uid = _user_id_from_config(config)
    if uid is None:
        return _no_user_error()
    return json.dumps(user_db.tracking_list(uid), default=str)


@tool
def target_add(
    symbol: Annotated[str, Field(description="BRVM symbol.")],
    target_price: Annotated[float, Field(description="Target price in F CFA.")],
    direction: Annotated[str, Field(description="Notify when price goes 'above' or 'below' target.")] = "above",
    config: RunnableConfig = None,
) -> str:
    """Set a price alert: notify the user when the symbol goes above or below the target price (F CFA)."""
    uid = _user_id_from_config(config)
    if uid is None:
        return _no_user_error()
    return json.dumps(user_db.target_add(uid, symbol, target_price, direction), default=str)


@tool
def target_remove(
    symbol: Annotated[str, Field(description="BRVM symbol.")],
    config: RunnableConfig = None,
) -> str:
    """Remove a price alert for a symbol."""
    uid = _user_id_from_config(config)
    if uid is None:
        return _no_user_error()
    return json.dumps(user_db.target_remove(uid, symbol), default=str)


@tool
def get_targets(
    config: RunnableConfig = None,
) -> str:
    """List the user's price alerts (targets)."""
    uid = _user_id_from_config(config)
    if uid is None:
        return _no_user_error()
    return json.dumps(user_db.target_list(uid), default=str)


PORTFOLIO_TOOLS = [
    get_portfolio,
    get_portfolio_summary,
    portfolio_add,
    portfolio_remove,
    get_tracking,
    tracking_add,
    tracking_remove,
    get_targets,
    target_add,
    target_remove,
]
