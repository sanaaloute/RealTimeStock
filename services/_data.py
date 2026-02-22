"""Shared data access: palmarès (Rich Bourse) and time series from CSV."""
from __future__ import annotations

import csv
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from scrapers.richbourse import RichBourseScraper
from scrapers.richbourse_timeseries import RichBourseTimeseriesScraper

DATA_SERIES_DIR = Path("data/series")
MAX_AGE_DAYS = 1  # CSV considered stale if last date is older than this


def fetch_palmares(period: str = "veille", progression: str = "tout") -> list[dict[str, Any]]:
    """Fetch current palmarès from Rich Bourse. Returns list of stocks with symbol, cours_actuel, volume, variation_pct, capitalisation, etc."""
    scraper = RichBourseScraper(period=period, progression=progression)
    result = scraper.scrape()
    if result.get("error"):
        return []
    return result.get("stocks") or []


def _find_series_csv(symbol: str) -> Path | None:
    """Return path to a CSV for symbol if it exists (any date range). Prefer newest by filename date."""
    symbol = symbol.strip().upper()
    if not DATA_SERIES_DIR.exists():
        return None
    candidates = list(DATA_SERIES_DIR.glob(f"{symbol}_*.csv"))
    if not candidates:
        return None
    # Filename: SYMBOL_YYYY-MM-DD_YYYY-MM-DD.csv — use last date (end_date)
    def end_date_from_path(p: Path) -> date:
        try:
            parts = p.stem.split("_")
            if len(parts) >= 3:
                return date.fromisoformat(parts[-1][:10])
        except ValueError:
            pass
        return date.min

    return max(candidates, key=end_date_from_path)


def get_series_status(symbol: str) -> dict[str, Any]:
    """Return status for one symbol: path, last_date, up_to_date (last_date >= today - MAX_AGE_DAYS)."""
    symbol = symbol.strip().upper()
    out: dict[str, Any] = {"symbol": symbol, "path": None, "last_date": None, "up_to_date": False}
    p = _find_series_csv(symbol)
    if not p or not p.exists():
        return out
    out["path"] = str(p)
    try:
        parts = p.stem.split("_")
        if len(parts) >= 3:
            out["last_date"] = parts[-1][:10]
            last = date.fromisoformat(out["last_date"])
            out["up_to_date"] = last >= (date.today() - timedelta(days=MAX_AGE_DAYS))
    except ValueError:
        pass
    return out


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


def ensure_timeseries_up_to_date(symbol: str) -> dict[str, Any]:
    """Check CSV for symbol; if missing or stale (older than MAX_AGE_DAYS), fetch and save. Return status."""
    status = get_series_status(symbol)
    if status["up_to_date"] and status["path"]:
        return {"symbol": symbol, "action": "skipped", "path": status["path"], "message": "Already up to date."}
    scraper = RichBourseTimeseriesScraper(symbol=symbol, output_dir=DATA_SERIES_DIR)
    result = scraper.scrape()
    if result.get("error"):
        return {"symbol": symbol, "action": "error", "error": result["error"]}
    return {
        "symbol": symbol,
        "action": "updated",
        "path": result.get("csv_path"),
        "rows": result.get("rows", 0),
        "date_range": result.get("date_range"),
    }


def list_series_status(symbols: list[str] | None = None) -> list[dict[str, Any]]:
    """List status for each symbol. If symbols is None, scan data/series for all SYMBOL_*.csv."""
    if symbols:
        return [get_series_status(s) for s in symbols]
    if not DATA_SERIES_DIR.exists():
        return []
    seen: set[str] = set()
    statuses: list[dict[str, Any]] = []
    for p in DATA_SERIES_DIR.glob("*_*.csv"):
        sym = p.stem.split("_")[0].upper()
        if sym not in seen:
            seen.add(sym)
            statuses.append(get_series_status(sym))
    return statuses


def run_daily_timeseries_update(symbols: list[str]) -> list[dict[str, Any]]:
    """Update CSVs for all symbols (call once per day). Returns list of per-symbol results."""
    results: list[dict[str, Any]] = []
    for symbol in symbols:
        results.append(ensure_timeseries_up_to_date(symbol))
    return results


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
