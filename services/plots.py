"""Plot time series for a company (line, area, etc.) and save to a temp file."""
from __future__ import annotations

import tempfile
from datetime import date
from pathlib import Path
from typing import Any, Literal

from ._data import load_series

ChartType = Literal["line", "area"]


def plot_timeseries(
    symbol: str,
    start_date: str | date,
    end_date: str | date,
    chart_type: ChartType = "line",
    *,
    fetch_if_missing: bool = True,
) -> dict[str, Any]:
    """
    Plot price over period and save to a temp PNG. Uses most up-to-date CSV for symbol.
    Returns {"image_path": path, "symbol", "start_date", "end_date", "points_count", "error": optional}.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    symbol = (symbol or "").strip().upper()
    start = start_date if isinstance(start_date, date) else date.fromisoformat(str(start_date)[:10])
    end = end_date if isinstance(end_date, date) else date.fromisoformat(str(end_date)[:10])

    rows = load_series(symbol, start_date=start, end_date=end, fetch_if_missing=fetch_if_missing)
    if not rows:
        return {
            "symbol": symbol,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "image_path": None,
            "points_count": 0,
            "error": "No data for this period.",
        }

    dates = [r["date"] for r in rows]
    prices = [r["price"] for r in rows]

    fig, ax = plt.subplots(figsize=(10, 5))
    if chart_type == "area":
        ax.fill_between(dates, prices, alpha=0.3)
    ax.plot(dates, prices, color="#1f77b4", linewidth=2)
    ax.set_xlabel("Date")
    ax.set_ylabel("Price (F CFA)")
    ax.set_title(f"{symbol} — {start} to {end}")
    fig.autofmt_xdate()
    plt.tight_layout()

    import os
    fd, path = tempfile.mkstemp(suffix=".png", prefix="chart_")
    try:
        plt.savefig(path, dpi=100)
    finally:
        os.close(fd)
    plt.close(fig)

    return {
        "symbol": symbol,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "image_path": path,
        "points_count": len(rows),
        "error": None,
    }
