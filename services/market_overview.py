"""BRVM market overview: top stocks by volume, top gainers, top losers. Only BRVM-listed symbols."""
from __future__ import annotations

from typing import Any

from ._data import fetch_palmares
from .brvm_companies import get_valid_symbols, get_symbol_to_name


def _filter_brvm(stocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep only stocks whose symbol is in the official BRVM list."""
    valid = get_valid_symbols()
    return [s for s in stocks if (s.get("symbol") or "").strip().upper() in valid]


def get_brvm_market_overview(top_n: int = 10) -> dict[str, Any]:
    """
    Return BRVM market overview from palmarès: top stocks by volume, top gainers, top losers.
    Only includes symbols from the official BRVM list (data/brvm_companies.txt).
    """
    stocks = fetch_palmares(period="veille", progression="tout")
    brvm_only = _filter_brvm(stocks)
    symbol_to_name = get_symbol_to_name()

    def _enrich(s: dict[str, Any]) -> dict[str, Any]:
        sym = (s.get("symbol") or "").strip().upper()
        return {
            "symbol": sym,
            "company_name": symbol_to_name.get(sym) or s.get("name") or sym,
            "volume": s.get("volume"),
            "cours_actuel": s.get("cours_actuel"),
            "variation_pct": s.get("variation_pct"),
            "capitalisation": s.get("capitalisation"),
        }

    enriched = [_enrich(s) for s in brvm_only]

    # Top by volume (descending; None volume last)
    by_volume = sorted(
        enriched,
        key=lambda x: (x["volume"] is None, -(x["volume"] or 0)),
    )[:top_n]

    # Top gainers (variation_pct descending, positive first)
    gainers = sorted(
        [e for e in enriched if e.get("variation_pct") is not None and e["variation_pct"] > 0],
        key=lambda x: -(x["variation_pct"] or 0),
    )[:top_n]

    # Top losers (variation_pct ascending, negative first)
    losers = sorted(
        [e for e in enriched if e.get("variation_pct") is not None and e["variation_pct"] < 0],
        key=lambda x: (x["variation_pct"] or 0),
    )[:top_n]

    return {
        "source": "BRVM palmarès (Rich Bourse)",
        "top_by_volume": by_volume,
        "top_gainers": gainers,
        "top_losers": losers,
        "total_brvm_stocks": len(enriched),
    }
