"""
Alpha Lens — FastAPI application entry point.

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

from app.core.config import settings
from app.db.engine import dispose_engine, init_engine
from app.db.tables import create_all_tables
from app.schemas.common import HealthResponse

logger = logging.getLogger(__name__)


# ── Lifespan ───────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """
    Manage resources that live for the entire application lifetime.

    Startup order matters — engine must exist before tables are created.
    """
    # ── startup ──────────────────────────────────────────────────
    logger.info("Initialising database engine → %s", settings.database_url)
    engine = init_engine()
    await create_all_tables(engine)
    logger.info("Database tables ready.")

    # Future pieces attach to app.state here, e.g.:
    #   app.state.chroma = init_chroma_client()  (Piece 3 — ChromaDB)
    #   app.state.graph  = build_langgraph()      (Piece 4 — pipeline)

    yield

    # ── shutdown ─────────────────────────────────────────────────
    logger.info("Disposing database engine.")
    await dispose_engine()


# ── App ────────────────────────────────────────────────────────────

app = FastAPI(
    title="Alpha Lens API",
    version="0.1.0",
    description=(
        "Market intelligence pipeline — real-data signal engine. "
        "FastAPI backend for the Alpha Lens Next.js frontend."
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


# ── System routes ──────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse, tags=["system"])
async def health() -> HealthResponse:
    """Liveness probe. Returns 200 if the process is up."""
    return HealthResponse(status="ok", version=app.version)


# ── Feature routers (registered as each piece is built) ───────────

from app.api.routes import (  # noqa: E402
    evaluations,
    pipeline,
    reports,
    sectors,
    signals,
    supply_chain,
    system,
    users,
)

app.include_router(reports.router, prefix="/api/v1")
app.include_router(signals.router, prefix="/api/v1")
app.include_router(pipeline.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
app.include_router(sectors.router, prefix="/api/v1")
app.include_router(supply_chain.router, prefix="/api/v1")
app.include_router(system.router, prefix="/api/v1")
app.include_router(evaluations.router, prefix="/api/v1")

# Future pieces:
# from app.api.routes import watchlist, agents
# app.include_router(watchlist.router, prefix="/api/v1")
