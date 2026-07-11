"""Log redaction: keep secrets out of log output.

The concrete leak: httpx logs every request URL at INFO level, and Telegram
Bot API URLs embed the bot token
(`https://api.telegram.org/bot<digits>:<secret>/sendMessage`). Install once at
process start (after logging.basicConfig) in every entry point that talks to
Telegram.
"""
from __future__ import annotations

import logging
import re

# Telegram bot token inside Bot API URLs: bot<digits>:<token>
_TELEGRAM_TOKEN_RE = re.compile(r"(bot)\d{5,}:[A-Za-z0-9_-]{10,}")


class RedactSecretsFilter(logging.Filter):
    """Redacts known secret patterns from rendered log messages."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            msg = record.getMessage()
        except Exception:
            return True
        redacted = _TELEGRAM_TOKEN_RE.sub(r"\1<redacted>", msg)
        if redacted != msg:
            record.msg = redacted
            record.args = ()
        return True


def install_log_redaction() -> None:
    """Attach the redaction filter to all root handlers and the httpx logger.

    Handler-level filters run for every record regardless of which logger
    emitted it (logger-level filters on ancestors do not); the explicit httpx
    logger filter covers setups without root handlers.
    """
    f = RedactSecretsFilter()
    for handler in logging.getLogger().handlers:
        handler.addFilter(f)
    logging.getLogger("httpx").addFilter(f)
