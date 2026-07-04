"""
MarketPulse — FastAPI application entry point.

Startup / shutdown lifecycle (lifespan):
    1. Initialise the AsyncEngine (asyncpg pool)
    2. Create all tables if they don't exist (idempotent)
    3. Dispose pool on shutdown

Routers are registered under /api/v1 and added piece by piece.
Only /health exists right now — every subsequent piece adds a router.

Run locally:
    cd backend
    uvicorn app.main:app --reload --port 8000
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app.core.config import settings
from app.db.engine import dispose_engine, init_engine
from app.db.repositories import agents as agent_repo
from app.db.repositories import signals as signal_repo
from app.db.tables import create_all_tables
from app.schemas.common import HealthResponse
from app.services.scheduler import start_scheduler, stop_scheduler

logger = logging.getLogger(__name__)


async def _reconcile_orphaned_runs(engine) -> None:
    """Fail any runs left pending/running by a previous process (orphans).

    The pipeline executes in an in-process thread pool, so none can have
    survived a restart — mark them failed so they never appear "stuck".
    """
    async with engine.begin() as conn:
        reaped = await signal_repo.fail_stale_runs(conn)
    if reaped:
        logger.info("Reconciled %d orphaned pipeline run(s) as failed.", reaped)


# ── Lifespan ───────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """
    Manage resources that live for the entire application lifetime.

    Startup order matters — engine must exist before tables are created.
    """
    # ── startup ──────────────────────────────────────────────────
    # Fail fast on an unsafe production config. In production we require a real
    # authentication gate and forbid the dev bypass, so a misconfiguration can
    # never silently let every request impersonate one user.
    if settings.app_env == "production":
        if settings.auth_bypass_email:
            raise RuntimeError(
                "AUTH_BYPASS_EMAIL must be empty when APP_ENV=production."
            )
        missing = [
            name
            for name, value in (
                ("GOOGLE_CLIENT_ID", settings.google_client_id),
                ("GOOGLE_CLIENT_SECRET", settings.google_client_secret),
                ("SESSION_SECRET_KEY", settings.session_secret_key),
            )
            if not value
        ]
        if missing:
            raise RuntimeError(
                "APP_ENV=production requires real authentication to be "
                f"configured. Missing: {', '.join(missing)}."
            )

    logger.info("Initialising database engine → %s", settings.database_url)
    engine = init_engine()
    await create_all_tables(engine)
    await agent_repo.ensure_builtin_agents_for_engine(engine)
    await _reconcile_orphaned_runs(engine)
    logger.info("Database tables ready.")

    # Track Record engine: a daily job matures predictions / house verdicts
    # into verified outcomes.
    start_scheduler(app)

    yield

    # ── shutdown ─────────────────────────────────────────────────
    stop_scheduler(app)
    logger.info("Disposing database engine.")
    await dispose_engine()


# ── App ────────────────────────────────────────────────────────────

app = FastAPI(
    title="MarketPulse API",
    version="0.1.0",
    description=(
        "Market intelligence pipeline — real-data signal engine. "
        "FastAPI backend for the MarketPulse Next.js frontend."
    ),
    lifespan=lifespan,
    # Disable the default /docs redirect so CORS isn't an issue during dev
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)


# ── CORS ───────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Session middleware (OAuth transaction state during Google sign-in) ──
# Only the short-lived state/nonce of the login redirect live in this cookie;
# the logged-in session itself is a separate HttpOnly cookie backed by the DB
# (see app/core/auth.py). Added only when a session secret is configured.
if settings.session_secret_key:
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.session_secret_key,
        session_cookie="mp_oauth",
        https_only=settings.cookie_secure,
        same_site=settings.cookie_samesite,
        max_age=600,  # 10 minutes is plenty for the redirect round-trip
    )


# ── System routes ──────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse, tags=["system"])
async def health() -> HealthResponse:
    """Liveness probe. Returns 200 if the process is up."""
    return HealthResponse(status="ok", version=app.version)


# ── Feature routers (registered as each piece is built) ───────────

from app.api.routes import (  # noqa: E402
    admin,
    agents,
    auth,
    evaluations,
    markets,
    pipeline,
    reports,
    sectors,
    signals,
    supply_chain,
    system,
    users,
    watchlist,
)

app.include_router(auth.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")
app.include_router(reports.router, prefix="/api/v1")
app.include_router(signals.router, prefix="/api/v1")
app.include_router(pipeline.router, prefix="/api/v1")
app.include_router(agents.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
app.include_router(sectors.router, prefix="/api/v1")
app.include_router(markets.router, prefix="/api/v1")
app.include_router(supply_chain.router, prefix="/api/v1")
app.include_router(system.router, prefix="/api/v1")
app.include_router(evaluations.router, prefix="/api/v1")
app.include_router(watchlist.router, prefix="/api/v1")

# Future pieces:
