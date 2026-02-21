"""Service: compare two stocks (growth, loss, price, period price, market cap, volume)."""
from __future__ import annotations

from datetime import date
from typing import Any

from ._data import fetch_palmares, load_series
from .stock_metrics import get_stock_metrics


def compare_stocks(
    symbol_a: str,
    symbol_b: str,
    period: str = "veille",
    period_price_date: date | str | None = None,
) -> dict[str, Any]:
    """
    Compare two stocks: growth, loss, current price, volume, market cap.
    If period_price_date is set, also compare price at that date (from time series).
    """
    symbol_a = (symbol_a or "").strip().upper()
    symbol_b = (symbol_b or "").strip().upper()

    ma = get_stock_metrics(symbol_a, at_time=None, period=period)
    mb = get_stock_metrics(symbol_b, at_time=None, period=period)

    comparison: dict[str, Any] = {
        "period": period,
        "symbol_a": symbol_a,
        "symbol_b": symbol_b,
        "a": {
            "price": ma.get("price"),
            "volume": ma.get("volume"),
            "growth_pct": ma.get("growth_pct"),
            "loss_pct": ma.get("loss_pct"),
            "capitalisation": ma.get("capitalisation"),
        },
        "b": {
            "price": mb.get("price"),
            "volume": mb.get("volume"),
            "growth_pct": mb.get("growth_pct"),
            "loss_pct": mb.get("loss_pct"),
            "capitalisation": mb.get("capitalisation"),
        },
        "period_price_date": None,
        "a_period_price": None,
        "b_period_price": None,
    }

    if period_price_date is not None:
        d = period_price_date if isinstance(period_price_date, date) else date.fromisoformat(str(period_price_date)[:10])
        comparison["period_price_date"] = d.isoformat()
        sa = load_series(symbol_a, start_date=d, end_date=d, fetch_if_missing=True)
        sb = load_series(symbol_b, start_date=d, end_date=d, fetch_if_missing=True)
        comparison["a_period_price"] = sa[0]["price"] if sa else None
        comparison["b_period_price"] = sb[0]["price"] if sb else None

    return comparison
