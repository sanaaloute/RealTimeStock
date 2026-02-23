"""LLM: ChatOllama for all agents and redact."""
from __future__ import annotations

from typing import Any

import config


def get_llm(
    model: str | None = None,
    temperature: float = 0,
    **kwargs: Any,
):
    """Return ChatOllama. Used by all agents and redact.
    Uses OLLAMA_KEEP_ALIVE to free GPU when model is idle (default 2m; use 0 to unload immediately)."""
    from langchain_ollama import ChatOllama
    llm_kwargs: dict[str, Any] = {
        "model": model or config.OLLAMA_MODEL,
        "temperature": temperature,
        "keep_alive": _parse_keep_alive(config.OLLAMA_KEEP_ALIVE),
        **kwargs,
    }
    if config.OLLAMA_BASE_URL:
        llm_kwargs["base_url"] = config.OLLAMA_BASE_URL
    return ChatOllama(**llm_kwargs)


def _parse_keep_alive(value: str) -> str | int:
    """Parse OLLAMA_KEEP_ALIVE: '0' or '0s' -> 0 (unload immediately); '2m', '5m' -> pass through."""
    v = (value or "").strip().lower()
    if v in ("0", "0s", "0m", "off"):
        return 0
    return value
