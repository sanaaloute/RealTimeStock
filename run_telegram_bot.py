"""
Run the Telegram bot (natural-language questions → master agent). Authorized users only.

Schedules a daily job to update company time series CSVs (data/series). Configure TIMESERIES_SYMBOLS in .env.
"""
import logging
import sys
import threading
import time

import config
from bot import build_application
from services._data import run_daily_timeseries_update

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

DAILY_INTERVAL_SEC = 24 * 3600


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

    app = build_application()
    logger.info("Bot starting (allowed IDs: %s). Daily timeseries update scheduled.", config.ALLOWED_TELEGRAM_IDS)
    app.run_polling(allowed_updates=["message"], bootstrap_retries=5)
    return 0


if __name__ == "__main__":
    sys.exit(main())
