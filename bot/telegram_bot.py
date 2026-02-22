"""Telegram bot: forwards messages to the master agent; only allowed users. Accepts text or voice/audio."""
from __future__ import annotations

import asyncio
import logging
import tempfile
from pathlib import Path
from typing import Any

from telegram import Update
from telegram.ext import Application, ContextTypes, MessageHandler, filters
from telegram.request import HTTPXRequest

import config
from agents import run_agent
from .redact import redact_for_telegram
from .voice_to_text import voice_to_text

logger = logging.getLogger(__name__)

MAX_MESSAGE_LENGTH = 4096  # Telegram limit
MAX_CAPTION_LENGTH = 1024  # Telegram photo caption limit
VOICE_LANGUAGE = "fr-FR"  # BRVM / West Africa; use "en-US" for English


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


async def _get_query_from_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str | None:
    """Extract query from text, or from voice/audio by converting to text. Returns None if nothing to process."""
    msg = update.message
    if not msg:
        return None
    # Text
    if msg.text:
        return msg.text.strip() or None
    # Voice or audio: download and transcribe
    voice = getattr(msg, "voice", None)
    audio = getattr(msg, "audio", None)
    file_id = None
    suffix = ".ogg"
    if voice:
        file_id = voice.file_id
    elif audio:
        file_id = audio.file_id
        suffix = ".m4a"  # Telegram audio often m4a
    if not file_id:
        return None
    try:
        tg_file = await context.bot.get_file(file_id)
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
            await tg_file.download_to_drive(f.name)
            path = Path(f.name)
        try:
            text = await asyncio.to_thread(voice_to_text, path, VOICE_LANGUAGE)
            return (text or "").strip() or None
        finally:
            path.unlink(missing_ok=True)
    except Exception as e:
        logger.warning("Voice/audio download or transcription failed: %s", e)
        return None


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    user = update.effective_user
    if not user:
        return
    user_id = user.id
    if not _is_allowed(user_id):
        await update.message.reply_text("You are not authorized to use this bot.")
        logger.warning("Unauthorized user %s (%s)", user_id, getattr(user, "username", ""))
        return

    query = await _get_query_from_message(update, context)
    if not query:
        await update.message.reply_text(
            "Send a text message or a voice note with your question (e.g. price of NTLC, compare two stocks). "
            "If you sent voice and this appears, the audio could not be transcribed."
        )
        return

    status = await update.message.reply_text("Thinking…")
    try:
        # thread_id enables conversation memory (summarize memory) per chat
        thread_id = str(update.effective_chat.id) if update.effective_chat else str(user_id)
        result = await asyncio.to_thread(
            run_agent,
            query,
            model=config.OLLAMA_MODEL,
            thread_id=thread_id,
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
    # Text, voice messages, or audio files
    app.add_handler(
        MessageHandler(
            (filters.TEXT & ~filters.COMMAND) | filters.VOICE | filters.AUDIO,
            handle_message,
        )
    )
    return app
