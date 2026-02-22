"""Load BRVM companies and symbols from data/brvm_companies.txt for NLU mapping (avoid hallucination)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

# Path relative to project root (where run_telegram_bot.py / run_agent.py are)
BRVM_COMPANIES_FILE = Path(__file__).resolve().parent.parent / "data" / "brvm_companies.txt"

_symbol_to_name: dict[str, str] = {}
_name_to_symbol: dict[str, str] = {}
_valid_symbols: set[str] = set()
_loaded = False


def _normalize(s: str) -> str:
    """Lowercase, strip, collapse spaces for lookup."""
    return " ".join((s or "").lower().strip().split())


def _load() -> None:
    global _symbol_to_name, _name_to_symbol, _valid_symbols, _loaded
    if _loaded:
        return
    _symbol_to_name = {}
    _name_to_symbol = {}
    _valid_symbols = set()
    if not BRVM_COMPANIES_FILE.exists():
        _loaded = True
        return
    with open(BRVM_COMPANIES_FILE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t", 1)
            if len(parts) < 2:
                continue
            symbol = parts[0].strip().upper()
            name_part = parts[1].strip()
            _valid_symbols.add(symbol)
            _symbol_to_name[symbol] = name_part
            # Map main name and symbol (as name) to symbol
            _name_to_symbol[_normalize(name_part)] = symbol
            _name_to_symbol[_normalize(symbol)] = symbol
            # Map first word or short names (e.g. "Nestlé", "Solibra")
            for word in name_part.replace(",", " ").replace("|", " ").split():
                w = word.strip()
                if len(w) >= 2 and w.upper() != symbol:
                    _name_to_symbol[_normalize(w)] = symbol
    _loaded = True


def get_valid_symbols() -> set[str]:
    """Return set of valid BRVM symbols."""
    _load()
    return set(_valid_symbols)


def get_symbol_to_name() -> dict[str, str]:
    """Return mapping symbol -> company name."""
    _load()
    return dict(_symbol_to_name)


def get_name_to_symbol() -> dict[str, str]:
    """Return mapping normalized name -> symbol."""
    _load()
    return dict(_name_to_symbol)


def resolve_to_symbol(mention: str) -> str | None:
    """
    Resolve user mention (symbol or company name) to official symbol.
    Returns symbol if found, None if unknown (caller can ask for clarification).
    """
    _load()
    mention = (mention or "").strip()
    if not mention:
        return None
    upper = mention.upper()
    if upper in _valid_symbols:
        return upper
    by_name = _name_to_symbol.get(_normalize(mention))
    if by_name:
        return by_name
    return None


def format_list_for_prompt() -> str:
    """Format the BRVM list for inclusion in NLU system prompt (symbol -> name, one per line)."""
    _load()
    if not _symbol_to_name:
        return "No BRVM company list loaded."
    lines = [f"- {sym}: {name}" for sym, name in sorted(_symbol_to_name.items())]
    return "\n".join(lines)


def normalize_entities(entities: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """
    Resolve symbol, symbol_a, symbol_b from entities using the BRVM list.
    Returns (updated_entities, list of unknown mentions to report).
    """
    _load()
    out = dict(entities)
    unknown: list[str] = []
    for key in ("symbol", "symbol_a", "symbol_b"):
        val = out.get(key)
        if not val or not isinstance(val, str):
            continue
        resolved = resolve_to_symbol(val)
        if resolved:
            out[key] = resolved
        else:
            unknown.append(val)
    return out, unknown
