"""Telegram bot: forwards to Chat API, allowed users only. Text and voice."""
from __future__ import annotations

import asyncio
import base64
import logging
import tempfile
from pathlib import Path
from typing import Any

import httpx
from telegram import Update
from telegram.ext import Application, ContextTypes, CommandHandler, MessageHandler, filters
from telegram.request import HTTPXRequest

import config
from .help import get_help_message
from .voice_to_text import voice_to_text
from services.user_db import get_or_create_user, has_sent_help, mark_help_sent

logger = logging.getLogger(__name__)

MAX_MESSAGE_LENGTH = 4096  # Telegram limit
MAX_CAPTION_LENGTH = 1024  # Telegram photo caption limit
VOICE_LANGUAGE = "fr-FR"  # BRVM / West Africa; use "en-US" for English
API_TIMEOUT = 120.0  # Agent can take a while


def _is_allowed(user_id: int) -> bool:
    if not config.ALLOWED_TELEGRAM_IDS:
        return False
    return user_id in config.ALLOWED_TELEGRAM_IDS


def _is_local_api() -> bool:
    u = config.BRVM_API_URL.lower()
    return "localhost" in u or "127.0.0.1" in u


async def _call_chat_api(query: str, thread_id: str, telegram_user_id: int) -> dict[str, Any]:
    url = f"{config.BRVM_API_URL}/chat"
    payload = {"query": query, "thread_id": thread_id, "telegram_user_id": telegram_user_id}
    client_kwargs = {"timeout": API_TIMEOUT}
    if _is_local_api():
        client_kwargs["trust_env"] = False
    async with httpx.AsyncClient(**client_kwargs) as client:
        resp = await client.post(url, json=payload)
        if resp.status_code != 200:
            try:
                data = resp.json()
                if "error" in data:
                    return data
            except Exception:
                pass
            return {"error": "The AI service is temporarily unavailable. Try again in a moment."}
        return resp.json()


async def _get_query_from_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str | None:
    msg = update.message
    if not msg:
        return None
    # Text
    if msg.text:
        return msg.text.strip() or None
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

    query_lower = query.strip().lower()
    if query_lower in ("help", "/help", "aide", "?", "aide moi", "comment utiliser", "how to use"):
        await update.message.reply_text(get_help_message())
        return

    get_or_create_user(user_id)
    if not has_sent_help(user_id):
        await update.message.reply_text(get_help_message())
        mark_help_sent(user_id)

    status = await update.message.reply_text("Thinking…")
    try:
        thread_id = str(update.effective_chat.id) if update.effective_chat else str(user_id)
        result = await _call_chat_api(query, thread_id, user_id)
    except Exception as e:
        logger.exception("API call failed for user %s: %s", user_id, e)
        await status.edit_text("Could not reach the AI service. Try again in a moment.")
        return

    if "error" in result:
        await status.edit_text(result["error"])
        return

    reply = result.get("reply", "")
    if len(reply) > MAX_MESSAGE_LENGTH:
        reply = reply[: MAX_MESSAGE_LENGTH - 20] + "\n\n… (truncated)"

    image_base64 = result.get("image_base64")
    if image_base64:
        caption = reply[:MAX_CAPTION_LENGTH] if len(reply) <= MAX_CAPTION_LENGTH else reply[: MAX_CAPTION_LENGTH - 20] + "\n… (truncated)"
        await status.delete()
        try:
            img_bytes = base64.b64decode(image_base64)
            await update.message.reply_photo(photo=img_bytes, caption=caption or None)
        except Exception as e:
            logger.warning("Failed to send image: %s", e)
            await update.message.reply_text(reply)
    else:
        await status.edit_text(reply)


TELEGRAM_CONNECT_TIMEOUT = 30.0
TELEGRAM_READ_TIMEOUT = 30.0
TELEGRAM_WRITE_TIMEOUT = 30.0


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message:
        await update.message.reply_text(get_help_message())


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message and update.effective_user:
        user_id = update.effective_user.id
        if not _is_allowed(user_id):
            await update.message.reply_text("You are not authorized to use this bot.")
            return
        await update.message.reply_text(get_help_message())


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
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(
        MessageHandler(
            (filters.TEXT & ~filters.COMMAND) | filters.VOICE | filters.AUDIO,
            handle_message,
        )
    )
    return app
