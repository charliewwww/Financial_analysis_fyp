"""
Backend settings — loaded from the project .env via pydantic-settings.

Mirrors config/settings.py from the Streamlit app but uses pydantic-settings
so every value is typed, validated, and IDE-autocomplete-friendly.

Usage anywhere in the backend:
    from app.core.config import settings
    print(settings.reasoning_model)
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # The .env file lives one level above backend/
        env_file="../.env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── LLM Provider ──────────────────────────────────────────────
    llm_provider: Literal["openrouter", "ollama", "deepseek"] = "openrouter"
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    ollama_base_url: str = "http://localhost:11434/v1"
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"

    # ── Model Selection ───────────────────────────────────────────
    reasoning_model: str = "google/gemma-4-31b-it"
    fast_model: str = "google/gemma-4-31b-it"
    llm_max_retries: int = 3
    llm_retry_base_delay: float = 2.0

    # ── Database ──────────────────────────────────────────────────
    # PostgreSQL (production): postgresql+asyncpg://user:pass@host/dbname
    # SQLite   (local dev):    sqlite+aiosqlite:///./dev.db  (no setup needed)
    database_url: str = "sqlite+aiosqlite:///./dev.db"

    # ── ChromaDB ──────────────────────────────────────────────────
    chroma_path: str = "./chroma_db"

    # ── External APIs ─────────────────────────────────────────────
    fred_api_key: str = ""
    sec_edgar_email: str = ""

    # ── Validation thresholds ─────────────────────────────────────
    numerical_tolerance_pct: float = 5.0

    # ── Pipeline execution ───────────────────────────────────────
    # The legacy analysis pipeline is blocking and runs in a thread pool.
    # A full sector board can be 10 tickers x 4 analysts, so the default
    # allows that product workflow to run in one wave instead of queuing.
    pipeline_max_workers: int = Field(
        default=48,
        ge=1,
        le=128,
        description="Maximum concurrent blocking pipeline runs.",
    )

    # A single client must not be able to flood the thread pool. A full sector
    # board is ~10 tickers x 4 analysts = 40 runs, so the default leaves
    # headroom for one board plus a few ad-hoc runs before returning HTTP 429.
    pipeline_max_active_runs_per_user: int = Field(
        default=60,
        ge=1,
        le=500,
        description="Max pending+running pipeline runs a single user may hold.",
    )

    # Each live run owns an in-memory SSE event queue. Cap its size so a run
    # whose stream is never consumed (or is consumed slowly) cannot grow
    # unbounded; on overflow the oldest event is dropped (drop-oldest).
    sse_queue_maxsize: int = Field(
        default=1000,
        ge=16,
        le=100_000,
        description="Max buffered SSE events per run before dropping oldest.",
    )

    # Queues whose SSE stream is never opened would otherwise leak forever.
    # The runner reaps queues older than this TTL on each new launch.
    sse_queue_orphan_ttl_seconds: int = Field(
        default=900,
        ge=30,
        le=86_400,
        description="Drop SSE queues older than this many seconds (orphans).",
    )

    # ── Observability (Langfuse) ──────────────────────────────────
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "https://cloud.langfuse.com"

    # ── CORS ──────────────────────────────────────────────────────
    # Add the Next.js dev origin; extend in .env for production.
    cors_origins: list[str] = Field(
        default=["http://localhost:3000"],
        description="Allowed origins for CORS. The Next.js dev server runs on :3000.",
    )

    # ── Auth ──────────────────────────────────────────────────────
    # Cloudflare Access passes the verified email in a header.
    # In local development (no CF tunnel), set this to any email string to
    # bypass the header check entirely.  Leave empty in production.
    auth_bypass_email: str = Field(
        default="",
        description=(
            "When non-empty, all requests are treated as this user. "
            "NEVER set in production — Cloudflare Access must be the gate."
        ),
    )

    # ── Environment ───────────────────────────────────────────────
    # Controls dev-mode safety nets (e.g. auth fallback).
    # Set APP_ENV=production in production deployments.
    app_env: Literal["development", "production"] = Field(
        default="development",
        description=(
            "Runtime environment. In 'development', missing CF headers fall "
            "back to test@example.com instead of raising 401. "
            "Set to 'production' when deploying behind Cloudflare Access."
        ),
    )

    # ── Backtester / accountability scheduler ─────────────────────
    # A background job matures predictions and house verdicts into verified
    # outcomes (the Track Record engine). Disable in tests/CI.
    scheduler_enabled: bool = Field(
        default=True,
        description="Run the daily outcome-resolution job on startup.",
    )
    resolution_interval_hours: int = Field(
        default=24,
        ge=1,
        le=168,
        description="Hours between automatic outcome-resolution runs.",
    )

    # ── Stale-run reaper ──────────────────────────────────────
    # The pipeline runs in an in-process thread pool, so a run still marked
    # pending/running after a crash/restart is an orphan. On startup ALL such
    # runs are failed; a periodic sweep also fails any run that has been
    # in-flight longer than this many minutes (a hung worker safety net).
    stale_run_timeout_minutes: int = Field(
        default=30,
        ge=1,
        le=1440,
        description="Fail runs still in-flight after this many minutes.",
    )
    stale_run_sweep_minutes: int = Field(
        default=5,
        ge=1,
        le=120,
        description="How often the stale-run reaper sweeps.",
    )

    # ── Authentication (self-hosted Google OIDC sign-in) ─────────
    # Google OAuth 2.0 / OpenID Connect credentials. Create them at
    # https://console.cloud.google.com/apis/credentials . Required in
    # production; when empty, only the dev bypass / dev fallback path works.
    google_client_id: str = ""
    google_client_secret: str = ""

    # Secret that signs the short-lived OAuth transaction cookie (state + nonce
    # during the Google redirect). Must be a long random string in production;
    # a blank value disables the real login flow.
    session_secret_key: str = ""

    # The logged-in session cookie. It carries only an opaque random token; the
    # row lives in user_sessions and we persist just the token's hash.
    session_cookie_name: str = "mp_session"
    session_ttl_days: int = Field(default=30, ge=1, le=365)
    # Set False only for local HTTP development; True everywhere served on HTTPS.
    cookie_secure: bool = True
    # 'lax' (recommended, CSRF-resistant) | 'strict' | 'none' (cross-site, needs Secure).
    cookie_samesite: Literal["lax", "strict", "none"] = "lax"
    # Optional explicit cookie domain (e.g. ".example.com"). Empty = host-only.
    cookie_domain: str = ""

    # Where to send the browser after login/logout (the frontend origin).
    frontend_base_url: str = "http://localhost:3000"
    # Public backend URL used to build the OAuth callback. Empty = infer from the
    # incoming request (fine locally; set explicitly when behind a proxy/CDN).
    backend_base_url: str = ""

    # Emails that are always allowed AND granted admin on first sign-in. Seeds
    # the first operator without editing code. Comma-separated in .env.
    auth_bootstrap_admin_emails: str = Field(
        default="",
        description=(
            "Comma-separated emails always allowed and granted admin on first "
            "sign-in (bootstrap operator)."
        ),
    )

    # ── Usage quota (app-provided AI) ────────────────────────────
    # Free analyses a single user may START per UTC day. 0 disables the cap.
    daily_run_quota: int = Field(default=25, ge=0, le=100_000)

    @property
    def bootstrap_admin_emails(self) -> list[str]:
        """Parsed, normalized list of bootstrap-admin emails."""
        return [
            e.strip().lower()
            for e in self.auth_bootstrap_admin_emails.split(",")
            if e.strip()
        ]


# Single shared instance — import this everywhere.
settings = Settings()
