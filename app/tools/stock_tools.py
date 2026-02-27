"""LangChain tools for scrapers and services."""
from __future__ import annotations

import json
from typing import Any

from langchain_core.tools import StructuredTool

from app.scrapers import BRVMScraper, RichBourseScraper, RichBourseTimeseriesScraper, SikaFinanceScraper
from app.utils import compare_stocks, compute_metrics, get_stock_metrics, get_timeseries
from app.utils._data import (
    ensure_timeseries_up_to_date,
    list_series_status,
    run_daily_timeseries_update,
)
from app.utils.news import (
    get_brvm_official_announcements,
    get_company_news as get_company_news_svc,
    get_market_news as get_market_news_svc,
)
from app.utils.plots import plot_timeseries as plot_timeseries_service
from app.utils.market_overview import get_brvm_market_overview
from app.utils.brvm_basics import get_brvm_basics
from app.utils.brvm_companies import get_symbol_to_name, get_symbol_to_sector, get_valid_symbols

import config
from .schemas import (
    CompareStocksInput,
    GetCompanyInfoInput,
    ComputeMetricsInput,
    EnsureAllTimeseriesInput,
    EnsureTimeseriesInput,
    GetBrvmAnnouncementsInput,
    GetBrvmBasicsInput,
    GetCompanyNewsInput,
    GetMarketNewsInput,
    GetStockMetricsInput,
    GetTimeseriesInput,
    ListTimeseriesStatusInput,
    GetMarketOverviewInput,
    PlotCompanyChartInput,
    ScrapeBrvmInput,
    ScrapeRichbourseInput,
    ScrapeRichbourseTimeseriesInput,
    ScrapeSikafinanceInput,
)

SLEEP = config.SLEEP_SECONDS


def _scrape_sikafinance(period: str = "veille", **kwargs: Any) -> str:
    scraper = SikaFinanceScraper(period=period, sleep_seconds=SLEEP)
    data = scraper.scrape()
    return json.dumps(data, ensure_ascii=False, default=str)


def _scrape_richbourse(period: str = "veille", progression: str = "tout", **kwargs: Any) -> str:
    scraper = RichBourseScraper(period=period, progression=progression, sleep_seconds=SLEEP)
    data = scraper.scrape()
    return json.dumps(data, ensure_ascii=False, default=str)


def _scrape_richbourse_timeseries(symbol: str, **kwargs: Any) -> str:
    from pathlib import Path
    data_dir = Path(__file__).resolve().parent.parent / "data" / "series"
    scraper = RichBourseTimeseriesScraper(symbol=symbol, output_dir=str(data_dir), sleep_seconds=SLEEP)
    data = scraper.scrape()
    return json.dumps(data, ensure_ascii=False, default=str)


def _scrape_brvm(_: Any = None) -> str:
    scraper = BRVMScraper(sleep_seconds=SLEEP)
    data = scraper.scrape()
    return json.dumps(data, ensure_ascii=False, default=str)


def _get_stock_metrics(symbol: str, at_time: str | None = None, period: str = "veille", **kwargs: Any) -> str:
    data = get_stock_metrics(symbol, at_time=at_time, period=period)
    return json.dumps(data, ensure_ascii=False, default=str)


def _get_timeseries(symbol: str, start_date: str, end_date: str, **kwargs: Any) -> str:
    data = get_timeseries(symbol, start_date, end_date)
    return json.dumps(data, ensure_ascii=False, default=str)


def _compare_stocks(
    symbol_a: str,
    symbol_b: str,
    period: str = "veille",
    period_price_date: str | None = None,
    **kwargs: Any,
) -> str:
    data = compare_stocks(symbol_a, symbol_b, period=period, period_price_date=period_price_date)
    return json.dumps(data, ensure_ascii=False, default=str)


def _compute_metrics(
    symbol: str,
    start_date: str | None = None,
    end_date: str | None = None,
    **kwargs: Any,
) -> str:
    data = compute_metrics(symbol, start_date=start_date, end_date=end_date)
    return json.dumps(data, ensure_ascii=False, default=str)


