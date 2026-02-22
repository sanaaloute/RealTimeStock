"""Telegram bot: forwards messages to the master agent; only allowed users."""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

from telegram import Update
from telegram.ext import Application, ContextTypes, MessageHandler, filters
from telegram.request import HTTPXRequest

import config
from agents import run_agent
from .redact import redact_for_telegram

logger = logging.getLogger(__name__)

MAX_MESSAGE_LENGTH = 4096  # Telegram limit
MAX_CAPTION_LENGTH = 1024  # Telegram photo caption limit


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
        # If NLU asked for clarification, return that as the reply
        clarification = result.get("clarification")
        if clarification:
            reply = await asyncio.to_thread(redact_for_telegram, clarification)
            if len(reply) > MAX_MESSAGE_LENGTH:
                reply = reply[: MAX_MESSAGE_LENGTH - 20] + "\n\n… (truncated)"
            await status.edit_text(reply)
            return

        messages = result.get("messages") or []
        raw_reply = _extract_reply(messages)
        reply = await asyncio.to_thread(redact_for_telegram, raw_reply)
        image_path = result.get("image_path")

        if image_path and Path(image_path).exists():
            caption = reply[:MAX_CAPTION_LENGTH] if len(reply) <= MAX_CAPTION_LENGTH else reply[: MAX_CAPTION_LENGTH - 20] + "\n… (truncated)"
            await status.delete()
            with open(image_path, "rb") as f:
                await update.message.reply_photo(photo=f, caption=caption or None)
            try:
                Path(image_path).unlink(missing_ok=True)
            except OSError:
                pass
        else:
            if len(reply) > MAX_MESSAGE_LENGTH:
                reply = reply[: MAX_MESSAGE_LENGTH - 20] + "\n\n… (truncated)"
            await status.edit_text(reply)
    except Exception as e:
        logger.exception("Agent error for user %s: %s", user_id, e)
        await status.edit_text(f"Error: {str(e)[:500]}")


# Longer timeouts for Docker/slow networks (default is 5s; Telegram can be slow from containers)
TELEGRAM_CONNECT_TIMEOUT = 30.0
TELEGRAM_READ_TIMEOUT = 30.0
TELEGRAM_WRITE_TIMEOUT = 30.0


def build_application() -> Application:
    request = HTTPXRequest(
        connect_timeout=TELEGRAM_CONNECT_TIMEOUT,
        read_timeout=TELEGRAM_READ_TIMEOUT,
        write_timeout=TELEGRAM_WRITE_TIMEOUT,
    )
    builder = (
        Application.builder()
        .token(config.TELEGRAM_BOT_TOKEN)
        .request(request)
    )
    app = builder.build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    return app
