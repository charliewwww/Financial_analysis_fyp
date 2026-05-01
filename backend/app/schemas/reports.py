"""
Report, Prediction, and accuracy-tracking schemas.

Mirrors the PostgreSQL tables that replace database/reports_db.py.
Snapshot columns (prices, technicals, news, filings, timing) are
deserialised into typed dicts — the frontend never receives raw JSON strings.

Endpoints:
    GET  /api/v1/reports                      → PaginatedResponse[ReportSummary]
    GET  /api/v1/reports/{id}                 → ReportDetail
    GET  /api/v1/reports/{id}/predictions     → list[PredictionSchema]
    GET  /api/v1/signals/accuracy             → AccuracyStats
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


# ── Prediction ─────────────────────────────────────────────────────

class PredictionSchema(BaseModel):
    """
    One row from the predictions table.

    A prediction links to EITHER a signal_card (Phase 1+ path) OR a legacy
    report — both FK columns are therefore optional.

    price_1w_later / actual_change_1w / checked_at / prediction_correct are
    null until the weekly accountability-check job runs.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    signal_card_id: int | None = None   # Phase 1+ path
    report_id: int | None = None        # Legacy sector-report path
    ticker: str
    price_at_report: float | None = None
    change_1w_at_report: float | None = None
    # Populated by the weekly accuracy-check job
    price_1w_later: float | None = None
    actual_change_1w: float | None = None
    checked_at: str | None = None
    prediction_correct: bool | None = None
    # AI-generated fields
    ai_direction: str | None = None
    ai_predicted_change: str | None = None
    ai_reasoning: str | None = None
    ai_risk: str | None = None


# ── Report — compact list view ─────────────────────────────────────

class ReportSummary(BaseModel):
    """
    Compact report record for the Reports list page.
    No snapshot blobs — just the columns needed to render a table row.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    sector_id: str
    sector_name: str
    created_at: str
    confidence_score: float | None = None
    validation_status: str | None = None
    data_sufficiency: str | None = None
    news_used: int = 0
    status: str = "active"


# ── Report — full detail view ──────────────────────────────────────

class ReportDetail(BaseModel):
    """
    Full report returned by GET /api/reports/{id}.

    Snapshot columns are stored as JSON text in the DB and deserialized
    into typed structures here so the frontend always gets real objects,
    never raw strings.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    sector_id: str
    sector_name: str
    created_at: str
    analysis: str
    validation: str | None = None
    news_summary: str | None = None
    confidence_score: float | None = None
    validation_status: str | None = None
    data_sufficiency: str | None = None
    news_used: int = 0
    status: str = "active"

    # Deserialized snapshots (list/dict, not raw JSON strings)
    prices_snapshot: list[dict[str, Any]] = Field(default_factory=list)
    technicals_snapshot: list[dict[str, Any]] = Field(default_factory=list)
    news_snapshot: list[dict[str, Any]] = Field(default_factory=list)
    filings_snapshot: list[dict[str, Any]] = Field(default_factory=list)
    timing_snapshot: dict[str, Any] = Field(default_factory=dict)

    predictions: list[PredictionSchema] = Field(default_factory=list)


# ── Accuracy stats ─────────────────────────────────────────────────

class SignalTypeBreakdown(BaseModel):
    """Per-signal-type accuracy bucket. Populated in Phase 2 once signal_type is set."""

    total: int = 0
    correct: int = 0
    accuracy_pct: float | None = None


class AccuracyStats(BaseModel):
    """
    Aggregated prediction accuracy — drives the Track Record page (Phase 2.3).

    Returned by GET /api/v1/signals/accuracy.

    direction_accuracy_pct is None when no predictions have been checked yet.
    by_signal_type is empty until Phase 2 signal_type classification is live.
    """

    total: int = 0
    checked: int = 0
    unchecked: int = 0
    direction_correct: int = 0
    direction_incorrect: int = 0
    direction_accuracy_pct: float | None = None
    avg_absolute_error_pct: float | None = None
    # Keyed by signal_type value: FUNDAMENTAL_SHIFT | MEDIA_NARRATIVE | TECHNICAL_ONLY
    by_signal_type: dict[str, SignalTypeBreakdown] = Field(default_factory=dict)
