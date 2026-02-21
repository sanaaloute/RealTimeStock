"""Service: current or given-time price, volume, growth, loss for a stock."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

from ._data import fetch_palmares, load_series


def get_stock_metrics(
    symbol: str,
    at_time: date | datetime | str | None = None,
    *,
    period: str = "veille",
) -> dict[str, Any]:
    """
    Get price, volume, growth, loss for a stock.
    If at_time is None: current data from palmarès (Rich Bourse).
    If at_time is set: historical price from time series (volume/growth/loss may be N/A).
    """
    symbol = (symbol or "").strip().upper()
    out: dict[str, Any] = {
        "symbol": symbol,
        "price": None,
        "volume": None,
        "growth_pct": None,
        "loss_pct": None,
        "capitalisation": None,
        "at_time": None,
        "source": "palmares",
    }

    if at_time is None:
        stocks = fetch_palmares(period=period, progression="tout")
        for s in stocks:
            if (s.get("symbol") or "").strip().upper() == symbol:
                out["price"] = s.get("cours_actuel")
                out["volume"] = s.get("volume")
                out["capitalisation"] = s.get("capitalisation")
                var = s.get("variation_pct")
                if var is not None:
                    out["growth_pct"] = var if var >= 0 else None
                    out["loss_pct"] = -var if var < 0 else None
                out["at_time"] = "current"
                break
        return out

    # Historical: resolve date and look up in series
    if isinstance(at_time, datetime):
        d = at_time.date()
    elif isinstance(at_time, str):
        d = date.fromisoformat(at_time.strip()[:10])
    else:
        d = at_time
    out["at_time"] = d.isoformat()
    out["source"] = "timeseries"

    series = load_series(symbol, start_date=d, end_date=d, fetch_if_missing=True)
    if series:
        out["price"] = series[0]["price"]
    # Volume/growth/loss not in chart data
    return out
