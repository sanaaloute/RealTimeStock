"""Telegram bot: forwards messages to the master agent; only allowed users. Accepts text or voice/audio."""
from __future__ import annotations

import asyncio
import logging
import tempfile
from pathlib import Path
from typing import Any

from telegram import Update
from telegram.ext import Application, ContextTypes, CommandHandler, MessageHandler, filters
from telegram.request import HTTPXRequest

import config
from agents import run_agent
from .help import get_help_message
from .redact import redact_for_telegram
from .voice_to_text import voice_to_text
from services.user_db import get_or_create_user, has_sent_help, mark_help_sent

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

    # Show help on explicit "help" / "aide" / "?" (any case)
    query_lower = query.strip().lower()
    if query_lower in ("help", "/help", "aide", "?", "aide moi", "comment utiliser", "how to use"):
        await update.message.reply_text(get_help_message())
        return

    # New user: send help once, then process their message
    get_or_create_user(user_id)
    if not has_sent_help(user_id):
        await update.message.reply_text(get_help_message())
        mark_help_sent(user_id)

    status = await update.message.reply_text("Thinking…")
    try:
        # thread_id enables conversation memory per chat; checkpointer persists user+AI history
        thread_id = str(update.effective_chat.id) if update.effective_chat else str(user_id)
        checkpointer = getattr(context.application, "bot_data", {}).get("checkpointer")
        result = await asyncio.to_thread(
            run_agent,
            query,
            model=config.OLLAMA_MODEL,
            thread_id=thread_id,
            telegram_user_id=user_id,
            checkpointer=checkpointer,
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
        # Ollama 503 / unavailable: friendly message instead of raw error
        status_code = getattr(e, "status_code", None) or (e.args[1] if len(getattr(e, "args", [])) > 1 else None)
        if status_code == 503 or "503" in str(e):
            await status.edit_text(
                "The AI service (Ollama) is temporarily unavailable. Often the model is not loaded yet: on your machine run "
                "ollama pull qwen3:8b then ollama run qwen3:8b (you can exit after it loads). Try again in a moment."
            )
        else:
            await status.edit_text(f"Error: {str(e)[:500]}")


# Longer timeouts for Docker/slow networks (default is 5s; Telegram can be slow from containers)
TELEGRAM_CONNECT_TIMEOUT = 30.0
TELEGRAM_READ_TIMEOUT = 30.0
TELEGRAM_WRITE_TIMEOUT = 30.0


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send help message for /help command."""
    if update.message:
        await update.message.reply_text(get_help_message())


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send help message for /start command (new or returning user)."""
    if update.message and update.effective_user:
        user_id = update.effective_user.id
        if not _is_allowed(user_id):
            await update.message.reply_text("You are not authorized to use this bot.")
            return
        await update.message.reply_text(get_help_message())


def build_application(checkpointer=None) -> Application:
    """Build the Telegram app. If checkpointer is provided, chat memory persists across restarts."""
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
    if checkpointer is not None:
        app.bot_data["checkpointer"] = checkpointer
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("start", cmd_start))
    # Text, voice messages, or audio files
    app.add_handler(
        MessageHandler(
            (filters.TEXT & ~filters.COMMAND) | filters.VOICE | filters.AUDIO,
            handle_message,
        )
    )
    return app
