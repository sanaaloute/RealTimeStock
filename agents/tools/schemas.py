"""Pydantic schemas for agent tools."""
from pydantic import BaseModel, Field


class ScrapeSikafinanceInput(BaseModel):
    period: str = Field(
        default="veille",
        description="Period: veille, une_semaine, un_mois, 3_mois, 6_mois, 1_an, etc.",
    )


class ScrapeRichbourseInput(BaseModel):
    period: str = Field(
        default="veille",
        description="Period: veille, 1_semaine, 1_mois, 3_mois, 6_mois, 1_an, etc.",
    )
    progression: str = Field(
        default="tout",
        description="Filter: tout, hausse, baisse, constante, hausse_baisse",
    )


class ScrapeRichbourseTimeseriesInput(BaseModel):
    symbol: str = Field(description="Stock symbol (e.g. NTLC, SLBC).")


class ScrapeBrvmInput(BaseModel):
    pass


class GetStockMetricsInput(BaseModel):
    symbol: str = Field(description="Stock symbol (e.g. NTLC).")
    at_time: str | None = Field(
        default=None,
        description="Optional date (YYYY-MM-DD) for historical price; omit for current.",
    )
    period: str = Field(default="veille", description="Palmarès period when at_time is omitted.")


class GetTimeseriesInput(BaseModel):
    symbol: str = Field(description="Stock symbol.")
    start_date: str = Field(description="Start date YYYY-MM-DD.")
    end_date: str = Field(description="End date YYYY-MM-DD.")


class CompareStocksInput(BaseModel):
    symbol_a: str = Field(description="First stock symbol.")
    symbol_b: str = Field(description="Second stock symbol.")
    period: str = Field(default="veille", description="Palmarès period.")
    period_price_date: str | None = Field(
        default=None,
        description="Optional date (YYYY-MM-DD) to compare price at that date.",
    )


class ComputeMetricsInput(BaseModel):
    symbol: str = Field(description="Stock symbol.")
    start_date: str | None = Field(default=None, description="Start date YYYY-MM-DD; omit for full series.")
    end_date: str | None = Field(default=None, description="End date YYYY-MM-DD; omit for full series.")


class EnsureTimeseriesInput(BaseModel):
    symbol: str = Field(description="Stock symbol (e.g. NTLC, SLBC).")


class ListTimeseriesStatusInput(BaseModel):
    symbols: str | None = Field(
        default=None,
        description="Comma-separated symbols to check; omit to list all CSVs in data/series.",
    )


class EnsureAllTimeseriesInput(BaseModel):
    pass


class PlotCompanyChartInput(BaseModel):
    symbol: str = Field(description="Stock symbol.")
    start_date: str = Field(description="Start date YYYY-MM-DD.")
    end_date: str = Field(description="End date YYYY-MM-DD.")
    chart_type: str = Field(
        default="line",
        description="Chart type: line or area.",
    )


class GetCompanyNewsInput(BaseModel):
    symbol: str = Field(description="Stock symbol or company name (e.g. PALC, Palm CI).")
    limit: int = Field(default=10, description="Max number of news items to return.")


class GetMarketNewsInput(BaseModel):
    limit: int = Field(default=15, description="Max number of news items to return.")


class GetBrvmAnnouncementsInput(BaseModel):
    limit: int = Field(default=15, description="Max number of announcements to return.")
    company: str | None = Field(default=None, description="Optional: filter by symbol or company name.")


class GetMarketOverviewInput(BaseModel):
    top_n: int = Field(default=10, description="Number of stocks to return per category (default 10).")


class GetBrvmBasicsInput(BaseModel):
    pass


class PortfolioAddInput(BaseModel):
    telegram_id: int = Field(description="User Telegram ID (from context).")
    symbol: str = Field(description="BRVM symbol (e.g. NTLC, SLBC).")
    buy_price: float = Field(description="Buy price in F CFA.")
    buy_date: str = Field(description="Buy date YYYY-MM-DD.")
    quantity: float = Field(default=1.0, description="Number of shares.")


class PortfolioRemoveInput(BaseModel):
    telegram_id: int = Field(description="User Telegram ID.")
    symbol: str = Field(description="BRVM symbol to remove.")


class GetPortfolioInput(BaseModel):
    telegram_id: int = Field(description="User Telegram ID.")


class GetPortfolioSummaryInput(BaseModel):
    telegram_id: int = Field(description="User Telegram ID.")


class TrackingAddInput(BaseModel):
    telegram_id: int = Field(description="User Telegram ID.")
    symbol: str = Field(description="BRVM symbol to track.")


class TrackingRemoveInput(BaseModel):
    telegram_id: int = Field(description="User Telegram ID.")
    symbol: str = Field(description="BRVM symbol to remove.")


class GetTrackingInput(BaseModel):
    telegram_id: int = Field(description="User Telegram ID.")


class TargetAddInput(BaseModel):
    telegram_id: int = Field(description="User Telegram ID.")
    symbol: str = Field(description="BRVM symbol.")
    target_price: float = Field(description="Target price in F CFA.")
    direction: str = Field(default="above", description="Notify when price goes 'above' or 'below' target.")


class TargetRemoveInput(BaseModel):
    telegram_id: int = Field(description="User Telegram ID.")
    symbol: str = Field(description="BRVM symbol.")


class GetTargetsInput(BaseModel):
    telegram_id: int = Field(description="User Telegram ID.")