def _ensure_timeseries(symbol: str, **kwargs: Any) -> str:
    data = ensure_timeseries_up_to_date(symbol)
    return json.dumps(data, ensure_ascii=False, default=str)


def _list_timeseries_status(symbols: str | None = None, **kwargs: Any) -> str:
    sym_list = [s.strip() for s in (symbols or "").split(",") if s.strip()] or None
    data = list_series_status(sym_list)
    return json.dumps(data, ensure_ascii=False, default=str)


def _ensure_all_timeseries(**kwargs: Any) -> str:
    data = run_daily_timeseries_update(config.TIMESERIES_SYMBOLS)
    return json.dumps(data, ensure_ascii=False, default=str)


def _get_company_news(symbol: str, limit: int = 10, **kwargs: Any) -> str:
    data = get_company_news_svc(symbol, limit=limit)
    return json.dumps(data, ensure_ascii=False, default=str)


def _get_market_news(limit: int = 15, **kwargs: Any) -> str:
    data = get_market_news_svc(limit=limit)
    return json.dumps(data, ensure_ascii=False, default=str)


def _get_brvm_announcements(limit: int = 15, company: str | None = None, **kwargs: Any) -> str:
    data = get_brvm_official_announcements(limit=limit, company=company)
    return json.dumps(data, ensure_ascii=False, default=str)


def _get_market_overview(top_n: int = 10, **kwargs: Any) -> str:
    data = get_brvm_market_overview(top_n=top_n)
    return json.dumps(data, ensure_ascii=False, default=str)


def _get_brvm_basics(**kwargs: Any) -> str:
    return get_brvm_basics()


def _get_company_info(symbol: str, **kwargs: Any) -> str:
    sym = (symbol or "").strip().upper()
    valid = get_valid_symbols()
    if sym not in valid:
        return json.dumps({"error": f"Unknown symbol: {symbol}. Use a valid BRVM symbol."}, ensure_ascii=False)
    name = get_symbol_to_name().get(sym, sym)
    sector = get_symbol_to_sector().get(sym, "")
    return json.dumps(
        {"symbol": sym, "company_name": name, "sector": sector or "Non spécifié"},
        ensure_ascii=False,
    )


def _plot_company_chart(
    symbol: str,
    start_date: str,
    end_date: str,
    chart_type: str = "line",
    **kwargs: Any,
) -> str:
    ct = "area" if (chart_type or "").strip().lower() == "area" else "line"
    data = plot_timeseries_service(symbol, start_date, end_date, chart_type=ct)
    if data.get("error") and not data.get("image_path"):
        return json.dumps(data, ensure_ascii=False, default=str)
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


scrape_sikafinance = StructuredTool.from_function(
    func=_scrape_sikafinance,
    name="scrape_sikafinance",
    description="Scrape Sika Finance palmarès (BRVM stocks: indices, gains, losses, volume). Returns JSON.",
    args_schema=ScrapeSikafinanceInput,
)

scrape_richbourse = StructuredTool.from_function(
    func=_scrape_richbourse,
    name="scrape_richbourse",
    description="Scrape Rich Bourse variation table (stocks with price, volume, variation %, capitalisation). Returns JSON.",
    args_schema=ScrapeRichbourseInput,
)

scrape_richbourse_timeseries = StructuredTool.from_function(
    func=_scrape_richbourse_timeseries,
    name="scrape_richbourse_timeseries",
    description="Fetch and save Rich Bourse time series for a stock symbol to data/series (CSV). Returns JSON with csv_path and row count.",
    args_schema=ScrapeRichbourseTimeseriesInput,
)

scrape_brvm = StructuredTool.from_function(
    func=_scrape_brvm,
    name="scrape_brvm",
    description="Scrape BRVM official site (indices and stocks). Returns JSON.",
    args_schema=ScrapeBrvmInput,
)

get_stock_metrics_tool = StructuredTool.from_function(
    func=_get_stock_metrics,
    name="get_stock_metrics",
    description="Get current or historical price, volume, growth %, loss % and capitalisation for a stock. Use at_time (YYYY-MM-DD) for historical price.",
    args_schema=GetStockMetricsInput,
)

