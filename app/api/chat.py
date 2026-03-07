"""FastAPI chat endpoint. Bot calls this; API runs agents and returns sanitized response."""
from __future__ import annotations

import asyncio
import base64
import logging
import sqlite3
from pathlib import Path

from contextlib import asynccontextmanager
from fastapi import APIRouter, FastAPI
from langchain_core.messages import AIMessage, ToolMessage
from pydantic import BaseModel

import config
from app.agents import run_agent
from app.agents.graph import CHAT_MEMORY_DB
from app.bot.redact import redact_for_telegram

logger = logging.getLogger(__name__)

router = APIRouter()

# Self-destruction: wipe all chat memory every 15 minutes
MEMORY_WIPE_INTERVAL_SEC = 15 * 60

# Tool names that fetch data from each source (for footer)
TOOLS_BY_SOURCE = {
    "Rich Bourse": {
        "get_company_news",
        "get_richbourse_prediction",
        "get_richbourse_dividends",
        "get_all_trends",
        "get_trends_by_option",
        "get_stock_prediction_detail",
        "scrape_richbourse",
        "scrape_richbourse_timeseries",
    },
    "Sika Finance": {
        "get_sikafinance_actualites",
        "get_sikafinance_communiques",
        "get_market_news",
        "scrape_sikafinance",
    },
    "BRVM": {
        "get_brvm_announcements",
        "scrape_brvm",
    },
}

SOURCE_FOOTER = "\n\nAttention : AI generated, be careful."


def _get_sources_from_messages(messages: list) -> set[str]:
    """Collect source labels (Rich Bourse, Sika Finance, BRVM) from tool calls in this turn."""
    tool_names: set[str] = set()
    for m in messages:
        if isinstance(m, ToolMessage) and getattr(m, "name", None):
            tool_names.add(str(m.name))
        if isinstance(m, AIMessage) and getattr(m, "tool_calls", None):
            for tc in m.tool_calls:
                name = tc.get("name") if isinstance(tc, dict) else getattr(tc, "name", None)
                if name:
                    tool_names.add(str(name))
    sources: set[str] = set()
    for source_label, tools in TOOLS_BY_SOURCE.items():
        if tool_names & tools:
            sources.add(source_label)
    return sources


def _format_source_footer(sources: set[str]) -> str:
    if not sources:
        return ""
    parts = sorted(sources)
    return f"\n\nSource(s): {', '.join(parts)}."


def _format_final_footer(sources: set[str]) -> str:
    """Always add AI disclaimer at the bottom; optionally add source line before it."""
    source_line = _format_source_footer(sources)
    return source_line + SOURCE_FOOTER


def _extract_reply(messages: list) -> str:
    for m in reversed(messages):
        if not getattr(m, "content", None):
            continue
        content = str(m.content).strip()
        if "[NLU]" in content:
            continue
        kind = getattr(m, "type", None) or type(m).__name__
        if kind == "ai" or "AI" in str(kind):
            return content
    for m in reversed(messages):
        if getattr(m, "content", None) and "Human" not in type(m).__name__:
            content = str(m.content).strip()
            if "[NLU]" not in content:
                return content
    return "No answer from the agent."


def _user_friendly_error(exc: Exception) -> str:
    err_str = str(exc).lower()
    if "recursion" in err_str:
        return "The question was too complex. Try a simpler question."
    if "404" in err_str:
        return "Model not found. Pull it first: ollama pull <model>"
    if "503" in err_str:
        return "Ollama is busy or still loading the model. Wait a few seconds and try again."
    if "ssl" in err_str or "eof" in err_str or "connect" in err_str:
        return "The AI service is temporarily unavailable. Check that Ollama is running and try again."
    if "timeout" in err_str:
        return "The request took too long. Try again."
    return "Something went wrong. Please try again."


class ChatRequest(BaseModel):
    query: str
    thread_id: str = "default"
    telegram_user_id: int | None = None


