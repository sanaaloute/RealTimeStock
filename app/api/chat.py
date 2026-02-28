"""FastAPI chat endpoint. Bot calls this; API runs agents and returns sanitized response."""
from __future__ import annotations

import base64
import logging
from pathlib import Path

from fastapi import APIRouter, FastAPI
from pydantic import BaseModel

import config
from app.agents import run_agent
from app.agents.graph import CHAT_MEMORY_DB
from app.bot.redact import redact_for_telegram

logger = logging.getLogger(__name__)

router = APIRouter()


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


@router.get("/health")
def health():
    return {"status": "ok"}


app = FastAPI(title="BRVM Chat API", version="1.0")
app.include_router(router)
