"""Portfolio, tracking, price targets (telegram_id from context)."""
from __future__ import annotations

import json
from typing import Any

from langchain_core.tools import StructuredTool

from app.utils import user_db
from .schemas import (
    GetPortfolioInput,
    GetPortfolioSummaryInput,
    GetTargetsInput,
    GetTrackingInput,
    PortfolioAddInput,
    PortfolioRemoveInput,
    TargetAddInput,
    TargetRemoveInput,
    TrackingAddInput,
    TrackingRemoveInput,
)


def _run_portfolio_add(telegram_id: int, symbol: str, buy_price: float, buy_date: str, quantity: float = 1.0, **kwargs: Any) -> str:
    return json.dumps(user_db.portfolio_add(telegram_id, symbol, buy_price, buy_date, quantity), default=str)


def _run_portfolio_remove(telegram_id: int, symbol: str, **kwargs: Any) -> str:
    return json.dumps(user_db.portfolio_remove(telegram_id, symbol), default=str)


def _run_get_portfolio(telegram_id: int, **kwargs: Any) -> str:
    return json.dumps(user_db.portfolio_with_prices(telegram_id), default=str)


def _run_get_portfolio_summary(telegram_id: int, **kwargs: Any) -> str:
    return json.dumps(user_db.portfolio_summary(telegram_id), default=str)


def _run_tracking_add(telegram_id: int, symbol: str, **kwargs: Any) -> str:
    return json.dumps(user_db.tracking_add(telegram_id, symbol), default=str)


def _run_tracking_remove(telegram_id: int, symbol: str, **kwargs: Any) -> str:
    return json.dumps(user_db.tracking_remove(telegram_id, symbol), default=str)


def _run_get_tracking(telegram_id: int, **kwargs: Any) -> str:
    return json.dumps(user_db.tracking_list(telegram_id), default=str)


def _run_target_add(telegram_id: int, symbol: str, target_price: float, direction: str = "above", **kwargs: Any) -> str:
    return json.dumps(user_db.target_add(telegram_id, symbol, target_price, direction), default=str)


def _run_target_remove(telegram_id: int, symbol: str, **kwargs: Any) -> str:
    return json.dumps(user_db.target_remove(telegram_id, symbol), default=str)


def _run_get_targets(telegram_id: int, **kwargs: Any) -> str:
    return json.dumps(user_db.target_list(telegram_id), default=str)


portfolio_add_tool = StructuredTool.from_function(
    func=_run_portfolio_add,
    name="portfolio_add",
    description="Add or update a stock position in the user's portfolio. Use the telegram_id from context. Requires: symbol, buy_price (F CFA), buy_date (YYYY-MM-DD). Optional: quantity (default 1).",
    args_schema=PortfolioAddInput,
)
portfolio_remove_tool = StructuredTool.from_function(
    func=_run_portfolio_remove,
    name="portfolio_remove",
    description="Remove a symbol from the user's portfolio.",
    args_schema=PortfolioRemoveInput,
)
get_portfolio_tool = StructuredTool.from_function(
    func=_run_get_portfolio,
    name="get_portfolio",
    description="Get the user's portfolio with current prices and gain/loss % per position. Use for 'show my portfolio', 'my portfolio'.",
    args_schema=GetPortfolioInput,
)
get_portfolio_summary_tool = StructuredTool.from_function(
    func=_run_get_portfolio_summary,
    name="get_portfolio_summary",
    description="Get portfolio summary: total cost, total value, overall gain/loss %. Use for 'portfolio growth', 'portfolio loss', 'how is my portfolio doing'.",
    args_schema=GetPortfolioSummaryInput,
)
tracking_add_tool = StructuredTool.from_function(
    func=_run_tracking_add,
    name="tracking_add",
    description="Add a BRVM symbol to the user's tracking list.",
    args_schema=TrackingAddInput,
)
tracking_remove_tool = StructuredTool.from_function(
    func=_run_tracking_remove,
    name="tracking_remove",
    description="Remove a symbol from the user's tracking list.",
    args_schema=TrackingRemoveInput,
)
get_tracking_tool = StructuredTool.from_function(
    func=_run_get_tracking,
    name="get_tracking",
    description="List symbols the user is tracking.",
    args_schema=GetTrackingInput,
)
target_add_tool = StructuredTool.from_function(
    func=_run_target_add,
    name="target_add",
    description="Set a price alert: notify the user when the symbol goes above or below the target price (F CFA). direction: 'above' or 'below'.",
    args_schema=TargetAddInput,
)
target_remove_tool = StructuredTool.from_function(
    func=_run_target_remove,
    name="target_remove",
    description="Remove a price alert for a symbol.",
    args_schema=TargetRemoveInput,
)
get_targets_tool = StructuredTool.from_function(
    func=_run_get_targets,
    name="get_targets",
    description="List the user's price alerts (targets).",
    args_schema=GetTargetsInput,
)

PORTFOLIO_TOOLS = [
    get_portfolio_tool,
    get_portfolio_summary_tool,
    portfolio_add_tool,
    portfolio_remove_tool,
    get_tracking_tool,
    tracking_add_tool,
    tracking_remove_tool,
    get_targets_tool,
    target_add_tool,
    target_remove_tool,
]
