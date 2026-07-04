"""
Reports repository — async equivalents of all operations in database/reports_db.py.

This is the ONLY place in the backend that touches the `reports` table.
All callers use this module; no raw SQL outside of db/.

Operations:
    list_reports(db, *, sector_id, page, page_size)  → (items, total)
    get_report(db, report_id)                         → ReportDetail | None
    create_report_from_state(db, state)               → int (report_id)
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, insert, select
from sqlalchemy.ext.asyncio import AsyncConnection

from app.db.tables import predictions, reports
from app.schemas.reports import PredictionSchema, ReportDetail, ReportSummary

# Columns returned for list views — excludes large JSONB blobs
_LIST_COLS = [
    reports.c.id,
    reports.c.sector_id,
    reports.c.sector_name,
    reports.c.created_at,
    reports.c.confidence_score,
    reports.c.validation_status,
    reports.c.data_sufficiency,
    reports.c.news_used,
    reports.c.status,
]


def _normalize_ts(value: Any) -> str:
    """Convert a datetime or string timestamp to an ISO string."""
    if value is None:
        return ""
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _coerce_jsonb(value: Any, default: Any) -> Any:
    """
    asyncpg returns JSONB as Python dicts/lists natively.
    Legacy rows (migrated from SQLite) may still have TEXT — parse those.
    """
    if value is None:
        return default
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, ValueError):
            return default
    return value


# ── List ───────────────────────────────────────────────────────────

async def list_reports(
    db: AsyncConnection,
    *,
    sector_id: str | None = None,
    market: str | None = None,
    user_email: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[ReportSummary], int]:
    """
    Paginated list of reports for the Reports page.
    Returns only lightweight columns — no snapshot blobs.
    Scoped to the requesting user; legacy rows (user_email IS NULL) are shared.

    `market` ('us' | 'hk') keeps a Hong Kong session free of US reports and
    vice-versa. HK sectors are prefixed 'hk_'; everything else counts as US
    (so legacy, non-prefixed sector ids stay visible in the US view).
    """
    base = select(*_LIST_COLS).order_by(reports.c.created_at.desc())
    count_q = select(func.count()).select_from(reports)

    if user_email:
        user_filter = (
            (reports.c.user_email == user_email)
            | (reports.c.user_email.is_(None))
        )
        base = base.where(user_filter)
        count_q = count_q.where(user_filter)

    if sector_id:
        base = base.where(reports.c.sector_id == sector_id)
        count_q = count_q.where(reports.c.sector_id == sector_id)

    if market:
        m = market.strip().lower()
        if m == "hk":
            base = base.where(reports.c.sector_id.like("hk_%"))
            count_q = count_q.where(reports.c.sector_id.like("hk_%"))
        elif m == "us":
            base = base.where(reports.c.sector_id.notlike("hk_%"))
            count_q = count_q.where(reports.c.sector_id.notlike("hk_%"))

    total: int = (await db.execute(count_q)).scalar_one()
    rows = (
        await db.execute(base.limit(page_size).offset((page - 1) * page_size))
    ).mappings().all()

    items = []
    for r in rows:
        d = dict(r)
        d["created_at"] = _normalize_ts(d.get("created_at"))
        items.append(ReportSummary.model_validate(d))

    return items, total


# ── Detail ─────────────────────────────────────────────────────────

async def get_report(
    db: AsyncConnection,
    report_id: int,
    user_email: str | None = None,
) -> ReportDetail | None:
    """
    Full report detail including deserialized snapshot columns and predictions.
    Used by GET /api/reports/{id}.
    When user_email is provided the row must belong to that user or be legacy.
    """
    q = select(reports).where(reports.c.id == report_id)
    if user_email:
        q = q.where(
            (reports.c.user_email == user_email)
            | (reports.c.user_email.is_(None))
        )
    row = (await db.execute(q)).mappings().first()

    if row is None:
        return None

    data = dict(row)
    data["created_at"] = _normalize_ts(data.get("created_at"))

    # Normalize JSONB / legacy TEXT snapshot columns
    for col in ("prices_snapshot", "technicals_snapshot", "news_snapshot", "filings_snapshot"):
        data[col] = _coerce_jsonb(data.get(col), [])
    data["timing_snapshot"] = _coerce_jsonb(data.get("timing_snapshot"), {})

    # Fetch associated predictions
    pred_rows = (
        await db.execute(
            select(predictions)
            .where(predictions.c.report_id == report_id)
            .order_by(predictions.c.ticker)
        )
    ).mappings().all()

    data["predictions"] = [
        PredictionSchema.model_validate({
            **dict(r),
            "checked_at": _normalize_ts(dict(r).get("checked_at")),
        })
        for r in pred_rows
    ]

    return ReportDetail.model_validate(data)


# ── Create ─────────────────────────────────────────────────────────

async def create_report_from_state(
    db: AsyncConnection,
    state: Any,
    user_email: str | None = None,
) -> int:
    """
    Async equivalent of reports_db.save_report_from_state().

    Inserts a report row + prediction rows from a completed PipelineState.
    Returns the new report ID.

    NOTE: In Phase 1, the pipeline primarily produces signal_cards.
    This function is kept for backward compatibility and the legacy sector
    analysis flow.  Use signals.create_signal_card() for the new output path.
    """
    now = datetime.now(timezone.utc)

    news_dicts = [
        {
            "title": a.title,
            "source": a.source,
            "link": a.link,
            "published": a.published,
            "summary": a.raw_summary,
            "condensed_summary": a.condensed_summary,
            "relevance": a.relevance_tag,
            "used_in_analysis": a.used_in_analysis,
        }
        for a in state.articles
    ]

    timing = {
        "total_seconds": state.total_duration_seconds,
        "steps": [
            {"name": n.node_name, "seconds": n.duration_seconds}
            for n in state.node_executions
        ],
    }

    result = await db.execute(
        insert(reports)
        .values(
            sector_id=state.sector_id,
            sector_name=state.sector_name,
            created_at=now,
            analysis=state.analysis_text,
            validation=state.validation_text,
            confidence_score=state.confidence_score,
            prices_snapshot=state.prices,
            technicals_snapshot=state.technicals,
            news_snapshot=news_dicts,
            filings_snapshot=state.filings,
            timing_snapshot=timing,
            news_used=len(state.articles),
            pipeline_state=state.to_dict(),
            news_summary=state.news_summary,
            data_sufficiency=state.data_sufficiency,
            validation_status=state.validation_status,
            user_email=user_email,
        )
        .returning(reports.c.id)
    )
    report_id: int = result.scalar_one()

    ai_pred_map = {p["ticker"]: p for p in getattr(state, "ai_predictions", [])}

    for p in state.prices:
        if p.get("error") or not p.get("price"):
            continue
        ai = ai_pred_map.get(p["ticker"], {})
        await db.execute(
            insert(predictions).values(
                report_id=report_id,
                ticker=p["ticker"],
                price_at_report=p["price"],
                change_1w_at_report=p.get("change_1w_pct"),
                ai_direction=ai.get("direction"),
                ai_predicted_change=ai.get("predicted_change"),
                ai_reasoning=ai.get("reasoning"),
                ai_risk=ai.get("key_risk"),
                user_email=user_email,
            )
        )

    return report_id
