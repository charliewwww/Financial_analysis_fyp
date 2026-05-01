"""
Predictions repository — the accountability loop.

Records price at signal time, updates with actual price 1 week later,
and computes rolling accuracy stats for the Track Record page (Phase 2.3).

Operations:
    list_for_report(db, report_id)           → list[PredictionSchema]
    list_for_signal_card(db, signal_card_id) → list[PredictionSchema]
    list_unchecked(db)                       → list[dict]  (for the weekly job)
    update_actual_price(db, pred_id, price)  → None
    get_accuracy_stats(db)                   → AccuracyStats
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import case, func, select, update
from sqlalchemy.ext.asyncio import AsyncConnection

from app.db.tables import predictions, reports, signal_cards
from app.schemas.reports import AccuracyStats, PredictionSchema


def _row_to_prediction(r: Any) -> PredictionSchema:
    d = dict(r)
    if d.get("checked_at") and hasattr(d["checked_at"], "isoformat"):
        d["checked_at"] = d["checked_at"].isoformat()
    return PredictionSchema.model_validate(d)


# ── Queries ────────────────────────────────────────────────────────

async def list_for_report(
    db: AsyncConnection, report_id: int
) -> list[PredictionSchema]:
    """All predictions associated with a legacy sector report."""
    rows = (
        await db.execute(
            select(predictions)
            .where(predictions.c.report_id == report_id)
            .order_by(predictions.c.ticker)
        )
    ).mappings().all()
    return [_row_to_prediction(r) for r in rows]


async def list_for_signal_card(
    db: AsyncConnection, signal_card_id: int
) -> list[PredictionSchema]:
    """All predictions associated with a Phase 1+ signal card."""
    rows = (
        await db.execute(
            select(predictions)
            .where(predictions.c.signal_card_id == signal_card_id)
            .order_by(predictions.c.ticker)
        )
    ).mappings().all()
    return [_row_to_prediction(r) for r in rows]


async def list_unchecked(db: AsyncConnection) -> list[dict]:
    """
    Predictions without a verified actual price.
    Consumed by the weekly accuracy-check background job.

    Returns enough data to fetch the actual price and call update_actual_price().
    """
    # Join both signal_cards and reports so the job knows which path each came from
    sc_label = signal_cards.c.ticker.label("sc_ticker")
    r_label = reports.c.created_at.label("report_date")

    rows = (
        await db.execute(
            select(
                predictions.c.id,
                predictions.c.ticker,
                predictions.c.price_at_report,
                predictions.c.signal_card_id,
                predictions.c.report_id,
                predictions.c.ai_direction,
            )
            .where(predictions.c.price_1w_later.is_(None))
            .order_by(predictions.c.id)
        )
    ).mappings().all()

    return [dict(r) for r in rows]


# ── Mutations ──────────────────────────────────────────────────────

async def update_actual_price(
    db: AsyncConnection, prediction_id: int, actual_price: float
) -> None:
    """
    Record the actual price 1 week after the signal.
    Computes directional accuracy automatically.

    Called by the weekly accuracy-check background job.
    """
    # Fetch the existing row to compute derived fields
    row = (
        await db.execute(
            select(
                predictions.c.price_at_report,
                predictions.c.ai_direction,
            ).where(predictions.c.id == prediction_id)
        )
    ).mappings().first()

    if row is None:
        return

    price_at_report: float | None = row["price_at_report"]
    ai_direction: str | None = row["ai_direction"]
    now = datetime.now(timezone.utc)

    actual_change: float | None = None
    if price_at_report and price_at_report > 0:
        actual_change = round(
            ((actual_price - price_at_report) / price_at_report) * 100, 2
        )

    # Directional accuracy: did the AI call the direction right?
    prediction_correct: bool | None = None
    if ai_direction and actual_change is not None:
        direction_upper = ai_direction.upper()
        if direction_upper == "BULLISH" and actual_change > 0:
            prediction_correct = True
        elif direction_upper == "BEARISH" and actual_change < 0:
            prediction_correct = True
        elif direction_upper == "NEUTRAL" and abs(actual_change) < 2:
            prediction_correct = True
        else:
            prediction_correct = False

    await db.execute(
        update(predictions)
        .where(predictions.c.id == prediction_id)
        .values(
            price_1w_later=actual_price,
            actual_change_1w=actual_change,
            checked_at=now,
            prediction_correct=prediction_correct,
        )
    )


# ── Accuracy stats ─────────────────────────────────────────────────

async def get_accuracy_stats(db: AsyncConnection) -> AccuracyStats:
    """
    Aggregate accuracy stats for the Track Record page (Phase 2.3).

    Returns overall counts + directional accuracy + avg absolute error.
    """
    total: int = (
        await db.execute(select(func.count()).select_from(predictions))
    ).scalar_one()

    checked: int = (
        await db.execute(
            select(func.count())
            .select_from(predictions)
            .where(predictions.c.price_1w_later.isnot(None))
        )
    ).scalar_one()

    # Directional accuracy
    direction_row = (
        await db.execute(
            select(
                func.count(
                    case((predictions.c.prediction_correct == True, 1))  # noqa: E712
                ).label("correct"),
                func.count(
                    case((predictions.c.prediction_correct == False, 1))  # noqa: E712
                ).label("incorrect"),
            ).where(predictions.c.prediction_correct.isnot(None))
        )
    ).mappings().first()

    correct = int(direction_row["correct"]) if direction_row else 0
    incorrect = int(direction_row["incorrect"]) if direction_row else 0
    total_rated = correct + incorrect
    accuracy_pct = round(correct / total_rated * 100, 1) if total_rated > 0 else None

    # Average absolute change (proxy for magnitude error)
    avg_err_row = (
        await db.execute(
            select(
                func.avg(func.abs(predictions.c.actual_change_1w)).label("avg_err")
            ).where(predictions.c.actual_change_1w.isnot(None))
        )
    ).mappings().first()
    avg_err = round(float(avg_err_row["avg_err"]), 2) if avg_err_row and avg_err_row["avg_err"] else None

    return AccuracyStats(
        total=total,
        checked=checked,
        unchecked=total - checked,
        direction_correct=correct,
        direction_incorrect=incorrect,
        direction_accuracy_pct=accuracy_pct,
        avg_absolute_error_pct=avg_err,
    )
