"""BRVM news: company news (Rich Bourse), market news (Sika Finance), official announcements (BRVM)."""
from __future__ import annotations

from typing import Any

from scrapers.brvm_announcements import fetch_brvm_announcements
from scrapers.richbourse_news import fetch_company_news
from scrapers.sikafinance_news import fetch_bourse_news

from services.brvm_companies import resolve_to_symbol


def get_company_news(symbol: str, limit: int = 15) -> dict[str, Any]:
    """
    Get latest news for a BRVM company from Rich Bourse. Symbol is resolved from brvm_companies list.
    Returns {source, symbol, items: [{date, title, url, snippet}], error?}.
    """
    resolved = resolve_to_symbol(symbol)
    sym = resolved or (symbol or "").strip().upper()
    out = fetch_company_news(sym, limit=limit)
    if not resolved and symbol and out.get("items"):
        out["resolved_symbol"] = sym
    if not out.get("items") and out.get("error") is None and not sym:
        out["error"] = "Unknown company. Use a valid BRVM symbol or company name."
    return out


def get_market_news(limit: int = 20) -> dict[str, Any]:
    """
    Get BRVM market news from Sika Finance (ACTUALITES DE LA BOURSE).
    Returns {source, url, items: [{date, title, url}], error?}.
    """
    return fetch_bourse_news(limit=limit)


def get_brvm_official_announcements(limit: int = 20, company: str | None = None) -> dict[str, Any]:
    """
    Get BRVM official announcements (convocations AGO, etc.) with PDF links.
    If company is set (symbol or name), filter to that company.
    """
    return fetch_brvm_announcements(limit=limit, company_filter=company)
