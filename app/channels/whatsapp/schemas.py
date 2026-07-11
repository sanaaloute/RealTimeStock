"""Payload schemas and parsing for the Evolution API webhook.

Evolution deliveries come in two shapes:
  * v2: {"event": "messages.upsert", "instance": "...", "data": {<message>}}
  * v1: {"event": "messages.upsert", "data": {"messages": [{<message>}, ...]}}

`parse_inbound_messages` normalizes both into `InboundMessage` items. Baileys
message content is too polymorphic for strict validation, so the envelope is
validated and the `message` tree is parsed defensively.
"""
from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Event types we act on; everything else (connection.update, status, ...) is ignored.
HANDLED_EVENT = "messages.upsert"

# JID suffixes we can map to a phone number / must ignore.
_USER_JID_SUFFIX = "@s.whatsapp.net"
_GROUP_JID_SUFFIX = "@g.us"


class EvolutionMessageKey(BaseModel):
    """`key` block of an Evolution/Baileys message."""

    remote_jid: str = Field(default="", alias="remoteJid")
    from_me: bool = Field(default=False, alias="fromMe")
    id: str = ""

    model_config = {"populate_by_name": True}


class InboundMessage(BaseModel):
    """One inbound WhatsApp message, normalized for the channel service."""

    phone: str  # digits only, e.g. "22670000000" — the channel user id
    message_id: str  # key.id, used for delivery dedup
    kind: str  # "text" | "audio" | "unsupported"
    text: str = ""
    audio_base64: str | None = None  # present when the instance sends base64
    audio_mimetype: str | None = None
    raw_message: dict[str, Any] = Field(default_factory=dict)  # for media fetch fallback


def _unwrap_message(message: dict[str, Any]) -> dict[str, Any]:
    """Descend one level through Baileys wrappers (ephemeral / view-once)."""
    for wrapper in ("ephemeralMessage", "viewOnceMessage", "viewOnceMessageV2"):
        inner = message.get(wrapper)
        if isinstance(inner, dict) and isinstance(inner.get("message"), dict):
            return inner["message"]
    return message


def _extract_data_items(data: Any) -> list[dict[str, Any]]:
    """Normalize the `data` block to a list of raw message dicts (v1 and v2)."""
    if isinstance(data, list):
        return [m for m in data if isinstance(m, dict)]
    if isinstance(data, dict):
        messages = data.get("messages")
        if isinstance(messages, list):  # v1 shape
            return [m for m in messages if isinstance(m, dict)]
        return [data]  # v2 shape: data IS the message
    return []


def _parse_one(raw: dict[str, Any]) -> InboundMessage | None:
    """Parse a single raw Baileys message, or None when it must be skipped."""
    try:
        key = EvolutionMessageKey.model_validate(raw.get("key") or {})
    except Exception as e:
        logger.debug("Skipping message with invalid key: %s", e)
        return None
    if key.from_me:
        return None  # our own outbound echoes
    jid = key.remote_jid
    if not jid or jid.endswith(_GROUP_JID_SUFFIX) or jid.endswith("@broadcast"):
        return None  # groups and broadcasts are out of scope
    if not jid.endswith(_USER_JID_SUFFIX):
        logger.debug("Skipping unsupported JID: %s", jid)
        return None
    phone = jid[: -len(_USER_JID_SUFFIX)]
    if not phone.isdigit():
        logger.debug("Skipping non-numeric sender JID: %s", jid)
        return None

    message = raw.get("message")
    if not isinstance(message, dict):
        return None
    message = _unwrap_message(message)

    # Plain text or extended text (replies, link previews)
    text = (message.get("conversation") or "").strip()
    if not text:
        ext = message.get("extendedTextMessage")
        if isinstance(ext, dict):
            text = (ext.get("text") or "").strip()
    if text:
        return InboundMessage(
            phone=phone, message_id=key.id, kind="text", text=text, raw_message=raw
        )

    # Voice note / audio
    audio = message.get("audioMessage")
    if isinstance(audio, dict):
        base64 = raw.get("base64") or message.get("base64")
        return InboundMessage(
            phone=phone,
            message_id=key.id,
            kind="audio",
            audio_base64=base64 if isinstance(base64, str) and base64 else None,
            audio_mimetype=audio.get("mimetype"),
            raw_message=raw,
        )

    return InboundMessage(
        phone=phone, message_id=key.id, kind="unsupported", raw_message=raw
    )


def parse_inbound_messages(payload: dict[str, Any]) -> list[InboundMessage]:
    """Extract inbound user messages from one Evolution webhook payload.

    Returns an empty list for events we don't handle, self-sent messages,
    groups/broadcasts, and malformed items — the webhook must never crash.
    """
    if not isinstance(payload, dict):
        return []
    event = str(payload.get("event") or "").lower().replace("_", ".")
    if event != HANDLED_EVENT:
        return []
    parsed: list[InboundMessage] = []
    for raw in _extract_data_items(payload.get("data")):
        msg = _parse_one(raw)
        if msg is not None:
            parsed.append(msg)
    return parsed
