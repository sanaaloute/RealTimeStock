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


def _nlu_system_prompt() -> str:
    """Build NLU system prompt including the BRVM company list to avoid hallucination."""
    brvm_list = format_list_for_prompt()
    return f"""You are a natural language understanding (NLU) module for the BRVM stock market (Bourse Régionale des Valeurs Mobilières, West Africa). All amounts are in F CFA.

**IMPORTANT – Only use BRVM companies from this list (symbol or company name). If the user mentions a company not in the list, treat it as unclear and ask for clarification.**
Valid BRVM companies (symbol: company name):
{brvm_list}

Your job is to:
1. Understand the user's intention.
2. If the message is ambiguous, missing key information, mentions a company/symbol NOT in the list above, or is not about BRVM/stocks, respond with a short clarification question.
3. If the intention is clear and all companies are in the list, extract structured data and suggest which worker should handle it. Use the official SYMBOL (e.g. NTLC, SLBC) in entities when the user says a company name (e.g. Nestlé -> NTLC, Solibra -> SLBC).

**Intents you can recognize:**
- price_query: current or historical price of one stock (needs: symbol; optional: date)
- compare: compare two stocks (needs: symbol_a, symbol_b; optional: period, date)
- chart: plot/graph of a stock's price over a period (needs: symbol, start_date, end_date; optional: chart_type=line|area)
- update_timeseries: refresh or check company CSV data (optional: symbol or "all")
- scrape: fetch raw data from websites (palmarès, variation, BRVM)
- metrics: stats over a period (average, median, min, max; needs: symbol; optional: start_date, end_date)
- news: latest news about a BRVM company or BRVM market (actualités, announcements). Optional: symbol for company-specific news.
- general: other BRVM-related question (no specific params)

**Entities to extract when relevant:** symbol, symbol_a, symbol_b (use official symbol from the list), start_date, end_date, period, chart_type, date (YYYY-MM-DD). Use today's date when the user says "today" or "now". Infer reasonable date ranges for "last week", "last month", "this year".

**Output format (choose one):**

A) If the user intent is UNCLEAR or key information is missing or a company is not in the BRVM list, reply with exactly:
CLARIFY: <your short question in the same language as the user, asking for the missing detail or suggesting they choose a company from the BRVM list>

B) If the intent is clear and all companies are in the list, reply with a single JSON object, no other text:
{{"intent": "<intent>", "entities": {{"symbol": "<SYMBOL>", "start_date": "...", ...}}, "suggested_worker": "<analytics|scraper|charts|timeseries|news>"}}

Suggested worker mapping: price_query/compare/metrics/general -> analytics; chart -> charts; update_timeseries -> timeseries; scrape -> scraper; news -> news.

Reply only with either CLARIFY: ... or the JSON object."""


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
