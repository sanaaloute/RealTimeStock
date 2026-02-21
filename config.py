"""Configuration for stock market scrapers and Telegram bot."""
import os
from dotenv import load_dotenv

load_dotenv()

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
SLEEP_SECONDS = float(os.getenv("SCRAPER_SLEEP_SECONDS", "2"))

# Target URLs
SIKAFINANCE_URL = "https://www.sikafinance.com/"
SIKAFINANCE_PALMARES_URL = "https://www.sikafinance.com/marches/palmares"
RICHBOURSE_URL = "https://www.richbourse.com/common/variation/index"
BRVM_URL = "https://www.brvm.org/"

# Telegram bot (run_telegram_bot.py)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
# Comma-separated Telegram user IDs (e.g. 123456789,987654321). Only these users can use the bot.
ALLOWED_TELEGRAM_IDS: list[int] = [7720243270]
_raw = os.getenv("ALLOWED_TELEGRAM_IDS", "").strip()
if _raw:
    for s in _raw.replace(" ", "").split(","):
        if s.isdigit():
            ALLOWED_TELEGRAM_IDS.append(int(s))

# Ollama (agent + redact). Set OLLAMA_BASE_URL in Docker to reach host (e.g. http://host.docker.internal:11434)
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gpt-oss")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "").strip() or None