get_timeseries_tool = StructuredTool.from_function(
    func=_get_timeseries,
    name="get_timeseries",
    description="Get time series (date, price) for a stock over a date range. Use for charts. Returns points list.",
    args_schema=GetTimeseriesInput,
)

compare_stocks_tool = StructuredTool.from_function(
    func=_compare_stocks,
    name="compare_stocks",
    description="Compare two stocks: price, volume, growth %, loss %, market cap. Optionally compare price at a given date (period_price_date).",
    args_schema=CompareStocksInput,
)

compute_metrics_tool = StructuredTool.from_function(
    func=_compute_metrics,
    name="compute_metrics",
    description="Compute average, median, min, max, stdev and count for a stock over a date range. Omit dates for full series.",
    args_schema=ComputeMetricsInput,
)

ensure_timeseries_tool = StructuredTool.from_function(
    func=_ensure_timeseries,
    name="ensure_timeseries",
    description="Check if company CSV exists and is up to date; fetch/refresh if missing or stale (older than 1 day).",
    args_schema=EnsureTimeseriesInput,
)

list_timeseries_status_tool = StructuredTool.from_function(
    func=_list_timeseries_status,
    name="list_timeseries_status",
    description="List status of company CSVs: path, last_date, up_to_date. Optionally pass comma-separated symbols.",
    args_schema=ListTimeseriesStatusInput,
)

ensure_all_timeseries_tool = StructuredTool.from_function(
    func=_ensure_all_timeseries,
    name="ensure_all_timeseries",
    description="Update CSVs for all configured target companies (daily job). Call once per day.",
    args_schema=EnsureAllTimeseriesInput,
)

plot_company_chart_tool = StructuredTool.from_function(
    func=_plot_company_chart,
    name="plot_company_chart",
    description="Plot price chart for a company over a date range. Uses most up-to-date CSV. Returns image_path (temp file) and summary. Chart types: line, area.",
    args_schema=PlotCompanyChartInput,
)

get_company_news_tool = StructuredTool.from_function(
    func=_get_company_news,
    name="get_company_news",
    description="Get latest news for a BRVM company from Rich Bourse (ground truth). Returns items with date, title, url, snippet. Use valid BRVM symbol or company name.",
    args_schema=GetCompanyNewsInput,
)

get_market_news_tool = StructuredTool.from_function(
    func=_get_market_news,
    name="get_market_news",
    description="Get BRVM market news from Sika Finance (ACTUALITES DE LA BOURSE). General finance news that can influence BRVM. No symbol required.",
    args_schema=GetMarketNewsInput,
)

get_brvm_announcements_tool = StructuredTool.from_function(
    func=_get_brvm_announcements,
    name="get_brvm_announcements",
    description="Get BRVM official announcements (convocations AGO, etc.) with PDF download links. Optionally filter by company symbol or name.",
    args_schema=GetBrvmAnnouncementsInput,
)

get_market_overview_tool = StructuredTool.from_function(
    func=_get_market_overview,
    name="get_market_overview",
    description="Get BRVM market overview: most traded stocks (top by volume), top gainers, top losers. Use this for questions like 'most traded stock', 'highest volume', 'top performers'. Returns only BRVM-listed symbols. All amounts in F CFA.",
    args_schema=GetMarketOverviewInput,
)

get_brvm_basics_tool = StructuredTool.from_function(
    func=_get_brvm_basics,
    name="get_brvm_basics",
    description="Get short text about BRVM (what it is, how to invest on BRVM). Use for questions like 'what is BRVM', 'how to invest in BRVM', 'how does the BRVM work'.",
    args_schema=GetBrvmBasicsInput,
)

get_company_info_tool = StructuredTool.from_function(
    func=_get_company_info,
    name="get_company_info",
    description="Get full company name and sector for a BRVM symbol. Use when you need to explain what a company does or its sector of activity.",
    args_schema=GetCompanyInfoInput,
)
