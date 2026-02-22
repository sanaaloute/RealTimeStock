"""LangChain tools wrapping scrapers and services."""
from __future__ import annotations

import json
from typing import Any

from langchain_core.tools import StructuredTool

from scrapers import BRVMScraper, RichBourseScraper, RichBourseTimeseriesScraper, SikaFinanceScraper
from services import compare_stocks, compute_metrics, get_stock_metrics, get_timeseries
from services._data import (
    ensure_timeseries_up_to_date,
    list_series_status,
    run_daily_timeseries_update,
)
from services.news import (
    get_brvm_official_announcements,
    get_company_news as get_company_news_svc,
    get_market_news as get_market_news_svc,
)
from services.plots import plot_timeseries as plot_timeseries_service

import config
from .schemas import (
    CompareStocksInput,
    ComputeMetricsInput,
    EnsureAllTimeseriesInput,
    EnsureTimeseriesInput,
    GetBrvmAnnouncementsInput,
    GetCompanyNewsInput,
    GetMarketNewsInput,
    GetStockMetricsInput,
    GetTimeseriesInput,
    ListTimeseriesStatusInput,
    PlotCompanyChartInput,
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


def _ensure_timeseries(symbol: str) -> str:
    data = ensure_timeseries_up_to_date(symbol)
    return json.dumps(data, ensure_ascii=False, default=str)


def _list_timeseries_status(symbols: str | None = None) -> str:
    sym_list = [s.strip() for s in (symbols or "").split(",") if s.strip()] or None
    data = list_series_status(sym_list)
    return json.dumps(data, ensure_ascii=False, default=str)


def _ensure_all_timeseries() -> str:
    data = run_daily_timeseries_update(config.TIMESERIES_SYMBOLS)
    return json.dumps(data, ensure_ascii=False, default=str)


def _get_company_news(symbol: str, limit: int = 10) -> str:
    data = get_company_news_svc(symbol, limit=limit)
    return json.dumps(data, ensure_ascii=False, default=str)


def _get_market_news(limit: int = 15) -> str:
    data = get_market_news_svc(limit=limit)
    return json.dumps(data, ensure_ascii=False, default=str)


def _get_brvm_announcements(limit: int = 15, company: str | None = None) -> str:
    data = get_brvm_official_announcements(limit=limit, company=company)
    return json.dumps(data, ensure_ascii=False, default=str)


def _plot_company_chart(
    symbol: str,
    start_date: str,
    end_date: str,
    chart_type: str = "line",
) -> str:
    ct = "area" if (chart_type or "").strip().lower() == "area" else "line"
    data = plot_timeseries_service(symbol, start_date, end_date, chart_type=ct)
    if data.get("error") and not data.get("image_path"):
        return json.dumps(data, ensure_ascii=False, default=str)
    # Return path so supervisor/bot can send image; include summary for the agent
    return json.dumps(
        {
            "image_path": data.get("image_path"),
            "symbol": data.get("symbol"),
            "start_date": data.get("start_date"),
            "end_date": data.get("end_date"),
            "points_count": data.get("points_count"),
            "message": f"Chart saved. Send image at {data.get('image_path')} with your explanation.",
        },
        ensure_ascii=False,
        default=str,
    )


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


def _run_ensure_timeseries(symbol: str, **kwargs: Any) -> str:
    return _ensure_timeseries(symbol)


def _run_list_timeseries_status(symbols: str | None = None, **kwargs: Any) -> str:
    return _list_timeseries_status(symbols)


def _run_ensure_all_timeseries(**kwargs: Any) -> str:
    return _ensure_all_timeseries()


def _run_plot_company_chart(
    symbol: str,
    start_date: str,
    end_date: str,
    chart_type: str = "line",
    **kwargs: Any,
) -> str:
    return _plot_company_chart(symbol, start_date, end_date, chart_type)


def _run_get_company_news(symbol: str, limit: int = 10, **kwargs: Any) -> str:
    return _get_company_news(symbol, limit)


def _run_get_market_news(limit: int = 15, **kwargs: Any) -> str:
    return _get_market_news(limit)


def _run_get_brvm_announcements(limit: int = 15, company: str | None = None, **kwargs: Any) -> str:
    return _get_brvm_announcements(limit, company)


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

ensure_timeseries_tool = StructuredTool.from_function(
    func=_run_ensure_timeseries,
    name="ensure_timeseries",
    description="Check if company CSV exists and is up to date; fetch/refresh if missing or stale (older than 1 day).",
    args_schema=EnsureTimeseriesInput,
)

list_timeseries_status_tool = StructuredTool.from_function(
    func=_run_list_timeseries_status,
    name="list_timeseries_status",
    description="List status of company CSVs: path, last_date, up_to_date. Optionally pass comma-separated symbols.",
    args_schema=ListTimeseriesStatusInput,
)

ensure_all_timeseries_tool = StructuredTool.from_function(
    func=_run_ensure_all_timeseries,
    name="ensure_all_timeseries",
    description="Update CSVs for all configured target companies (daily job). Call once per day.",
    args_schema=EnsureAllTimeseriesInput,
)

plot_company_chart_tool = StructuredTool.from_function(
    func=_run_plot_company_chart,
    name="plot_company_chart",
    description="Plot price chart for a company over a date range. Uses most up-to-date CSV. Returns image_path (temp file) and summary. Chart types: line, area.",
    args_schema=PlotCompanyChartInput,
)

get_company_news_tool = StructuredTool.from_function(
    func=_run_get_company_news,
    name="get_company_news",
    description="Get latest news for a BRVM company from Rich Bourse (ground truth). Returns items with date, title, url, snippet. Use valid BRVM symbol or company name.",
    args_schema=GetCompanyNewsInput,
)

get_market_news_tool = StructuredTool.from_function(
    func=_run_get_market_news,
    name="get_market_news",
    description="Get BRVM market news from Sika Finance (ACTUALITES DE LA BOURSE). General finance news that can influence BRVM. No symbol required.",
    args_schema=GetMarketNewsInput,
)

get_brvm_announcements_tool = StructuredTool.from_function(
    func=_run_get_brvm_announcements,
    name="get_brvm_announcements",
    description="Get BRVM official announcements (convocations AGO, etc.) with PDF download links. Optionally filter by company symbol or name.",
    args_schema=GetBrvmAnnouncementsInput,
)
