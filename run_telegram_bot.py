"""
Run the Telegram bot (natural-language questions → master agent). Authorized users only.

Schedules: daily timeseries CSV update; periodic check of price targets and notifies users.
Chat memory (user + AI) persists in data/chat_memory.db across restarts.
"""
import logging
import sys
import threading
import time

import config
from agents.graph import CHAT_MEMORY_DB
from bot import build_application
from services._data import run_daily_timeseries_update

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

DAILY_INTERVAL_SEC = 24 * 3600
TARGET_CHECK_INTERVAL_SEC = 300  # 5 minutes


def _daily_timeseries_job() -> None:
    """Run once per day: update CSVs for all configured symbols."""
    while True:
        time.sleep(DAILY_INTERVAL_SEC)
        try:
            logger.info("Daily timeseries update: %s", config.TIMESERIES_SYMBOLS)
            results = run_daily_timeseries_update(config.TIMESERIES_SYMBOLS)
            for r in results:
                logger.info("Timeseries %s: %s", r.get("symbol"), r.get("action", r))
        except Exception as e:
            logger.exception("Daily timeseries update failed: %s", e)


async def _check_target_alerts(context) -> None:
    """Job: check price targets and send Telegram notifications to users whose target was reached."""
    try:
        from services.user_db import check_targets_and_notify
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


def main() -> int:
    if not config.TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN is not set. Add it to .env (from @BotFather).")
        return 1
    if not config.ALLOWED_TELEGRAM_IDS:
        logger.error("ALLOWED_TELEGRAM_IDS is empty. Add at least one Telegram user ID to .env.")
        return 1

    # Schedule daily CSV update (once per day)
    thread = threading.Thread(target=_daily_timeseries_job, daemon=True)
    thread.start()

    # Persistent chat memory: user + AI messages in SQLite
    CHAT_MEMORY_DB.parent.mkdir(parents=True, exist_ok=True)
    from langgraph.checkpoint.sqlite import SqliteSaver

    with SqliteSaver.from_conn_string(str(CHAT_MEMORY_DB)) as checkpointer:
        app = build_application(checkpointer=checkpointer)
        # Price target alerts: check every 5 min (requires pip install "python-telegram-bot[job-queue]")
        if app.job_queue is not None:
            app.job_queue.run_repeating(_check_target_alerts, interval=TARGET_CHECK_INTERVAL_SEC, first=60)
            logger.info(
                "Bot starting (allowed IDs: %s). Chat memory: %s. Daily timeseries + target alerts (every %s s) scheduled.",
                config.ALLOWED_TELEGRAM_IDS,
                CHAT_MEMORY_DB,
                TARGET_CHECK_INTERVAL_SEC,
            )
        else:
            logger.warning(
                "JobQueue not available. Install with: pip install \"python-telegram-bot[job-queue]\" for price target alerts."
            )
            logger.info(
                "Bot starting (allowed IDs: %s). Chat memory: %s. Daily timeseries scheduled; target alerts disabled.",
                config.ALLOWED_TELEGRAM_IDS,
                CHAT_MEMORY_DB,
            )
        app.run_polling(allowed_updates=["message"], bootstrap_retries=5)
    return 0


if __name__ == "__main__":
    sys.exit(main())