class ChatResponse(BaseModel):
    reply: str
    image_base64: str | None = None
    clarification: bool = False


class ChatError(BaseModel):
    error: str


class ClearMemoryRequest(BaseModel):
    thread_id: str = "default"


def clear_all_chat_memory() -> None:
    """Erase all conversation checkpoints and writes from the chat memory DB. Safe to call if DB/tables do not exist."""
    if not CHAT_MEMORY_DB.exists():
        return
    try:
        with sqlite3.connect(str(CHAT_MEMORY_DB)) as conn:
            conn.execute("DELETE FROM writes")
            conn.execute("DELETE FROM checkpoints")
            conn.commit()
        logger.info("Chat memory wiped (all threads).")
    except sqlite3.OperationalError as e:
        if "no such table" in str(e).lower():
            return
        logger.warning("Chat memory wipe failed (tables may not exist yet): %s", e)
    except Exception as e:
        logger.warning("Chat memory wipe failed: %s", e)


@router.post("/chat")
def chat(req: ChatRequest) -> ChatResponse | ChatError:
    try:
        CHAT_MEMORY_DB.parent.mkdir(parents=True, exist_ok=True)
        from langgraph.checkpoint.sqlite import SqliteSaver

        with SqliteSaver.from_conn_string(str(CHAT_MEMORY_DB)) as checkpointer:
            from app.models.llm import get_default_model
            result = run_agent(
                query=req.query,
                model=get_default_model(),
                thread_id=req.thread_id,
                telegram_user_id=req.telegram_user_id,
                checkpointer=checkpointer,
            )

        clarification = result.get("clarification")
        if clarification:
            reply = redact_for_telegram(clarification)
            return ChatResponse(reply=reply, clarification=True)

        messages = result.get("messages") or []
        raw_reply = _extract_reply(messages)
        reply = redact_for_telegram(raw_reply)
        sources = _get_sources_from_messages(messages)
        footer = _format_final_footer(sources)
        reply = (reply + footer) if reply else footer.strip()

        image_base64 = None
        image_path = result.get("image_path")
        if image_path and Path(image_path).exists():
            try:
                with open(image_path, "rb") as f:
                    image_base64 = base64.b64encode(f.read()).decode("ascii")
            finally:
                Path(image_path).unlink(missing_ok=True)

        return ChatResponse(reply=reply, image_base64=image_base64)
    except Exception as e:
        logger.exception("Chat API error: %s", e)
        return ChatError(error=_user_friendly_error(e))


@router.post("/clear-memory")
def clear_memory(req: ClearMemoryRequest) -> dict:
    """Clear conversation checkpoint for the given thread_id. Bot can call this for /clearmemory."""
    try:
        CHAT_MEMORY_DB.parent.mkdir(parents=True, exist_ok=True)
        from langgraph.checkpoint.sqlite import SqliteSaver

        with SqliteSaver.from_conn_string(str(CHAT_MEMORY_DB)) as checkpointer:
            checkpointer.delete_thread(req.thread_id)
        return {"ok": True, "message": "Conversation memory cleared."}
    except Exception as e:
        logger.exception("Clear memory error: %s", e)
        return {"ok": False, "error": _user_friendly_error(e)}


@router.get("/health")
def health():
    return {"status": "ok"}


async def _memory_wipe_loop() -> None:
    """Background task: every MEMORY_WIPE_INTERVAL_SEC, wipe all chat memory."""
    while True:
        await asyncio.sleep(MEMORY_WIPE_INTERVAL_SEC)
        try:
            await asyncio.to_thread(clear_all_chat_memory)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.warning("Memory wipe loop error: %s", e)


@asynccontextmanager
async def _lifespan(app: FastAPI):
    task = asyncio.create_task(_memory_wipe_loop())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(title="BRVM Chat API", version="1.0", lifespan=_lifespan)
app.include_router(router)
