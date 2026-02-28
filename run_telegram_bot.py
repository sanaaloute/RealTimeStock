"""Run Telegram bot only (requires API). For API + bot together, use: python main.py"""
import logging
import sys
import threading
import time

import httpx

import config
from app.bot import build_application
from app.utils._data import run_daily_timeseries_update

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


def main() -> int:
    if not config.TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN is not set. Add it to .env (from @BotFather).")
        return 1
    if not config.ALLOWED_TELEGRAM_IDS:
        logger.error("ALLOWED_TELEGRAM_IDS is empty. Add at least one Telegram user ID to .env.")
        return 1
    if config.OLLAMA_CLOUD and not config.OLLAMA_API_KEY:
        logger.error("OLLAMA_API_KEY is required when OLLAMA_CLOUD=true. Create one at https://ollama.com/settings/keys")
        return 1

    api_url = config.BRVM_API_URL
    health_url = f"{api_url}/health"
    client_kwargs = {"timeout": 5.0}
    if "localhost" in api_url.lower() or "127.0.0.1" in api_url:
        client_kwargs["trust_env"] = False
    try:
        with httpx.Client(**client_kwargs) as client:
            r = client.get(health_url)
            if r.status_code != 200:
                logger.error(
                    "Chat API at %s returned %s. Start the API first: python main.py or python run_api.py",
                    api_url,
                    r.status_code,
                )
                return 1
    except httpx.ConnectError as e:
        logger.error(
            "Cannot reach Chat API at %s. Is it running? Start it with: python main.py or python run_api.py\n"
            "If bot and API run on different machines, set BRVM_API_URL in .env to the API URL (e.g. http://your-server:8000).\n"
            "Error: %s",
            api_url,
            e,
        )
        return 1
    except Exception as e:
        logger.error("Chat API health check failed: %s", e)
        return 1

    thread = threading.Thread(target=_daily_timeseries_job, daemon=True)
    thread.start()

    app = build_application()
    if app.job_queue is not None:
        app.job_queue.run_repeating(_check_target_alerts, interval=TARGET_CHECK_INTERVAL_SEC, first=60)
        logger.info(
            "Bot starting (allowed IDs: %s). Chat API: %s. Daily timeseries + target alerts (every %s s) scheduled.",
            config.ALLOWED_TELEGRAM_IDS,
            config.BRVM_API_URL,
            TARGET_CHECK_INTERVAL_SEC,
        )
    else:
        logger.warning(
            "JobQueue not available. Install with: pip install \"python-telegram-bot[job-queue]\" for price target alerts."
        )
        logger.info(
            "Bot starting (allowed IDs: %s). Chat API: %s. Daily timeseries scheduled; target alerts disabled.",
            config.ALLOWED_TELEGRAM_IDS,
            config.BRVM_API_URL,
        )
    app.run_polling(allowed_updates=["message"], bootstrap_retries=5)
    return 0


if __name__ == "__main__":
    sys.exit(main())
