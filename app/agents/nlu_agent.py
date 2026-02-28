"""NLU: intent/entity extraction, clarification, suggested_worker."""
from __future__ import annotations

import json
import logging
import re
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

logger = logging.getLogger(__name__)
from app.models.llm import get_llm

import config
from app.utils.brvm_companies import (
    format_list_for_prompt,
    normalize_entities,
)

from app.agents.utils import get_time_prefix


def _nlu_system_prompt() -> str:
    brvm_list = format_list_for_prompt()
    return f"""BRVM stock assistant NLU. Output CLARIFY or JSON only. F CFA. {get_time_prefix()}

**CRITICAL:** Extract entities ONLY from the user message below. Do NOT reuse symbols from previous turns. Each question is independent.

**BRVM symbols only:**
{brvm_list}
Unknown symbol or other exchange → CLARIFY.

**Intents (exact):** market_overview | price_query | compare | chart | metrics | news | scrape | update_timeseries | brvm_basics | portfolio_display | portfolio_add | portfolio_remove | tracking_list | tracking_add | target_set | target_list | general

**Worker:** analytics (prices, compare, stats, overview) | charts (plot) | timeseries (CSV) | scraper (raw fetch) | news | portfolio

**Output:**
A) Unclear → CLARIFY: <short question>
B) Clear → {{"intent": "...", "entities": {{"symbol": "NTLC", ...}}, "suggested_worker": "analytics"}}"""


def _extract_user_text(messages: list) -> str:
    for m in reversed(messages):
        if isinstance(m, HumanMessage) and m.content:
            return str(m.content).strip()
    return ""


def _parse_nlu_response(content: str) -> tuple[dict[str, Any] | None, str | None]:
    text = (content or "").strip()
    # Clarification: line starting with CLARIFY:
    if text.upper().startswith("CLARIFY:"):
        clarification = text[8:].strip()
        if clarification:
            return None, clarification
    # Try to find JSON in the response (allow nested braces for "entities")
    def _make_structured(intent: str, entities: dict, worker: str) -> tuple[dict[str, Any], str | None]:
        # Resolve and validate symbols against BRVM list; ask for clarification if unknown
        entities, unknown = normalize_entities(entities)
        if unknown:
            return (
                None,
                f"Company or symbol not found on BRVM: {', '.join(unknown)}. Please use a symbol from the BRVM list (e.g. NTLC, SLBC, SNTS, Sonatel, Solibra, Nestlé).",
            )
        return {
            "intent": intent,
            "entities": entities,
            "suggested_worker": worker,
        }, None

    for candidate in (text.strip(), re.sub(r"^.*?(\{)", r"\1", text, count=1)):
        try:
            data = json.loads(candidate)
            if isinstance(data, dict) and "intent" in data:
                intent = data.get("intent") or "general"
                entities = data.get("entities") if isinstance(data.get("entities"), dict) else {}
                worker = data.get("suggested_worker") or "analytics"
                return _make_structured(intent, entities, worker)
        except json.JSONDecodeError:
            pass
    # Find first { and match balanced braces
    start = text.find("{")
    if start >= 0:
        depth = 0
        for i, c in enumerate(text[start:], start=start):
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    try:
                        data = json.loads(text[start : i + 1])
                        if isinstance(data, dict) and "intent" in data:
                            intent = data.get("intent") or "general"
                            entities = data.get("entities") if isinstance(data.get("entities"), dict) else {}
                            worker = data.get("suggested_worker") or "analytics"
                            return _make_structured(intent, entities, worker)
                    except json.JSONDecodeError:
                        pass
                    break
    # Fallback: treat as unclear
    return None, "Could you rephrase your question? For example: 'What is the price of NTLC?' or 'Plot SLBC from 2025-01-01 to 2025-02-21'."


def run_nlu_node(state: dict, model: str) -> dict:
    logger.info("[GRAPH] node=nlu start")
    messages = state.get("messages") or []
    user_text = _extract_user_text(messages)
    if not user_text:
        return {
            "messages": messages,
            "clarification": "What would you like to know about BRVM stocks?",
            "structured_data": None,
        }

    llm = get_llm(model=model)

    system = _nlu_system_prompt()
    prompt = f"User message: {user_text}"
    reply = llm.invoke(
        [
            SystemMessage(content=system),
            HumanMessage(content=prompt),
        ]
    )
    content = reply.content if hasattr(reply, "content") else str(reply)
    structured_data, clarification = _parse_nlu_response(content)

    if clarification:
        return {
            "messages": messages,
            "clarification": clarification,
            "structured_data": None,
        }

    summary = f"[NLU] intent={structured_data.get('intent')}, entities={structured_data.get('entities')}, suggested_worker={structured_data.get('suggested_worker')}"
    new_messages = list(messages) + [AIMessage(content=summary)]

    return {
        "messages": new_messages,
        "structured_data": structured_data,
        "clarification": None,
    }


def create_nlu_node(model: str):
    def node(state: dict) -> dict:
        return run_nlu_node(state, model)

    return node
