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
SIKAFINANCE_ACTUALITES_URL = "https://www.sikafinance.com/marches/actualites_bourse_brvm"
SIKAFINANCE_COMMUNIQUES_URL = "https://www.sikafinance.com/marches/communiques_brvm"
RICHBOURSE_PREDICTION_URL = "https://www.richbourse.com/common/prevision-boursiere/synthese"
RICHBOURSE_DIVIDENDE_URL = "https://www.richbourse.com/common/dividende/index"
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
if _raw_symbols:
    TIMESERIES_SYMBOLS: list[str] = [s.strip().upper() for s in _raw_symbols.split(",") if s.strip()]
else:
    # Default: use all symbols from app/data/BRVM_Companies.xlsx
    try:
        from app.utils.brvm_companies import get_valid_symbols
        TIMESERIES_SYMBOLS = sorted(get_valid_symbols())
    except Exception:
        TIMESERIES_SYMBOLS = []

# LLM provider: ollama | groq | openrouter
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama").strip().lower() or "ollama"
# Optional: override model for current provider (e.g. LLM_MODEL=llama-3.1-70b)
LLM_MODEL = os.getenv("LLM_MODEL", "").strip() or None
# LLM temperature (0=deterministic, higher=more creative). Default 0.5
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.0").strip() or "0.0")

# Ollama
OLLAMA_CLOUD_HOST = "https://ollama.com"
OLLAMA_API_KEY = os.getenv("OLLAMA_API_KEY", "").strip() or None
OLLAMA_CLOUD = os.getenv("OLLAMA_CLOUD", "").strip().lower() in ("1", "true", "yes")
OLLAMA_CLOUD_MODEL = "glm-5:cloud"
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", OLLAMA_CLOUD_MODEL if OLLAMA_CLOUD else "llama3.2:3b")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "").strip() or None
OLLAMA_KEEP_ALIVE = os.getenv("OLLAMA_KEEP_ALIVE", "2m").strip() or "2m"

# Groq (https://console.groq.com)
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip() or None
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b").strip()

# Graph: max steps before stopping (prevents endless loops)
RECURSION_LIMIT = int(os.getenv("RECURSION_LIMIT", "100").strip() or "100")

# OpenRouter (https://openrouter.ai)
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip() or None
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "arcee-ai/trinity-large-preview:free").strip()
OPENROUTER_SITE_URL = os.getenv("OPENROUTER_SITE_URL", "").strip() or None  # Optional: HTTP-Referer for rankings
OPENROUTER_SITE_NAME = os.getenv("OPENROUTER_SITE_NAME", "").strip() or None  # Optional: X-OpenRouter-Title for rankings
