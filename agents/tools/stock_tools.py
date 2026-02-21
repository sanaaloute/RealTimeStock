"""LangChain tools wrapping scrapers and services."""
from __future__ import annotations

import json
from typing import Any

from langchain_core.tools import StructuredTool

from scrapers import BRVMScraper, RichBourseScraper, RichBourseTimeseriesScraper, SikaFinanceScraper
from services import compare_stocks, compute_metrics, get_stock_metrics, get_timeseries

import config
from .schemas import (
    CompareStocksInput,
    ComputeMetricsInput,
    GetStockMetricsInput,
    GetTimeseriesInput,
    ScrapeBrvmInput,
    ScrapeRichbourseInput,
    ScrapeRichbourseTimeseriesInput,
    ScrapeSikafinanceInput,
)

SLEEP = config.SLEEP_SECONDS


def _scrape_sikafinance(period: str) -> str:
    scraper = SikaFinanceScraper(period=period, sleep_seconds=SLEEP)
    data = scraper.scrape()
    return json.dumps(data, ensure_ascii=False, default=str)


def _scrape_richbourse(period: str, progression: str) -> str:
    scraper = RichBourseScraper(period=period, progression=progression, sleep_seconds=SLEEP)
    data = scraper.scrape()
    return json.dumps(data, ensure_ascii=False, default=str)


def _scrape_richbourse_timeseries(symbol: str) -> str:
    scraper = RichBourseTimeseriesScraper(symbol=symbol, output_dir="data/series", sleep_seconds=SLEEP)
    data = scraper.scrape()
    return json.dumps(data, ensure_ascii=False, default=str)


def _scrape_brvm(_: Any = None) -> str:
    scraper = BRVMScraper(sleep_seconds=SLEEP)
    data = scraper.scrape()
    return json.dumps(data, ensure_ascii=False, default=str)


def _get_stock_metrics(symbol: str, at_time: str | None = None, period: str = "veille") -> str:
    data = get_stock_metrics(symbol, at_time=at_time, period=period)
    return json.dumps(data, ensure_ascii=False, default=str)


def _get_timeseries(symbol: str, start_date: str, end_date: str) -> str:
    data = get_timeseries(symbol, start_date, end_date)
    return json.dumps(data, ensure_ascii=False, default=str)


def _compare_stocks(
    symbol_a: str,
    symbol_b: str,
    period: str = "veille",
    period_price_date: str | None = None,
) -> str:
    data = compare_stocks(symbol_a, symbol_b, period=period, period_price_date=period_price_date)
    return json.dumps(data, ensure_ascii=False, default=str)


def _compute_metrics(
    symbol: str,
    start_date: str | None = None,
    end_date: str | None = None,
) -> str:
    data = compute_metrics(symbol, start_date=start_date, end_date=end_date)
    return json.dumps(data, ensure_ascii=False, default=str)


# --- Tool runners: accept kwargs (LangChain invokes with **input) ---
def _run_sikafinance(period: str = "veille", **kwargs: Any) -> str:
    return _scrape_sikafinance(period)


def _run_richbourse(period: str = "veille", progression: str = "tout", **kwargs: Any) -> str:
    return _scrape_richbourse(period, progression)


def _run_richbourse_timeseries(symbol: str, **kwargs: Any) -> str:
    return _scrape_richbourse_timeseries(symbol)


def _run_brvm(**kwargs: Any) -> str:
    return _scrape_brvm()


def _run_stock_metrics(
    symbol: str,
    at_time: str | None = None,
    period: str = "veille",
    **kwargs: Any,
) -> str:
    return _get_stock_metrics(symbol, at_time, period or "veille")


def _run_timeseries(symbol: str, start_date: str, end_date: str, **kwargs: Any) -> str:
    return _get_timeseries(symbol, start_date, end_date)


def _run_compare(
    symbol_a: str,
    symbol_b: str,
    period: str = "veille",
    period_price_date: str | None = None,
    **kwargs: Any,
) -> str:
    return _compare_stocks(symbol_a, symbol_b, period or "veille", period_price_date)


def _run_compute_metrics(
    symbol: str,
    start_date: str | None = None,
    end_date: str | None = None,
    **kwargs: Any,
) -> str:
    return _compute_metrics(symbol, start_date, end_date)


scrape_sikafinance = StructuredTool.from_function(
    func=_run_sikafinance,
    name="scrape_sikafinance",
    description="Scrape Sika Finance palmarès (BRVM stocks: indices, gains, losses, volume). Returns JSON.",
    args_schema=ScrapeSikafinanceInput,
)

scrape_richbourse = StructuredTool.from_function(
    func=_run_richbourse,
    name="scrape_richbourse",
    description="Scrape Rich Bourse variation table (stocks with price, volume, variation %, capitalisation). Returns JSON.",
    args_schema=ScrapeRichbourseInput,
)

scrape_richbourse_timeseries = StructuredTool.from_function(
    func=_run_richbourse_timeseries,
    name="scrape_richbourse_timeseries",
    description="Fetch and save Rich Bourse time series for a stock symbol to data/series (CSV). Returns JSON with csv_path and row count.",
    args_schema=ScrapeRichbourseTimeseriesInput,
)

scrape_brvm = StructuredTool.from_function(
    func=_run_brvm,
    name="scrape_brvm",
    description="Scrape BRVM official site (indices and stocks). Returns JSON.",
    args_schema=ScrapeBrvmInput,
)

get_stock_metrics_tool = StructuredTool.from_function(
    func=_run_stock_metrics,
    name="get_stock_metrics",
    description="Get current or historical price, volume, growth %, loss % and capitalisation for a stock. Use at_time (YYYY-MM-DD) for historical price.",
    args_schema=GetStockMetricsInput,
)

get_timeseries_tool = StructuredTool.from_function(
    func=_run_timeseries,
    name="get_timeseries",
    description="Get time series (date, price) for a stock over a date range. Use for charts. Returns points list.",
    args_schema=GetTimeseriesInput,
)

compare_stocks_tool = StructuredTool.from_function(
    func=_run_compare,
    name="compare_stocks",
    description="Compare two stocks: price, volume, growth %, loss %, market cap. Optionally compare price at a given date (period_price_date).",
    args_schema=CompareStocksInput,
)

compute_metrics_tool = StructuredTool.from_function(
    func=_run_compute_metrics,
    name="compute_metrics",
    description="Compute average, median, min, max, stdev and count for a stock over a date range. Omit dates for full series.",
    args_schema=ComputeMetricsInput,
)
