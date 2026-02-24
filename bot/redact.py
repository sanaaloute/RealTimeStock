"""Redact agent output to plain text for Telegram."""
from __future__ import annotations

import re

from langchain_core.messages import HumanMessage, SystemMessage
from agents.llm import get_llm

# Drop lines that mention file paths or tool usage (internal details)
_PATH_LINE = re.compile(
    r"/tmp/|/var/|chart_.*\.png|image_path|saved at .*\.(png|jpg)|stored at|image at\s|Send image at",
    re.IGNORECASE,
)
_TOOL_LINE = re.compile(
    r"plot_company_chart|get_timeseries|scrape_sikafinance|scrape_richbourse|scrape_brvm|get_stock_metrics|compare_stocks|compute_metrics|ensure_timeseries|list_timeseries_status|I used (?:the )?\w+ (?:tool|function)|called \w+ tool",
    re.IGNORECASE,
)

REDACT_SYSTEM = """You are a plain-text formatter for BRVM (Bourse Régionale des Valeurs Mobilières) market data. Rewrite the following text so it is suitable for a simple chat message.

Context: All amounts and prices are in F CFA (Franc CFA). Keep this currency when mentioning prices or values.

Rules:
- Output plain text only. No markdown.
- No asterisks (*) or other markdown symbols.
- No tables: convert table content into short lines or lists.
- For any list, use a dash and space (- ) at the start of each item.
- No code blocks, no backticks.
- Keep the same information and a clear structure. Be concise.
- Do not add greetings or extra commentary. Only output the rewritten text.
- Remove entirely: any file paths (e.g. /tmp/..., C:\\..., chart_xxx.png), any mention of where an image is stored or saved, and any mention of tools or functions used (e.g. plot_company_chart, get_timeseries, scrape_sikafinance, get_stock_metrics, or "I used the ... tool"). The user must not see internal details about storage or tools."""

REDACT_USER_TEMPLATE = """Rewrite the following text as a simple chat message. Keep the same information and a clear structure. Be concise. Plain text only.

Rewrite as plain text:
{raw_output}
"""


def _strip_internal_refs(text: str) -> str:
    lines = text.split("\n")
    out = [ln for ln in lines if not _PATH_LINE.search(ln) and not _TOOL_LINE.search(ln)]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip()


def _to_plain_text(text: str) -> str:
    if not text:
        return text
    return re.sub(r"\*\*([^*]*)\*\*", r"\1", text).replace("**", "")


def redact_for_telegram(raw_output: str, model: str | None = None) -> str:
    raw = (raw_output or "").strip()
    if not raw:
        return "No answer."

    llm = get_llm(model=model, temperature=0)
    messages = [
        SystemMessage(content=REDACT_SYSTEM),
        HumanMessage(content=REDACT_USER_TEMPLATE.format(raw_output=raw)),
    ]
    response = llm.invoke(messages)
    out = getattr(response, "content", None) or str(response)
    out = (out or raw).strip()
    out = _strip_internal_refs(out) or out
    return _to_plain_text(out)
