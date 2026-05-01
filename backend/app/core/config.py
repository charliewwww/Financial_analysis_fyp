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
    llm_provider: Literal["openrouter", "ollama"] = "openrouter"
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    ollama_base_url: str = "http://localhost:11434/v1"

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


# Single shared instance — import this everywhere.
settings = Settings()
