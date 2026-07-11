"""FastAPI chat endpoint. Bot calls this; API runs agents and returns sanitized response."""
from __future__ import annotations

import base64
import logging
import secrets
import sqlite3
import threading
import time
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel

import config
from app.agents import run_agent
from app.agents.graph import CHAT_MEMORY_DB
from app.bot.redact import redact_for_telegram
from app.utils.user_db import decrement_daily_usage, increment_daily_usage

logger = logging.getLogger(__name__)

app = FastAPI(title="BRVM Chat API", version="1.0")

if not config.API_SECRET_KEY:
    logger.warning(
        "API_SECRET_KEY is not set: /chat accepts UNAUTHENTICATED requests. "
        "Set API_SECRET_KEY in .env before exposing this API."
    )


def verify_api_key(x_api_key: str | None = Header(default=None)) -> None:
    """Require the shared secret when API_SECRET_KEY is configured (constant-time compare)."""
    secret = config.API_SECRET_KEY
    if not secret:
        return  # dev mode: no key configured
    if not x_api_key or not secrets.compare_digest(x_api_key.strip(), secret):
        raise HTTPException(status_code=401, detail="Invalid or missing API key.")


# --- Coarse per-user rate limiting (in-memory, per-process) ---
_RATE_WINDOW_SEC = 60.0
_rate_hits: dict[str, list[float]] = {}
_rate_lock = threading.Lock()
_rate_last_cleanup = 0.0


def _rate_limited(key: str) -> bool:
    """True if `key` exceeded RATE_LIMIT_PER_MINUTE within the last 60 seconds."""
    limit = config.RATE_LIMIT_PER_MINUTE
    if limit <= 0:
        return False
    global _rate_last_cleanup
    now = time.monotonic()
    with _rate_lock:
        hits = [t for t in _rate_hits.get(key, []) if now - t < _RATE_WINDOW_SEC]
        if len(hits) >= limit:
            _rate_hits[key] = hits
            return True
        hits.append(now)
        _rate_hits[key] = hits
        if now - _rate_last_cleanup > 600:  # keep dict bounded
            _rate_last_cleanup = now
            for k in [k for k, v in _rate_hits.items() if not v or now - v[-1] >= _RATE_WINDOW_SEC]:
                _rate_hits.pop(k, None)
    return False


# One persistent checkpointer for the process: created once (not per request),
# usable from uvicorn's worker threads (check_same_thread=False), WAL mode so
# concurrent readers/writers don't block each other.
_checkpointer = None
_checkpointer_lock = threading.Lock()


def _get_checkpointer():
    global _checkpointer
    if _checkpointer is None:
        with _checkpointer_lock:
            if _checkpointer is None:
                from langgraph.checkpoint.sqlite import SqliteSaver

                CHAT_MEMORY_DB.parent.mkdir(parents=True, exist_ok=True)
                conn = sqlite3.connect(
                    str(CHAT_MEMORY_DB), check_same_thread=False, timeout=30.0
                )
                try:
                    conn.execute("PRAGMA journal_mode=WAL")
                    conn.execute("PRAGMA busy_timeout=30000")
                except sqlite3.Error as e:
                    logger.warning("SQLite pragmas skipped: %s", e)
                _checkpointer = SqliteSaver(conn)
    return _checkpointer


# Cap concurrent agent runs so a burst of users can't melt the LLM backend.
_agent_semaphore = threading.Semaphore(max(1, config.MAX_CONCURRENT_AGENTS))


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
    if "503" in err_str or "ssl" in err_str or "eof" in err_str or "connect" in err_str:
        return "The AI service is temporarily unavailable. Try again in a moment."
    if "timeout" in err_str:
        return "The request took too long. Try again."
    return "Something went wrong. Please try again."


class ChatRequest(BaseModel):
    query: str
    thread_id: str = "default"
    telegram_user_id: int | None = None
    # Channel-agnostic identity (e.g. "wa:22507000000"). When set, it is the
    # key used for rate limiting and the daily quota. Telegram callers keep
    # sending telegram_user_id (their key stays the raw id for back-compat).
    user_id: str | None = None


class ChatResponse(BaseModel):
    reply: str
    image_base64: str | None = None
    clarification: bool = False


class ChatError(BaseModel):
    error: str


def _quota_active(user_key: str) -> bool:
    return config.DAILY_FREE_QUOTA > 0 and user_key not in config.QUOTA_EXEMPT_IDS


@app.post("/chat", dependencies=[Depends(verify_api_key)])
def chat(req: ChatRequest) -> ChatResponse | ChatError:
    if req.user_id:
        user_key = req.user_id
    elif req.telegram_user_id is not None:
        user_key = str(req.telegram_user_id)
    else:
        user_key = f"thread:{req.thread_id}"
    if _rate_limited(user_key):
        logger.info("Rate limited: %s", user_key)
        return ChatError(error="Too many requests. Please wait a moment and try again.")
    acquired = _agent_semaphore.acquire(timeout=config.AGENT_QUEUE_TIMEOUT)
    if not acquired:
        logger.warning("Agent pool saturated; rejecting request for thread %s", req.thread_id)
        return ChatError(
            error="The assistant is busy right now (too many requests). Please try again in a moment."
        )
    counted = False
    try:
        # Daily free quota: count the request once it has a worker slot, so
        # rate-limited/"busy" rejections never consume quota. Atomic
        # increment-then-check keeps concurrent requests from overshooting.
        if _quota_active(user_key):
            used = increment_daily_usage(user_key)
            if used > config.DAILY_FREE_QUOTA:
                decrement_daily_usage(user_key)
                logger.info("Daily quota exhausted: %s (limit %d)", user_key, config.DAILY_FREE_QUOTA)
                return ChatError(
                    error=(
                        f"⏳ Vous avez atteint la limite de {config.DAILY_FREE_QUOTA} "
                        "requêtes gratuites par jour. Revenez demain pour continuer !"
                    )
                )
            counted = True
        result = run_agent(
            query=req.query,
            model=config.OLLAMA_MODEL,
            thread_id=req.thread_id,
            telegram_user_id=req.telegram_user_id,
            checkpointer=_get_checkpointer(),
        )

        clarification = result.get("clarification")
        if clarification:
            reply = redact_for_telegram(clarification)
            return ChatResponse(reply=reply, clarification=True)

        messages = result.get("messages") or []
        raw_reply = _extract_reply(messages)
        reply = redact_for_telegram(raw_reply)

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
        if counted:
            decrement_daily_usage(user_key)  # refund: failed requests are free
        logger.exception("Chat API error: %s", e)
        return ChatError(error=_user_friendly_error(e))
    finally:
        _agent_semaphore.release()


@app.get("/health")
def health():
    return {"status": "ok"}


# WhatsApp Business Cloud API webhook (no-op unless WHATSAPP_* env vars are set).
from app.api.whatsapp import router as whatsapp_router  # noqa: E402

app.include_router(whatsapp_router)
