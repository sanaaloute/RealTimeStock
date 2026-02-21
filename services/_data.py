"""Shared data access: palmarès (Rich Bourse) and time series from CSV."""
from __future__ import annotations

import csv
from datetime import date, datetime
from pathlib import Path
from typing import Any

from scrapers.richbourse import RichBourseScraper
from scrapers.richbourse_timeseries import RichBourseTimeseriesScraper

DATA_SERIES_DIR = Path("data/series")


def fetch_palmares(period: str = "veille", progression: str = "tout") -> list[dict[str, Any]]:
    """Fetch current palmarès from Rich Bourse. Returns list of stocks with symbol, cours_actuel, volume, variation_pct, capitalisation, etc."""
    scraper = RichBourseScraper(period=period, progression=progression)
    result = scraper.scrape()
    if result.get("error"):
        return []
    return result.get("stocks") or []


def _find_series_csv(symbol: str) -> Path | None:
    """Return path to a CSV for symbol if it exists (any date range)."""
    symbol = symbol.strip().upper()
    if not DATA_SERIES_DIR.exists():
        return None
    for p in DATA_SERIES_DIR.glob(f"{symbol}_*.csv"):
        return p
    return None


def ensure_series_csv(symbol: str) -> Path | None:
    """Ensure we have a series CSV for symbol; fetch if missing. Returns path or None."""
    p = _find_series_csv(symbol)
    if p is not None:
        return p
    scraper = RichBourseTimeseriesScraper(symbol=symbol, output_dir=DATA_SERIES_DIR)
    result = scraper.scrape()
    if result.get("error") or not result.get("csv_path"):
        return None
    return Path(result["csv_path"])


def load_series(
    symbol: str,
    start_date: date | str | None = None,
    end_date: date | str | None = None,
    *,
    fetch_if_missing: bool = True,
) -> list[dict[str, Any]]:
    """
    Load time series for symbol from data/series CSV.
    Returns list of {"date": date, "price": float}. Optional start/end filter (inclusive).
    If no CSV exists and fetch_if_missing, runs timeseries scraper first.
    """
    if fetch_if_missing:
        ensure_series_csv(symbol)
    p = _find_series_csv(symbol)
    if not p or not p.exists():
        return []

    def parse_dt(s: str) -> date:
        try:
            return datetime.strptime(s.strip()[:10], "%Y-%m-%d").date()
        except ValueError:
            return date.min

    rows: list[dict[str, Any]] = []
    with open(p, newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            dt_str = row.get("Date", "")
            price_str = row.get("Price", "")
            if not dt_str or not price_str:
                continue
            d = parse_dt(dt_str)
            try:
                price = float(price_str.replace(",", "."))
            except ValueError:
                continue
            if start_date is not None and d < (start_date if isinstance(start_date, date) else date.fromisoformat(str(start_date)[:10])):
                continue
            if end_date is not None and d > (end_date if isinstance(end_date, date) else date.fromisoformat(str(end_date)[:10])):
                continue
            rows.append({"date": d, "price": price})

    rows.sort(key=lambda r: r["date"])
    return rows
