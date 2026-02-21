"""
Run the Telegram bot (natural-language questions → master agent). Authorized users only.

Setup:
  1. Create a bot with @BotFather, get TELEGRAM_BOT_TOKEN.
  2. Add your Telegram user ID(s) to ALLOWED_TELEGRAM_IDS in .env (comma-separated).
     To get your ID: message @userinfobot on Telegram.
  3. python run_telegram_bot.py
"""
import logging
import sys

import config
from bot import build_application

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def main() -> int:
    if not config.TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN is not set. Add it to .env (from @BotFather).")
        return 1
    if not config.ALLOWED_TELEGRAM_IDS:
        logger.error("ALLOWED_TELEGRAM_IDS is empty. Add at least one Telegram user ID to .env.")
        return 1

    app = build_application()
    logger.info("Bot starting (allowed IDs: %s). Send a message to the bot.", config.ALLOWED_TELEGRAM_IDS)
    app.run_polling(allowed_updates=["message"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
