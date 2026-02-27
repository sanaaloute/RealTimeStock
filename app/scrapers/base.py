"""Base scraper using Tavily API with configurable sleep."""
import time
import logging
from abc import ABC, abstractmethod
from typing import Any

from tavily import TavilyClient

import config

logger = logging.getLogger(__name__)


class BaseScraper(ABC):
    """Base class for stock market scrapers using Tavily extract + sleep."""

    def __init__(
        self,
        api_key: str | None = None,
        sleep_seconds: float | None = None,
    ):
        self._api_key = api_key or config.TAVILY_API_KEY
        self._sleep_seconds = sleep_seconds if sleep_seconds is not None else config.SLEEP_SECONDS
        self._client: TavilyClient | None = None

    @property
    def client(self) -> TavilyClient:
        if self._client is None:
            if not self._api_key:
                raise ValueError("TAVILY_API_KEY is not set. Set it in .env or pass api_key=.")
            self._client = TavilyClient(api_key=self._api_key)
        return self._client

    @property
    def url(self) -> str:
        """Override in subclasses."""
        return ""

    def _sleep(self) -> None:
        """Apply configured delay between requests."""
        if self._sleep_seconds > 0:
            logger.debug("Sleeping %.1f s", self._sleep_seconds)
            time.sleep(self._sleep_seconds)

    def fetch_raw(self) -> dict[str, Any]:
        """Fetch page content via Tavily extract. Call _sleep before/after as needed."""
        self._sleep()
        try:
            response = self.client.extract([self.url])
            self._sleep()
            return response
        except Exception as e:
            logger.exception("Tavily extract failed for %s: %s", self.url, e)
            raise

    def extract_content(self) -> str:
        """Get raw text content from Tavily response (results[].raw_content or content).
        Replaces \\xa0 (non-breaking space) with empty string for clean parsing and JSON output.
        """
        raw = self.fetch_raw()
        if not isinstance(raw, dict):
            return str(raw).strip().replace("\xa0", "")
        results = raw.get("results", [])
        if isinstance(results, list) and results:
            first = results[0]
            if isinstance(first, dict):
                content = (first.get("raw_content") or first.get("content") or "").strip()
                return content.replace("\xa0", "")
        return ""

    @abstractmethod
    def scrape(self) -> dict[str, Any]:
        """Fetch and parse stock data. Return structured dict."""
        ...
