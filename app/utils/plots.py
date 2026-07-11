"""Plot time series for a company (line, area, etc.) and save to a temp file."""
from __future__ import annotations

import os
import tempfile
from datetime import date
from typing import Any, Literal

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np

from app.utils._data import load_series

ChartType = Literal["line", "area"]

# Modern color palette: teal accent with gradient fill
LINE_COLOR = "#0d9488"
FILL_ALPHA = 0.35
GRID_ALPHA = 0.25
BG_COLOR = "#fafafa"


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
    prices = np.array([r["price"] for r in rows], dtype=float)
    x_numeric = mdates.date2num(dates)

    fig, ax = plt.subplots(figsize=(11, 6), facecolor=BG_COLOR)
    ax.set_facecolor(BG_COLOR)

    # Fill under the line (gradient effect: darker at top, lighter at bottom)
    ax.fill_between(
        dates,
        prices,
        prices.min() - (prices.max() - prices.min()) * 0.02,
        alpha=FILL_ALPHA,
        color=LINE_COLOR,
        interpolate=True,
    )

    # Main line
    ax.plot(
        dates,
        prices,
        color=LINE_COLOR,
        linewidth=2.5,
        solid_capstyle="round",
        solid_joinstyle="round",
    )

    # Grid
    ax.grid(True, linestyle="-", alpha=GRID_ALPHA)
    ax.set_axisbelow(True)

    # Labels and title
    ax.set_xlabel("Date", fontsize=11, color="#374151")
    ax.set_ylabel("Price (F CFA)", fontsize=11, color="#374151")
    ax.set_title(f"{symbol} — {start} to {end}", fontsize=14, fontweight=600, color="#111827", pad=12)

    # Tidy spines
    for spine in ax.spines.values():
        spine.set_color("#e5e7eb")
        spine.set_linewidth(0.8)

    # Y-axis: format with thousands separators for F CFA
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f"{x:,.0f}"))

    # Date formatting
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b %Y"))
    ax.xaxis.set_major_locator(mdates.AutoDateLocator(maxticks=8))
    fig.autofmt_xdate()

    plt.tight_layout()

    fd, path = tempfile.mkstemp(suffix=".png", prefix="chart_")
    try:
        plt.savefig(path, dpi=120, facecolor=BG_COLOR, edgecolor="none", bbox_inches="tight")
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
