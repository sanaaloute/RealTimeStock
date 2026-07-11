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

# Market data cache: palmarès page is scraped at most once per TTL (stale snapshot
# is served if a refresh fails). Default 300s = 5 minutes.
PALMARES_CACHE_TTL_SECONDS = float(os.getenv("PALMARES_CACHE_TTL_SECONDS", "300"))

# Chat API: cap concurrent agent runs; extra requests wait up to AGENT_QUEUE_TIMEOUT
# then get a friendly "busy" reply instead of melting the LLM backend.
MAX_CONCURRENT_AGENTS = int(os.getenv("MAX_CONCURRENT_AGENTS", "4"))
AGENT_QUEUE_TIMEOUT = float(os.getenv("AGENT_QUEUE_TIMEOUT", "60"))

# Security: shared secret the bot sends as X-API-Key to call the Chat API.
# Empty = dev mode (no auth, warning logged). MUST be set in production.
API_SECRET_KEY = os.getenv("API_SECRET_KEY", "").strip()

# Coarse per-user rate limit on /chat (requests per minute). 0 = disabled.
RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "30"))

# Free daily quota on /chat (requests per user per UTC day). 0 = unlimited.
# Failed requests are refunded; rate-limited/busy rejections never count.
DAILY_FREE_QUOTA = int(os.getenv("DAILY_FREE_QUOTA", "30"))
# Comma-separated user ids exempt from the daily quota (owner/testers).
# Accepts raw Telegram ids or channel keys like "wa:22507000000".
QUOTA_EXEMPT_IDS = {s.strip() for s in os.getenv("QUOTA_EXEMPT_IDS", "").split(",") if s.strip()}

# WhatsApp Business Cloud API channel. All three required to enable; the webhook
# (GET/POST /whatsapp/webhook) must be reachable over public HTTPS from Meta.
WHATSAPP_VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "").strip()
WHATSAPP_ACCESS_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN", "").strip()
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "").strip()
WHATSAPP_ENABLED = bool(WHATSAPP_VERIFY_TOKEN and WHATSAPP_ACCESS_TOKEN and WHATSAPP_PHONE_NUMBER_ID)
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
