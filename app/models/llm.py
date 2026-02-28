"""Unified LLM factory. Supports Ollama, Groq, OpenRouter via LLM_PROVIDER env."""
from __future__ import annotations

from typing import Any

import config


def get_default_model() -> str:
    """Return default model for current LLM_PROVIDER."""
    if config.LLM_MODEL:
        return config.LLM_MODEL
    provider = (config.LLM_PROVIDER or "ollama").strip().lower()
    if provider == "ollama":
        return config.OLLAMA_MODEL
    if provider == "groq":
        return config.GROQ_MODEL
    if provider == "openrouter":
        return config.OPENROUTER_MODEL
    return config.OLLAMA_MODEL


def get_llm(model: str | None = None, temperature: float | None = None, **kwargs: Any):
    """
    Return LLM instance based on LLM_PROVIDER (ollama, groq, openrouter).
    Model can be overridden per-call; otherwise uses LLM_MODEL or provider-specific default.
    Temperature defaults to config.LLM_TEMPERATURE (0.5).
    """
    if temperature is None:
        temperature = config.LLM_TEMPERATURE
    provider = (config.LLM_PROVIDER or "ollama").strip().lower()
    # Use explicit model arg, then LLM_MODEL env, else provider default
    effective_model = model or config.LLM_MODEL or (
        config.OLLAMA_MODEL if provider == "ollama" else
        config.GROQ_MODEL if provider == "groq" else
        config.OPENROUTER_MODEL
    )

    if provider == "ollama":
        return _ollama(effective_model, temperature, **kwargs)
    if provider == "groq":
        return _groq(effective_model, temperature, **kwargs)
    if provider == "openrouter":
        return _openrouter(effective_model, temperature, **kwargs)

    raise ValueError(
        f"Unknown LLM_PROVIDER: {config.LLM_PROVIDER}. "
        "Use: ollama, groq, or openrouter"
    )


def _ollama(model: str | None, temperature: float, **kwargs: Any):
    from .provider_ollama import create_ollama_llm
    return create_ollama_llm(model=model, temperature=temperature, **kwargs)


def _groq(model: str | None, temperature: float, **kwargs: Any):
    from .provider_groq import create_groq_llm
    return create_groq_llm(model=model, temperature=temperature, **kwargs)


def _openrouter(model: str | None, temperature: float, **kwargs: Any):
    from .provider_openrouter import create_openrouter_llm
    return create_openrouter_llm(model=model, temperature=temperature, **kwargs)
