"""Single entry point: FastAPI + Telegram bot. Run with: python main.py or uvicorn app.main:app."""
from __future__ import annotations

import logging
import multiprocessing
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI

import config
from app.api.chat import router as chat_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

DAILY_INTERVAL_SEC = 24 * 3600
TARGET_CHECK_INTERVAL_SEC = 300


def _daily_timeseries_job() -> None:
    """Run once per day: update CSVs for all configured symbols."""
    while True:
        time.sleep(DAILY_INTERVAL_SEC)
        try:
            from app.utils._data import run_daily_timeseries_update
            logger.info("Daily timeseries update: %s", config.TIMESERIES_SYMBOLS)
            for r in run_daily_timeseries_update(config.TIMESERIES_SYMBOLS):
                logger.info("Timeseries %s: %s", r.get("symbol"), r.get("action", r))
        except Exception as e:
            logger.exception("Daily timeseries update failed: %s", e)


async def _check_target_alerts(context) -> None:
    """Job: check price targets and send Telegram notifications."""
    try:
        from app.utils.user_db import check_targets_and_notify
        allowed = set(config.ALLOWED_TELEGRAM_IDS or [])
        for telegram_id, text in check_targets_and_notify():
            if telegram_id not in allowed:
                continue
            try:
                await context.bot.send_message(chat_id=telegram_id, text=text)
                logger.info("Target alert sent to user %s", telegram_id)
            except Exception as e:
                logger.warning("Failed to send target alert to %s: %s", telegram_id, e)
    except Exception as e:
        logger.exception("Target check job failed: %s", e)


def _run_telegram_bot() -> None:
    """Run Telegram bot (blocking). Must run in main thread for signal handlers; use Process."""
    time.sleep(2)  # Let uvicorn finish starting
    if not config.TELEGRAM_BOT_TOKEN:
        logger.warning("TELEGRAM_BOT_TOKEN not set. Telegram bot disabled.")
        return
    if not config.ALLOWED_TELEGRAM_IDS:
        logger.warning("ALLOWED_TELEGRAM_IDS empty. Telegram bot disabled.")
        return

    import threading
    thread = threading.Thread(target=_daily_timeseries_job, daemon=True)
    thread.start()

    from app.bot import build_application
    app = build_application()
    if app.job_queue is not None:
        app.job_queue.run_repeating(_check_target_alerts, interval=TARGET_CHECK_INTERVAL_SEC, first=60)
        logger.info(
            "Telegram bot starting (allowed IDs: %s). API: %s. Daily timeseries + target alerts (every %s s).",
            config.ALLOWED_TELEGRAM_IDS,
            config.BRVM_API_URL,
            TARGET_CHECK_INTERVAL_SEC,
        )
    else:
        logger.info(
            "Telegram bot starting (allowed IDs: %s). API: %s. Target alerts disabled (install python-telegram-bot[job-queue]).",
            config.ALLOWED_TELEGRAM_IDS,
            config.BRVM_API_URL,
        )
    app.run_polling(allowed_updates=["message"], bootstrap_retries=5)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start Telegram bot in background process (needs main thread for signal handlers)."""
    if config.TELEGRAM_BOT_TOKEN and config.ALLOWED_TELEGRAM_IDS:
        p = multiprocessing.Process(target=_run_telegram_bot, daemon=True)
        p.start()
        logger.info("Telegram bot process started.")
    else:
        logger.info("API-only mode (no Telegram bot). Set TELEGRAM_BOT_TOKEN and ALLOWED_TELEGRAM_IDS for full mode.")
    yield
    # Shutdown: daemon threads exit with process


app = FastAPI(title="BRVM Chat API", version="1.0", lifespan=lifespan)
app.include_router(chat_router)
