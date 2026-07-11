"""TTL cache for market data (palmarès) with stale-if-error fallback.

Market pages are scraped live over HTTP. Without a cache, every user query,
portfolio valuation and alert check re-scrapes the same page — slow, costly,
and ban-prone. This cache keeps results in memory (fast path) and on disk
(survives restarts), and serves the last known good value when a refresh
fails so the bot keeps answering instead of returning empty data.
"""
from __future__ import annotations

import json
import logging
import threading
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_CACHE_DIR = Path(__file__).resolve().parent.parent / "data"


class MarketDataCache:
    """In-memory TTL cache persisted to disk; can serve stale data on failure."""

    def __init__(self, ttl_seconds: float = 300.0, persist_path: Path | None = None):
        self.ttl = float(ttl_seconds)
        self._path = persist_path
        self._lock = threading.Lock()
        self._store: dict[str, tuple[float, Any]] = {}
        if persist_path is not None:
            self._load_disk()

    def _load_disk(self) -> None:
        try:
            if self._path and self._path.exists():
                raw = json.loads(self._path.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    for k, v in raw.items():
                        if isinstance(v, dict) and "ts" in v:
                            self._store[k] = (float(v["ts"]), v.get("value"))
        except Exception as e:
            logger.warning("Could not load market cache from disk: %s", e)

    def _save_disk(self) -> None:
        if self._path is None:
            return
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            raw = {k: {"ts": ts, "value": val} for k, (ts, val) in self._store.items()}
            tmp = self._path.with_suffix(self._path.suffix + ".tmp")
            tmp.write_text(json.dumps(raw, ensure_ascii=False, default=str), encoding="utf-8")
            tmp.replace(self._path)
        except Exception as e:
            logger.warning("Could not persist market cache: %s", e)

    def get(self, key: str) -> Any | None:
        """Return cached value if present and younger than TTL, else None."""
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            ts, value = entry
            if time.time() - ts > self.ttl:
                return None
            return value

    def get_stale(self, key: str) -> Any | None:
        """Return cached value regardless of age (fallback when refresh fails)."""
        with self._lock:
            entry = self._store.get(key)
            return entry[1] if entry is not None else None

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            self._store[key] = (time.time(), value)
            self._save_disk()


PALMARES_CACHE_PATH = _CACHE_DIR / "palmares_cache.json"

# Process-wide singleton (created lazily so config is loaded first).
_palmares_cache: MarketDataCache | None = None


def get_palmares_cache() -> MarketDataCache:
    """Process-wide palmarès cache, TTL from config.PALMARES_CACHE_TTL_SECONDS."""
    global _palmares_cache
    if _palmares_cache is None:
        import config

        ttl = getattr(config, "PALMARES_CACHE_TTL_SECONDS", 300.0)
        _palmares_cache = MarketDataCache(ttl_seconds=ttl, persist_path=PALMARES_CACHE_PATH)
    return _palmares_cache
