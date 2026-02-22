"""Pydantic schemas for agent tools (scrapers + services)."""
from pydantic import BaseModel, Field


# --- Scraper tools ---
class ScrapeSikafinanceInput(BaseModel):
    """Input for scraping Sika Finance palmarès."""

    period: str = Field(
        default="veille",
        description="Period: veille, une_semaine, un_mois, 3_mois, 6_mois, 1_an, etc.",
    )


class ScrapeRichbourseInput(BaseModel):
    """Input for scraping Rich Bourse variation/palmarès."""

    period: str = Field(
        default="veille",
        description="Period: veille, 1_semaine, 1_mois, 3_mois, 6_mois, 1_an, etc.",
    )
    progression: str = Field(
        default="tout",
        description="Filter: tout, hausse, baisse, constante, hausse_baisse",
    )


class ScrapeRichbourseTimeseriesInput(BaseModel):
    """Input for fetching and saving Rich Bourse time series for a symbol."""

    symbol: str = Field(description="Stock symbol (e.g. NTLC, SLBC).")


class ScrapeBrvmInput(BaseModel):
    """Input for scraping BRVM (no args)."""

    pass


# --- Service tools ---
class GetStockMetricsInput(BaseModel):
    """Input for getting current or historical price, volume, growth, loss."""

    symbol: str = Field(description="Stock symbol (e.g. NTLC).")
    at_time: str | None = Field(
        default=None,
        description="Optional date (YYYY-MM-DD) for historical price; omit for current.",
    )
    period: str = Field(default="veille", description="Palmarès period when at_time is omitted.")


class GetTimeseriesInput(BaseModel):
    """Input for getting time series (for charts) over a date range."""

    symbol: str = Field(description="Stock symbol.")
    start_date: str = Field(description="Start date YYYY-MM-DD.")
    end_date: str = Field(description="End date YYYY-MM-DD.")


class CompareStocksInput(BaseModel):
    """Input for comparing two stocks."""

    symbol_a: str = Field(description="First stock symbol.")
    symbol_b: str = Field(description="Second stock symbol.")
    period: str = Field(default="veille", description="Palmarès period.")
    period_price_date: str | None = Field(
        default=None,
        description="Optional date (YYYY-MM-DD) to compare price at that date.",
    )


class ComputeMetricsInput(BaseModel):
    """Input for computing average, median, min, max, stdev over a period."""

    symbol: str = Field(description="Stock symbol.")
    start_date: str | None = Field(default=None, description="Start date YYYY-MM-DD; omit for full series.")
    end_date: str | None = Field(default=None, description="End date YYYY-MM-DD; omit for full series.")


# --- Timeseries CSV updater ---
class EnsureTimeseriesInput(BaseModel):
    """Check and update CSV for one company (fetch if missing or stale)."""

    symbol: str = Field(description="Stock symbol (e.g. NTLC, SLBC).")


class ListTimeseriesStatusInput(BaseModel):
    """List status of all company CSVs (path, last_date, up_to_date). Optional symbols to check."""

    symbols: str | None = Field(
        default=None,
        description="Comma-separated symbols to check; omit to list all CSVs in data/series.",
    )


class EnsureAllTimeseriesInput(BaseModel):
    """Update CSVs for all configured target companies (daily job). No args."""

    pass


# --- Charts ---
class PlotCompanyChartInput(BaseModel):
    """Plot price chart for a company over a date range. Saves image to temp file; path returned."""

    symbol: str = Field(description="Stock symbol.")
    start_date: str = Field(description="Start date YYYY-MM-DD.")
    end_date: str = Field(description="End date YYYY-MM-DD.")
    chart_type: str = Field(
        default="line",
        description="Chart type: line or area.",
    )


# --- News (ground truth from Rich Bourse, Sika Finance, BRVM) ---
class GetCompanyNewsInput(BaseModel):
    """Get latest news for a BRVM company from Rich Bourse."""

    symbol: str = Field(description="Stock symbol or company name (e.g. PALC, Palm CI).")
    limit: int = Field(default=10, description="Max number of news items to return.")


class GetMarketNewsInput(BaseModel):
    """Get BRVM market news from Sika Finance (ACTUALITES DE LA BOURSE). No symbol required."""

    limit: int = Field(default=15, description="Max number of news items to return.")


class GetBrvmAnnouncementsInput(BaseModel):
    """Get BRVM official announcements (convocations AGO, PDFs). Optionally filter by company."""

    limit: int = Field(default=15, description="Max number of announcements to return.")
    company: str | None = Field(default=None, description="Optional: filter by symbol or company name.")
