"""Telegram bot: forwards messages to the master agent; only allowed users."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from telegram import Update
from telegram.ext import Application, ContextTypes, MessageHandler, filters

import config
from agents import run_agent
from .redact import redact_for_telegram

logger = logging.getLogger(__name__)

MAX_MESSAGE_LENGTH = 4096  # Telegram limit


def _is_allowed(user_id: int) -> bool:
    if not config.ALLOWED_TELEGRAM_IDS:
        return False
    return user_id in config.ALLOWED_TELEGRAM_IDS


def _extract_reply(messages: list[Any]) -> str:
    """Last AI message content, or fallback."""
    for m in reversed(messages):
        if not getattr(m, "content", None):
            continue
        kind = getattr(m, "type", None) or type(m).__name__
        if kind == "ai" or "AI" in str(kind):
            return str(m.content).strip()
    for m in reversed(messages):
        if getattr(m, "content", None) and "Human" not in type(m).__name__:
            return str(m.content).strip()
    return "No answer from the agent."


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return
    user = update.effective_user
    if not user:
        return
    user_id = user.id
    if not _is_allowed(user_id):
        await update.message.reply_text("You are not authorized to use this bot.")
        logger.warning("Unauthorized user %s (%s)", user_id, getattr(user, "username", ""))
        return

    query = update.message.text.strip()
    if not query:
        await update.message.reply_text("Send a question about BRVM stocks (e.g. price of NTLC, compare two stocks).")
        return

    status = await update.message.reply_text("Thinking…")
    try:
        result = await asyncio.to_thread(
            run_agent,
            query,
            model=config.OLLAMA_MODEL,
        )
        messages = result.get("messages") or []
        raw_reply = _extract_reply(messages)
        reply = await asyncio.to_thread(redact_for_telegram, raw_reply)
        if len(reply) > MAX_MESSAGE_LENGTH:
            reply = reply[: MAX_MESSAGE_LENGTH - 20] + "\n\n… (truncated)"
        await status.edit_text(reply)
    except Exception as e:
        logger.exception("Agent error for user %s: %s", user_id, e)
        await status.edit_text(f"Error: {str(e)[:500]}")


def build_application() -> Application:
    app = (
        Application.builder()
        .token(config.TELEGRAM_BOT_TOKEN)
        .build()
    )
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    return app
