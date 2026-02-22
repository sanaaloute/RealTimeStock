"""NLU worker: understand user intent, extract structured data, or ask for clarification."""
from __future__ import annotations

import json
import re
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_ollama import ChatOllama

import config
from services.brvm_companies import (
    format_list_for_prompt,
    normalize_entities,
)

from agents.utils import get_time_prefix


def _nlu_system_prompt() -> str:
    """Build NLU system prompt including the BRVM company list to avoid hallucination."""
    brvm_list = format_list_for_prompt()
    return f"""You are the NLU (natural language understanding) module for the BRVM stock assistant (Bourse Régionale des Valeurs Mobilières). This assistant covers only BRVM—not other stock exchanges (NYSE, NASDAQ, other African bourses). All amounts are in F CFA. You output either a clarification question or a single JSON object—nothing else.

**{get_time_prefix()}** — Use this date/time when the user says "today", "now", or relative expressions ("last week", "this month"). Resolve relative dates to YYYY-MM-DD.

**Strict rule:** Only recognize companies/symbols from this list. If the user names a company or symbol NOT in the list, output CLARIFY asking them to choose from the BRVM list. If the user asks about another stock market (e.g. "Wall Street", "Nigeria stock exchange"), output CLARIFY: "This assistant only covers the BRVM (West African regional exchange)."
Valid BRVM companies (symbol: company name):
{brvm_list}

**Intents (use exactly these strings):**
- market_overview: most traded stock, highest volume, top performers, top gainers, top losers, market summary. No required entities (analytics worker will use market overview tool).
- price_query: current or historical price of one stock. Requires: symbol.
- compare: compare two stocks. Requires: symbol_a, symbol_b. Optional: period, start_date, end_date.
- chart: plot/graph of a stock's price over a period. Requires: symbol. Optional: start_date, end_date, chart_type (line|area). Infer dates if user says "last week" etc.
- update_timeseries: check or refresh company CSV data. Optional: symbol (or "all" for all symbols).
- scrape: fetch raw data from BRVM websites (palmarès, variation, time series CSV, BRVM site). No required entities.
- metrics: statistics over a period (average, median, min, max). Requires: symbol. Optional: start_date, end_date.
- news: latest news/actualités/announcements about a BRVM company or the market. Optional: symbol.
- brvm_basics: what is BRVM, how to invest on BRVM, how does BRVM work. No required entities.
- general: other BRVM-related question; no specific params.

**Entities:** symbol, symbol_a, symbol_b must be the official SYMBOL from the list (e.g. Nestlé → NTLC, Solibra → SLBC). Dates in YYYY-MM-DD. period: e.g. "1W", "1M", "1Y". chart_type: "line" or "area".

**Output (exactly one of the two):**

A) Unclear / missing info / company not in list / user asks about another exchange → one line:
CLARIFY: <Short question in the user's language. Ask for the missing detail or say we only cover BRVM.>

B) Clear intent, all companies in list (if any) → single JSON, no other text:
{{"intent": "<intent>", "entities": {{"symbol": "<SYMBOL>", ...}}, "suggested_worker": "<analytics|scraper|charts|timeseries|news>"}}

**Worker mapping:** market_overview, price_query, compare, metrics, brvm_basics, general → analytics. chart → charts. update_timeseries → timeseries. scrape → scraper. news → news.

Reply only with CLARIFY: ... or the JSON object."""


def _extract_user_text(messages: list) -> str:
    """Last human message content."""
    for m in reversed(messages):
        if isinstance(m, HumanMessage) and m.content:
            return str(m.content).strip()
    return ""


def _parse_nlu_response(content: str) -> tuple[dict[str, Any] | None, str | None]:
    """
    Parse LLM response. Returns (structured_data, clarification).
    One of them is set; the other is None.
    """
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
    """
    NLU node: read last user message, call LLM, return state with either
    clarification (and route to end) or structured_data + summary message (and route to supervisor).
    """
    messages = state.get("messages") or []
    user_text = _extract_user_text(messages)
    if not user_text:
        return {
            "messages": messages,
            "clarification": "What would you like to know about BRVM stocks?",
            "structured_data": None,
        }

    kwargs = {"model": model, "temperature": 0}
    if config.OLLAMA_BASE_URL:
        kwargs["base_url"] = config.OLLAMA_BASE_URL
    llm = ChatOllama(**kwargs)

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

    # Append a short summary so the supervisor sees the extracted structure
    summary = f"[NLU] intent={structured_data.get('intent')}, entities={structured_data.get('entities')}, suggested_worker={structured_data.get('suggested_worker')}"
    new_messages = list(messages) + [AIMessage(content=summary)]

    return {
        "messages": new_messages,
        "structured_data": structured_data,
        "clarification": None,
    }


def create_nlu_node(model: str):
    """Build the NLU graph node (function that takes state, returns state update)."""

    def node(state: dict) -> dict:
        return run_nlu_node(state, model)

    return node
