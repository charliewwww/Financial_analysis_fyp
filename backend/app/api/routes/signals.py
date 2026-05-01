"""
Signals router — the Phase 1+ primary output surface.

Signal cards are the structured, per-ticker verdicts produced by the new
pipeline (signal, conviction, validated numerical claims, supply chain impact).
This router is what the Morning Brief, Board of Analysts, and Track Record
pages in the Next.js frontend consume.

Endpoints:
    GET  /api/v1/signals                        Paginated list with filters
    GET  /api/v1/signals/accuracy               Track Record stats (Phase 2.3)
    GET  /api/v1/signals/latest/{ticker}        Most recent signal for a ticker
    GET  /api/v1/signals/{card_id}              Full signal card
    GET  /api/v1/signals/{card_id}/predictions  Predictions for a signal card

Path ordering matters: static segments (`/accuracy`, `/latest/{ticker}`)
must be declared BEFORE `/{card_id}` so FastAPI's router doesn't try to
interpret "accuracy" as an integer card ID.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncConnection

from app.core.auth import CurrentUser
from app.db.engine import get_db
from app.db.repositories import predictions as pred_repo
from app.db.repositories import signals as signal_repo
from app.schemas.analysis import SignalCardSchema
from app.schemas.common import PaginatedResponse
from app.schemas.reports import AccuracyStats, PredictionSchema

router = APIRouter(prefix="/signals", tags=["signals"])

DB = Annotated[AsyncConnection, Depends(get_db)]


# ── Accuracy stats  (declared first — static path) ─────────────────

@router.get(
    "/accuracy",
    response_model=AccuracyStats,
    summary="Prediction accuracy stats",
    description=(
        "Aggregated directional accuracy across all checked predictions. "
        "Drives the Track Record page (Phase 2.3). "
        "`direction_accuracy_pct` is null until at least one prediction "
        "has been verified by the weekly accuracy-check job."
    ),
)
async def get_accuracy(db: DB, user: CurrentUser) -> AccuracyStats:
    return await pred_repo.get_accuracy_stats(db)


# ── Latest signal for a ticker  (declared before /{card_id}) ────────

@router.get(
    "/latest/{ticker}",
    response_model=SignalCardSchema,
    summary="Latest signal for a ticker",
    description=(
        "Returns the most recent signal card for the given ticker symbol. "
        "Pass `agent_id` to scope to a specific analyst agent "
        "(e.g. the Supply Chain Analyst)."
    ),
)
async def get_latest_signal(
    ticker: str,
    db: DB,
    user: CurrentUser,
    agent_id: int | None = Query(
        default=None,
        description="Scope to a specific agent. Omit for the system default.",
    ),
) -> SignalCardSchema:
    card = await signal_repo.get_latest_signal(
        db, ticker.upper(), agent_id=agent_id, user_email=user
    )
    if card is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No signal found for ticker '{ticker.upper()}'.",
        )
    return card


# ── Paginated list with filters ────────────────────────────────────

@router.get(
    "/",
    response_model=PaginatedResponse[SignalCardSchema],
    summary="List signal cards",
    description=(
        "Paginated list of signal cards, newest first. "
        "All query parameters are optional and combinable:\n"
        "- `ticker` — filter to a single ticker\n"
        "- `signal` — BULLISH | BEARISH | NEUTRAL\n"
        "- `signal_type` — FUNDAMENTAL_SHIFT | MEDIA_NARRATIVE | TECHNICAL_ONLY\n"
        "- `agent_id` — filter to a specific analyst agent\n\n"
        "These filters power the Morning Brief filter panel (Phase 2 — User Insight Explorer)."
    ),
)
async def list_signals(
    db: DB,
    user: CurrentUser,
    ticker: str | None = Query(default=None, description="e.g. 'NVDA' or '0700.HK'"),
    signal: str | None = Query(default=None, description="BULLISH | BEARISH | NEUTRAL"),
    signal_type: str | None = Query(
        default=None,
        description="FUNDAMENTAL_SHIFT | MEDIA_NARRATIVE | TECHNICAL_ONLY",
    ),
    agent_id: int | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> PaginatedResponse[SignalCardSchema]:
    items, total = await signal_repo.list_signal_cards(
        db,
        ticker=ticker,
        signal=signal,
        signal_type=signal_type,
        agent_id=agent_id,
        user_email=user,
        page=page,
        page_size=page_size,
    )
    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        has_next=(page * page_size) < total,
    )


# ── Signal card detail ─────────────────────────────────────────────

@router.get(
    "/{card_id}",
    response_model=SignalCardSchema,
    summary="Get signal card",
    description=(
        "Returns the full signal card including all numerical claims, "
        "sources, and supply chain impact entries."
    ),
)
async def get_signal_card(card_id: int, db: DB, user: CurrentUser) -> SignalCardSchema:
    card = await signal_repo.get_signal_card(db, card_id, user_email=user)
    if card is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Signal card {card_id} not found.",
        )
    return card


# ── Predictions for a signal card ─────────────────────────────────

@router.get(
    "/{card_id}/predictions",
    response_model=list[PredictionSchema],
    summary="Predictions for a signal card",
    description=(
        "Returns all price predictions recorded when this signal card was created. "
        "The `prediction_correct` field is null until the weekly accuracy job runs."
    ),
)
async def get_signal_predictions(
    card_id: int, db: DB, user: CurrentUser
) -> list[PredictionSchema]:
    card = await signal_repo.get_signal_card(db, card_id, user_email=user)
    if card is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Signal card {card_id} not found.",
        )
    return await pred_repo.list_for_signal_card(db, card_id)
