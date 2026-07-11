"""Async client for the Evolution API (self-hosted WhatsApp gateway).

Every HTTP call to Evolution lives in this module — nothing else in the
channel builds URLs or requests. Sends are retried with exponential backoff
on transient failures (timeouts, connection errors, 5xx); 4xx responses are
raised immediately since retrying them is pointless.

Docs: https://doc.evolution-api.com  (v2 endpoints)
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

import config

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_SEC = 30.0
MAX_RETRIES = 3
RETRY_BASE_DELAY_SEC = 1.0


class EvolutionError(Exception):
    """Raised when the Evolution API cannot deliver after all retries."""


class EvolutionClient:
    """Thin async wrapper over the Evolution message endpoints."""

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        instance: str | None = None,
        timeout: float = DEFAULT_TIMEOUT_SEC,
        max_retries: int = MAX_RETRIES,
    ) -> None:
        self._base_url = (base_url if base_url is not None else config.EVOLUTION_URL).rstrip("/")
        self._api_key = api_key if api_key is not None else config.EVOLUTION_API_KEY
        self._instance = instance if instance is not None else config.EVOLUTION_INSTANCE
        self._timeout = timeout
        self._max_retries = max(1, max_retries)

    # --- Public API -------------------------------------------------------

    async def send_text(self, number: str, text: str) -> dict[str, Any]:
        """Send a text message to a WhatsApp number (digits only)."""
        if not text:
            return {}
        return await self._post(
            f"/message/sendText/{self._instance}",
            {"number": number, "text": text},
        )

    async def send_image(
        self, number: str, image_base64: str, caption: str = ""
    ) -> dict[str, Any]:
        """Send a PNG image (base64, no data-URI prefix) with an optional caption."""
        return await self._post(
            f"/message/sendMedia/{self._instance}",
            {
                "number": number,
                "mediatype": "image",
                "mimetype": "image/png",
                "media": image_base64,
                "caption": caption[:1024],
            },
        )

    async def get_media_base64(self, message: dict[str, Any]) -> str | None:
        """Fetch the base64 of an inbound media message (voice note fallback).

        Used when the webhook payload did not embed the media bytes (instance
        webhook base64 disabled). Returns None when unavailable.
        """
        try:
            data = await self._post(
                f"/chat/getBase64FromMediaMessage/{self._instance}",
                {"message": message, "convertToMp4": False},
            )
        except EvolutionError as e:
            logger.warning("Media base64 fetch failed: %s", e)
            return None
        base64 = data.get("base64") if isinstance(data, dict) else None
        return base64 if isinstance(base64, str) and base64 else None

    # --- Internals --------------------------------------------------------

    async def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        """POST with retries: backoff on transport errors and 5xx, fail fast on 4xx."""
        url = f"{self._base_url}{path}"
        headers = {"apikey": self._api_key, "Content-Type": "application/json"}
        last_error: Exception | None = None
        for attempt in range(1, self._max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    resp = await client.post(url, json=payload, headers=headers)
                if resp.status_code >= 500:
                    raise httpx.HTTPStatusError(
                        f"server error {resp.status_code}", request=resp.request, response=resp
                    )
                if resp.status_code >= 400:
                    # Client error (bad request, auth, ...): no point retrying.
                    logger.error(
                        "Evolution rejected %s (HTTP %s): %s", path, resp.status_code, resp.text[:300]
                    )
                    raise EvolutionError(f"Evolution HTTP {resp.status_code}: {resp.text[:200]}")
                try:
                    return resp.json()
                except ValueError:
                    return {}
            except EvolutionError:
                raise
            except (httpx.TransportError, httpx.HTTPStatusError) as e:
                last_error = e
                if attempt >= self._max_retries:
                    break
                delay = RETRY_BASE_DELAY_SEC * (2 ** (attempt - 1))
                logger.warning(
                    "Evolution %s attempt %d/%d failed (%s); retrying in %.1fs",
                    path, attempt, self._max_retries, e, delay,
                )
                await asyncio.sleep(delay)
        logger.error("Evolution %s failed after %d attempts: %s", path, self._max_retries, last_error)
        raise EvolutionError(f"Evolution unreachable after {self._max_retries} attempts: {last_error}")
