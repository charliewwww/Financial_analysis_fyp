"""
Global settings — loaded from .env file.
Everything configurable lives here. Change model, thresholds, etc. in one place.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ── LLM Provider Toggle ───────────────────────────────────────────
# Set LLM_PROVIDER in .env to switch between cloud and local:
#   LLM_PROVIDER=openrouter   → use OpenRouter API (dev mode, fast iteration)
#   LLM_PROVIDER=ollama       → use local Ollama server (production, $0/month)
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openrouter").lower()

# ── LLM (OpenRouter — development) ────────────────────────────────
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# ── LLM (Ollama — local production) ───────────────────────────────
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")

# ── Model Selection ───────────────────────────────────────────────
# GLM-4.7-Flash: fast, free on both OpenRouter and Ollama.
# Same model on both providers — ensures identical behavior.
if LLM_PROVIDER == "ollama":
    LLM_BASE_URL = OLLAMA_BASE_URL
    LLM_API_KEY = "ollama"  # Ollama doesn't need a real key
    REASONING_MODEL = os.getenv("REASONING_MODEL", "glm4")
    FAST_MODEL = os.getenv("FAST_MODEL", "glm4")
else:
    LLM_BASE_URL = OPENROUTER_BASE_URL
    LLM_API_KEY = OPENROUTER_API_KEY
    REASONING_MODEL = os.getenv("REASONING_MODEL", "z-ai/glm-4.7-flash")
    FAST_MODEL = os.getenv("FAST_MODEL", "z-ai/glm-4.7-flash")

# ── FRED (Federal Reserve Economic Data) ──────────────────────────
# Free API key from https://fred.stlouisfed.org/docs/api/api_key.html
# Provides macroeconomic indicators (Fed Funds rate, CPI, GDP, etc.)
# Optional: pipeline works without it, but macro context enriches analysis
FRED_API_KEY = os.getenv("FRED_API_KEY", "")

# ── SEC EDGAR ──────────────────────────────────────────────────────
# SEC requires a User-Agent with your email. No account needed.
# Anyone worldwide can use it. It's just so they can contact you
# if your script is sending too many requests.
SEC_EDGAR_EMAIL = os.getenv("SEC_EDGAR_EMAIL", "")
SEC_EDGAR_BASE_URL = "https://efts.sec.gov/LATEST"
SEC_EDGAR_FILINGS_URL = "https://www.sec.gov/cgi-bin/browse-edgar"

# ── Validation Thresholds ─────────────────────────────────────────
# If a number in the analysis differs from real data by more than this %,
# flag it as potentially wrong
NUMERICAL_TOLERANCE_PCT = 5.0  # Tightened: 5% catches real errors while allowing rounding

# ── LLM Retry ─────────────────────────────────────────────────────
# Exponential backoff for transient API errors (rate-limit, timeout, 5xx)
LLM_MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "3"))
LLM_RETRY_BASE_DELAY = float(os.getenv("LLM_RETRY_BASE_DELAY", "2.0"))  # seconds

# Confidence score range
CONFIDENCE_MIN = 1
CONFIDENCE_MAX = 10

# ── Token Budget ──────────────────────────────────────────────────
# Max characters for the assembled analysis prompt (prevents silent truncation)
# GLM-4.7-Flash context window is ~128K tokens; we target ~60K chars (~15K tokens)
# to leave plenty of room for system prompt + response while avoiding data loss.
MAX_PROMPT_CHARS = int(os.getenv("MAX_PROMPT_CHARS", "60000"))

# ── Database ──────────────────────────────────────────────────────
DATABASE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "reports.db")
MAX_REPORTS = int(os.getenv("MAX_REPORTS", "50"))  # Auto-purge oldest beyond this

# ── Langfuse Observability (optional) ─────────────────────────────
# Set all 3 to enable LLM tracing in Langfuse.  Leave blank to disable.
LANGFUSE_PUBLIC_KEY = os.getenv("LANGFUSE_PUBLIC_KEY", "")
LANGFUSE_SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY", "")
LANGFUSE_HOST = os.getenv("LANGFUSE_HOST", "https://us.cloud.langfuse.com")
LANGFUSE_ENABLED = bool(LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY)

# ── RSS Fetch ─────────────────────────────────────────────────────
# Max articles per feed to fetch (keeps things fast)
MAX_ARTICLES_PER_FEED = 10
# Max age of news articles in days (ignore older stuff)
NEWS_MAX_AGE_DAYS = 7
