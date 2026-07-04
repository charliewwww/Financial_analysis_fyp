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

from sqlalchemy import case, func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncConnection

from app.db.tables import predictions, reports, signal_cards
from app.schemas.reports import AccuracyStats, PredictionSchema


def _row_to_prediction(r: Any) -> PredictionSchema:
    d = dict(r)
    if d.get("checked_at") and hasattr(d["checked_at"], "isoformat"):
        d["checked_at"] = d["checked_at"].isoformat()
    return PredictionSchema.model_validate(d)


def _user_scope(user_email: str | None):
    if not user_email:
        return None
    return (predictions.c.user_email == user_email) | (predictions.c.user_email.is_(None))


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


async def create_for_signal_card(
    db: AsyncConnection,
    signal_card_id: int,
    rows: list[dict[str, Any]],
    user_email: str | None = None,
) -> list[int]:
    """Persist prediction rows created alongside a structured signal card."""
    inserted: list[int] = []
    for row in rows:
        ticker = str(row.get("ticker") or "").strip().upper()
        if not ticker:
            continue
        result = await db.execute(
            insert(predictions)
            .values(
                signal_card_id=signal_card_id,
                ticker=ticker,
                price_at_report=row.get("price_at_report"),
                change_1w_at_report=row.get("change_1w_at_report"),
                ai_direction=row.get("ai_direction"),
                ai_predicted_change=row.get("ai_predicted_change"),
                ai_reasoning=row.get("ai_reasoning"),
                ai_risk=row.get("ai_risk"),
                user_email=user_email,
            )
            .returning(predictions.c.id)
        )
        inserted.append(result.scalar_one())
    return inserted


async def list_unchecked(db: AsyncConnection) -> list[dict]:
    """
    Predictions without a verified actual price.
    Consumed by the daily accuracy-check background job (prediction_resolver).

    Returns enough data to age-gate, fetch the actual price, and call
    update_actual_price(). ``source_date`` is the creation time of the parent
    signal card (or legacy report), used to decide whether the 1-week outcome
    is mature enough to score.
    """
    source_date = func.coalesce(
        signal_cards.c.created_at, reports.c.created_at
    ).label("source_date")

    rows = (
        await db.execute(
            select(
                predictions.c.id,
                predictions.c.ticker,
                predictions.c.price_at_report,
                predictions.c.signal_card_id,
                predictions.c.report_id,
                predictions.c.ai_direction,
                source_date,
            )
            .select_from(
                predictions
                .outerjoin(
                    signal_cards,
                    predictions.c.signal_card_id == signal_cards.c.id,
                )
                .outerjoin(
                    reports,
                    predictions.c.report_id == reports.c.id,
                )
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

async def get_accuracy_stats(
    db: AsyncConnection,
    user_email: str | None = None,
) -> AccuracyStats:
    """
    Aggregate accuracy stats for the Track Record page (Phase 2.3).

    Returns overall counts + directional accuracy + avg absolute error.
    """
    scope = _user_scope(user_email)

    total_q = select(func.count()).select_from(predictions)
    if scope is not None:
        total_q = total_q.where(scope)
    total: int = (await db.execute(total_q)).scalar_one()

    checked_q = (
        select(func.count())
        .select_from(predictions)
        .where(predictions.c.price_1w_later.isnot(None))
    )
    if scope is not None:
        checked_q = checked_q.where(scope)
    checked: int = (await db.execute(checked_q)).scalar_one()

    # Directional accuracy
    direction_q = select(
        func.count(
            case((predictions.c.prediction_correct == True, 1))  # noqa: E712
        ).label("correct"),
        func.count(
            case((predictions.c.prediction_correct == False, 1))  # noqa: E712
        ).label("incorrect"),
    ).where(predictions.c.prediction_correct.isnot(None))
    if scope is not None:
        direction_q = direction_q.where(scope)
    direction_row = (await db.execute(direction_q)).mappings().first()

    correct = int(direction_row["correct"]) if direction_row else 0
    incorrect = int(direction_row["incorrect"]) if direction_row else 0
    total_rated = correct + incorrect
    accuracy_pct = round(correct / total_rated * 100, 1) if total_rated > 0 else None

    # Average absolute change (proxy for magnitude error)
    avg_err_q = select(
        func.avg(func.abs(predictions.c.actual_change_1w)).label("avg_err")
    ).where(predictions.c.actual_change_1w.isnot(None))
    if scope is not None:
        avg_err_q = avg_err_q.where(scope)
    avg_err_row = (await db.execute(avg_err_q)).mappings().first()
    avg_err = round(float(avg_err_row["avg_err"]), 2) if avg_err_row and avg_err_row["avg_err"] else None

    by_type: dict[str, Any] = {}
    type_q = (
        select(
            signal_cards.c.signal_type.label("signal_type"),
            func.count(predictions.c.id).label("checked"),
            func.count(case((predictions.c.prediction_correct == True, 1))).label("correct"),  # noqa: E712
        )
        .select_from(predictions.join(signal_cards, predictions.c.signal_card_id == signal_cards.c.id))
        .where(predictions.c.prediction_correct.isnot(None))
        .where(signal_cards.c.signal_type.isnot(None))
        .group_by(signal_cards.c.signal_type)
    )
    if scope is not None:
        type_q = type_q.where(scope)
    for row in (await db.execute(type_q)).mappings().all():
        checked_for_type = int(row["checked"] or 0)
        correct_for_type = int(row["correct"] or 0)
        by_type[str(row["signal_type"])] = {
            "total": checked_for_type,
            "correct": correct_for_type,
            "accuracy_pct": round(correct_for_type / checked_for_type * 100, 1)
            if checked_for_type
            else None,
        }

    return AccuracyStats(
        total=total,
        checked=checked,
        unchecked=total - checked,
        direction_correct=correct,
        direction_incorrect=incorrect,
        direction_accuracy_pct=accuracy_pct,
        avg_absolute_error_pct=avg_err,
        by_signal_type=by_type,
    )
