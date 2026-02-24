"""ChatOllama for agents. Local Ollama or Ollama Cloud (OLLAMA_CLOUD=true)."""
from __future__ import annotations

from typing import Any

import config


def get_llm(model: str | None = None, temperature: float = 0, **kwargs: Any):
    from langchain_ollama import ChatOllama

    model_name = model or config.OLLAMA_MODEL
    base_url = config.OLLAMA_BASE_URL
    headers: dict[str, str] | None = None

    if config.OLLAMA_CLOUD:
        if not config.OLLAMA_API_KEY:
            raise ValueError(
                "OLLAMA_API_KEY is required when OLLAMA_CLOUD=true. "
                "Create one at https://ollama.com/settings/keys"
            )
        base_url = config.OLLAMA_CLOUD_HOST
        headers = {"Authorization": f"Bearer {config.OLLAMA_API_KEY}"}
        if not model:
            model_name = config.OLLAMA_CLOUD_MODEL

    llm_kwargs: dict[str, Any] = {
        "model": model_name,
        "temperature": temperature,
        "keep_alive": _parse_keep_alive(config.OLLAMA_KEEP_ALIVE),
        **kwargs,
    }
    if base_url:
        llm_kwargs["base_url"] = base_url
    if headers:
        llm_kwargs["headers"] = headers
    return ChatOllama(**llm_kwargs)


def _parse_keep_alive(value: str) -> str | int:
    v = (value or "").strip().lower()
    if v in ("0", "0s", "0m", "off"):
        return 0
    return value
