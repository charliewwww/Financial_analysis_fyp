"""
Reports router — read access to legacy sector analysis reports.

These are the reports produced by the original Streamlit pipeline
(sector-level, 2000-word Markdown essay).  They are kept as a read-only
archive; new analyses produce signal_cards via the signals router.

Endpoints:
    GET  /api/v1/reports                    Paginated list, optional ?sector_id filter
    GET  /api/v1/reports/{report_id}        Full report with deserialized snapshots
    GET  /api/v1/reports/{report_id}/predictions   Prediction rows for one report
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncConnection

from app.core.auth import CurrentUser
from app.db.engine import get_db
from app.db.repositories import predictions as pred_repo
from app.db.repositories import reports as report_repo
from app.schemas.common import PaginatedResponse
from app.schemas.reports import PredictionSchema, ReportDetail, ReportSummary

router = APIRouter(prefix="/reports", tags=["reports"])

# Type alias for the injected DB connection
DB = Annotated[AsyncConnection, Depends(get_db)]


# ── List ───────────────────────────────────────────────────────────

@router.get(
    "/",
    response_model=PaginatedResponse[ReportSummary],
    summary="List reports",
    description=(
        "Returns a paginated list of sector analysis reports, newest first. "
        "Pass `sector_id` to filter to one sector (e.g. `semiconductors`)."
    ),
)
async def list_reports(
    db: DB,
    user: CurrentUser,
    sector_id: str | None = Query(default=None, description="Filter by sector key."),
    market: str | None = Query(default=None, description="us | hk"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> PaginatedResponse[ReportSummary]:
    items, total = await report_repo.list_reports(
        db, sector_id=sector_id, market=market, user_email=user, page=page, page_size=page_size
    )
    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        has_next=(page * page_size) < total,
    )


# ── Detail ─────────────────────────────────────────────────────────

@router.get(
    "/{report_id}",
    response_model=ReportDetail,
    summary="Get report detail",
    description=(
        "Returns a single report with all snapshot data deserialized "
        "(prices, technicals, news, filings, timing) and its predictions."
    ),
)
async def get_report(report_id: int, db: DB, user: CurrentUser) -> ReportDetail:
    report = await report_repo.get_report(db, report_id, user_email=user)
    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report {report_id} not found.",
        )
    return report


# ── Predictions ────────────────────────────────────────────────────

@router.get(
    "/{report_id}/predictions",
    response_model=list[PredictionSchema],
    summary="List predictions for a report",
    description=(
        "Returns all ticker-level predictions recorded when this report was saved. "
        "Predictions with `price_1w_later=null` have not yet been checked by "
        "the weekly accuracy job."
    ),
)
async def get_report_predictions(
    report_id: int, db: DB, user: CurrentUser
) -> list[PredictionSchema]:
    # Verify the report exists and belongs to this user
    report = await report_repo.get_report(db, report_id, user_email=user)
    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report {report_id} not found.",
        )
    return await pred_repo.list_for_report(db, report_id)
