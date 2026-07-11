"""
Rich Bourse time-series scraper: fetch chart data (Highcharts) for a symbol and save to CSV.

URL: https://www.richbourse.com/common/mouvements/index/{symbol}
CSV: data/series/{symbol}_{min_date}_{max_date}.csv
"""
import csv
import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import requests

from .base import BaseScraper

logger = logging.getLogger(__name__)

BASE_URL = "https://www.richbourse.com/common/mouvements/index"
DATA_SERIES_DIR = Path(__file__).resolve().parent.parent / "data" / "series"


def extract_highcharts_series(html: str) -> list[list[int | float]] | None:
    """Extract first Highcharts data array [[timestamp_ms, value], ...] from page."""
    pattern = r"\?\s*(\[\[.*?\]\])\s*:"
    match = re.search(pattern, html, re.DOTALL)
    if not match:
        return None
    return json.loads(match.group(1))


class RichBourseTimeseriesScraper(BaseScraper):
    """Fetch mouvement page for a symbol, extract time series from Highcharts, save to CSV."""

    def __init__(
        self,
        symbol: str,
        api_key: str | None = None,
        sleep_seconds: float | None = None,
        output_dir: Path | str | None = None,
    ):
        super().__init__(api_key=api_key, sleep_seconds=sleep_seconds)
        self._symbol = (symbol or "").strip().upper()
        self._output_dir = Path(output_dir) if output_dir else DATA_SERIES_DIR

    @property
    def url(self) -> str:
        return f"{BASE_URL}/{self._symbol}"

    def scrape(self) -> dict[str, Any]:
        """Fetch page, extract series, write CSV to data/series/{symbol}_{min_date}_{max_date}.csv."""
        out: dict[str, Any] = {
            "source": "richbourse_timeseries",
            "url": self.url,
            "symbol": self._symbol,
            "csv_path": None,
            "date_range": None,
            "rows": 0,
            "error": None,
        }
        if not self._symbol:
            out["error"] = "symbol is required"
            return out

        try:
            self._sleep()
            resp = requests.get(
                self.url,
                timeout=30,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; rv:109.0) Gecko/20100101 Firefox/115.0"},
            )
            resp.raise_for_status()
            self._sleep()
            html = resp.text
        except Exception as e:
            logger.warning("Fetch failed for %s: %s", self.url, e)
            out["error"] = str(e)
            return out

        series = extract_highcharts_series(html)
        if not series:
            out["error"] = "No Highcharts series found"
            return out

        records = []
        for timestamp_ms, price in series:
            dt = datetime.fromtimestamp(timestamp_ms / 1000)
            records.append({"date": dt, "price": price})

        records.sort(key=lambda r: r["date"])
        if not records:
            out["error"] = "No data points"
            return out

        min_dt = records[0]["date"]
        max_dt = records[-1]["date"]
        min_str = min_dt.strftime("%Y-%m-%d")
        max_str = max_dt.strftime("%Y-%m-%d")
        out["date_range"] = [min_str, max_str]
        out["rows"] = len(records)

        self._output_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{self._symbol}_{min_str}_{max_str}.csv"
        csv_path = self._output_dir / filename

        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["Date", "Price"])
            w.writeheader()
            for r in records:
                w.writerow({"Date": r["date"].strftime("%Y-%m-%d %H:%M:%S"), "Price": r["price"]})

        out["csv_path"] = str(csv_path)
        return out
