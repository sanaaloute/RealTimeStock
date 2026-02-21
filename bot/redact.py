"""Redact agent output to plain text for Telegram: no markdown, no *, no tables; lists with '-'."""
from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama

import config

REDACT_SYSTEM = """You are a plain-text formatter for BRVM (Bourse Régionale des Valeurs Mobilières) market data. Rewrite the following text so it is suitable for a simple chat message.

Context: All amounts and prices are in F CFA (Franc CFA). Keep this currency when mentioning prices or values.

Rules:
- Output plain text only. No markdown.
- No asterisks (*) or other markdown symbols.
- No tables: convert table content into short lines or lists.
- For any list, use a dash and space (- ) at the start of each item.
- No code blocks, no backticks.
- Keep the same information and a clear structure. Be concise.
- Do not add greetings or extra commentary. Only output the rewritten text."""

REDACT_USER_TEMPLATE = """Rewrite as plain text:

{raw_output}"""


def redact_for_telegram(raw_output: str, model: str | None = None) -> str:
    """
    Use a dedicated LLM instance and prompt to convert agent output to plain text
    (no markdown, no *, no tables; lists with -). Returns the redacted string.
    """
    raw = (raw_output or "").strip()
    if not raw:
        return "No answer."

    kwargs = {"model": model or config.OLLAMA_MODEL, "temperature": 0}
    if config.OLLAMA_BASE_URL:
        kwargs["base_url"] = config.OLLAMA_BASE_URL
    llm = ChatOllama(**kwargs)
    messages = [
        SystemMessage(content=REDACT_SYSTEM),
        HumanMessage(content=REDACT_USER_TEMPLATE.format(raw_output=raw)),
    ]
    response = llm.invoke(messages)
    out = getattr(response, "content", None) or str(response)
    return (out or raw).strip()
