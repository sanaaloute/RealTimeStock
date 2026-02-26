"""Configuration for scrapers and Telegram bot."""
import os
from dotenv import load_dotenv

load_dotenv()

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
SLEEP_SECONDS = float(os.getenv("SCRAPER_SLEEP_SECONDS", "2"))

SIKAFINANCE_URL = "https://www.sikafinance.com/"
SIKAFINANCE_PALMARES_URL = "https://www.sikafinance.com/marches/palmares"
RICHBOURSE_URL = "https://www.richbourse.com/common/variation/index"
RICHBOURSE_NEWS_URL = "https://www.richbourse.com/common/news/index"
SIKAFINANCE_BOURSE_URL = "https://www.sikafinance.com/bourse/"
BRVM_URL = "https://www.brvm.org/"
BRVM_ANNOUNCEMENTS_URL = "https://www.brvm.org/fr/emetteurs/type-annonces/convocations-assemblees-generales"

BRVM_API_URL = os.getenv("BRVM_API_URL", "http://localhost:8000").rstrip("/")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
ALLOWED_TELEGRAM_IDS: list[int] = []
_raw = os.getenv("ALLOWED_TELEGRAM_IDS", "").strip()
if _raw:
    for s in _raw.replace(" ", "").split(","):
        if s.isdigit():
            ALLOWED_TELEGRAM_IDS.append(int(s))

_raw_symbols = os.getenv("TIMESERIES_SYMBOLS", "").strip()
TIMESERIES_SYMBOLS: list[str] = [s.strip().upper() for s in _raw_symbols.split(",") if s.strip()] if _raw_symbols else [
    "NTLC", "SLBC", "SNTS", "TTLS", "CFA", "BOAB", "BICC", "SDSC", "SDCC", "FTSC", "CAGC", "TLSR", "ETIT", "SGBC", "NEIC", "SMBC", "CBIBF", "ECOC", "BRVM"
]

OLLAMA_CLOUD_HOST = "https://ollama.com"
OLLAMA_API_KEY = os.getenv("OLLAMA_API_KEY", "").strip() or None
OLLAMA_CLOUD = os.getenv("OLLAMA_CLOUD", "").strip().lower() in ("1", "true", "yes")
OLLAMA_CLOUD_MODEL = "glm-5:cloud"
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", OLLAMA_CLOUD_MODEL if OLLAMA_CLOUD else "glm-5:cloud")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "").strip() or None
OLLAMA_KEEP_ALIVE = os.getenv("OLLAMA_KEEP_ALIVE", "2m").strip() or "2m"
