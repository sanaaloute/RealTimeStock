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
RICHBOURSE_NEWS_URL = "https://www.richbourse.com/common/news/index"
SIKAFINANCE_BOURSE_URL = "https://www.sikafinance.com/bourse/"
BRVM_URL = "https://www.brvm.org/"
BRVM_ANNOUNCEMENTS_URL = "https://www.brvm.org/fr/emetteurs/type-annonces/convocations-assemblees-generales"

# Telegram bot (run_telegram_bot.py)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
# Comma-separated Telegram user IDs (e.g. 123456789,987654321). Only these users can use the bot.
ALLOWED_TELEGRAM_IDS: list[int] = []
_raw = os.getenv("ALLOWED_TELEGRAM_IDS", "").strip()
if _raw:
    for s in _raw.replace(" ", "").split(","):
        if s.isdigit():
            ALLOWED_TELEGRAM_IDS.append(int(s))

# Timeseries CSV: symbols to keep up to date (daily); comma-separated, or empty to use default BRVM list
_raw_symbols = os.getenv("TIMESERIES_SYMBOLS", "").strip()
TIMESERIES_SYMBOLS: list[str] = [s.strip().upper() for s in _raw_symbols.split(",") if s.strip()] if _raw_symbols else [
    "NTLC", "SLBC", "SNTS", "TTLS", "CFA", "BOAB", "BICC", "SDSC", "SDCC", "FTSC", "CAGC", "TLSR", "ETIT", "SGBC", "NEIC", "SMBC", "CBIBF", "ECOC", "BRVM"
]

# Ollama (agent + redact)
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gpt-oss")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "").strip() or None
