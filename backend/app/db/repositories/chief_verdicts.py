"""
Chief Strategist verdicts repository — the desk's own accountability loop.

Persists the single house call the Chief Strategist makes across all analysts
for a ticker, then records the actual 1-week outcome so the prediction page can
track the DESK's directional accuracy (separate from each analyst).

Operations:
    create(db, values)                       → int   (new verdict id)
    list_recent(db, user_email, limit)       → list[ChiefVerdictRecord]
    latest_for_ticker(db, ticker, email)     → ChiefVerdictRecord | None
    list_unchecked(db)                       → list[dict]  (weekly job)
    update_actual_price(db, id, price)       → None
    get_accuracy(db, user_email)             → ChiefVerdictAccuracy
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncConnection

from app.db.tables import chief_verdicts
from app.schemas.analysis import ChiefVerdictAccuracy, ChiefVerdictRecord


def _user_scope(user_email: str | None):
    if not user_email:
        return None
    return (chief_verdicts.c.user_email == user_email) | (
        chief_verdicts.c.user_email.is_(None)
    )


def _market_scope(market: str | None):
    """Restrict to one market by ticker suffix (hk = '*.HK', us = everything else)."""
    if not market:
        return None
    m = market.strip().lower()
    if m == "hk":
        return chief_verdicts.c.ticker.like("%.HK")
    if m == "us":
        return chief_verdicts.c.ticker.notlike("%.HK")
    return None


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _row_to_record(r: Any) -> ChiefVerdictRecord:
    d = dict(r)
    d["created_at"] = _iso(d.get("created_at")) or ""
    d["checked_at"] = _iso(d.get("checked_at"))
    correct = d.get("verdict_correct")
    if correct is not None:
        d["verdict_correct"] = bool(correct)
    return ChiefVerdictRecord.model_validate(
        {
            "id": d.get("id"),
            "ticker": d.get("ticker"),
            "run_id": d.get("run_id"),
            "action": d.get("action") or "HOLD",
            "conviction": d.get("conviction"),
            "deciding_reason": d.get("deciding_reason") or "",
            "summary": d.get("summary") or "",
            "agreement": d.get("agreement") or "",
            "dissent": d.get("dissent") or "",
            "risk_assessment": d.get("risk_assessment") or "",
            "analyst_count": d.get("analyst_count") or 0,
            "price_at_verdict": d.get("price_at_verdict"),
            "price_1w_later": d.get("price_1w_later"),
            "actual_change_1w": d.get("actual_change_1w"),
            "checked_at": d.get("checked_at"),
            "verdict_correct": d.get("verdict_correct"),
            "created_at": d.get("created_at"),
        }
    )


# ── Mutations ──────────────────────────────────────────────────────

async def create(db: AsyncConnection, values: dict[str, Any]) -> int:
    """Persist a new Chief Strategist verdict; returns the new id."""
    payload = dict(values)
    payload.setdefault("created_at", datetime.now(timezone.utc))
    result = await db.execute(
        insert(chief_verdicts).values(**payload).returning(chief_verdicts.c.id)
    )
    return result.scalar_one()


async def update_actual_price(
    db: AsyncConnection, verdict_id: int, actual_price: float
) -> None:
    """
    Record the actual price 1 week after the verdict and score it.

    BUY  → correct if price rose.
    SELL → correct if price fell.
    HOLD → correct if the move stayed within ±2%.
    """
    row = (
        await db.execute(
            select(
                chief_verdicts.c.price_at_verdict,
                chief_verdicts.c.action,
            ).where(chief_verdicts.c.id == verdict_id)
        )
    ).mappings().first()

    if row is None:
        return

    price_at_verdict: float | None = row["price_at_verdict"]
    action: str = (row["action"] or "HOLD").upper()
    now = datetime.now(timezone.utc)

    actual_change: float | None = None
    if price_at_verdict and price_at_verdict > 0:
        actual_change = round(
            ((actual_price - price_at_verdict) / price_at_verdict) * 100, 2
        )

    verdict_correct: bool | None = None
    if actual_change is not None:
        if action == "BUY":
            verdict_correct = actual_change > 0
        elif action == "SELL":
            verdict_correct = actual_change < 0
        else:  # HOLD
            verdict_correct = abs(actual_change) < 2

    await db.execute(
        update(chief_verdicts)
        .where(chief_verdicts.c.id == verdict_id)
        .values(
            price_1w_later=actual_price,
            actual_change_1w=actual_change,
            checked_at=now,
            verdict_correct=verdict_correct,
        )
    )


# ── Queries ────────────────────────────────────────────────────────

async def list_recent(
    db: AsyncConnection,
    user_email: str | None = None,
    limit: int = 20,
) -> list[ChiefVerdictRecord]:
    """Most recent verdicts, newest first."""
    query = select(chief_verdicts).order_by(chief_verdicts.c.created_at.desc())
    scope = _user_scope(user_email)
    if scope is not None:
        query = query.where(scope)
    query = query.limit(limit)
    rows = (await db.execute(query)).mappings().all()
    return [_row_to_record(r) for r in rows]


async def latest_for_ticker(
    db: AsyncConnection,
    ticker: str,
    user_email: str | None = None,
) -> ChiefVerdictRecord | None:
    """The most recent verdict for a ticker, if any."""
    query = (
        select(chief_verdicts)
        .where(chief_verdicts.c.ticker == ticker.strip().upper())
        .order_by(chief_verdicts.c.created_at.desc())
        .limit(1)
    )
    scope = _user_scope(user_email)
    if scope is not None:
        query = query.where(scope)
    row = (await db.execute(query)).mappings().first()
    return _row_to_record(row) if row else None


async def list_unchecked(db: AsyncConnection) -> list[dict]:
    """Verdicts without a verified 1-week price (for the weekly job)."""
    rows = (
        await db.execute(
            select(
                chief_verdicts.c.id,
                chief_verdicts.c.ticker,
                chief_verdicts.c.price_at_verdict,
                chief_verdicts.c.action,
                chief_verdicts.c.created_at,
            )
            .where(chief_verdicts.c.price_1w_later.is_(None))
            .order_by(chief_verdicts.c.id)
        )
    ).mappings().all()
    return [dict(r) for r in rows]


# ── Accuracy ───────────────────────────────────────────────────────

async def get_accuracy(
    db: AsyncConnection,
    user_email: str | None = None,
    recent_limit: int = 10,
    market: str | None = None,
) -> ChiefVerdictAccuracy:
    """Aggregate track record for the Chief Strategist's house calls."""
    scope = _user_scope(user_email)
    market_scope = _market_scope(market)

    base = select(chief_verdicts)
    if scope is not None:
        base = base.where(scope)
    if market_scope is not None:
        base = base.where(market_scope)
    rows = (await db.execute(base)).mappings().all()

    total = len(rows)
    checked = sum(1 for r in rows if r["price_1w_later"] is not None)
    correct = sum(1 for r in rows if bool(r["verdict_correct"]))
    buy_calls = sum(1 for r in rows if (r["action"] or "").upper() == "BUY")
    sell_calls = sum(1 for r in rows if (r["action"] or "").upper() == "SELL")
    hold_calls = sum(1 for r in rows if (r["action"] or "").upper() == "HOLD")
    hit_rate = round(correct / checked, 4) if checked else None

    recent_q = select(chief_verdicts).order_by(
        chief_verdicts.c.created_at.desc()
    )
    if scope is not None:
        recent_q = recent_q.where(scope)
    if market_scope is not None:
        recent_q = recent_q.where(market_scope)
    recent_q = recent_q.limit(recent_limit)
    recent_rows = (await db.execute(recent_q)).mappings().all()

    return ChiefVerdictAccuracy(
        total=total,
        checked=checked,
        correct=correct,
        hit_rate=hit_rate,
        buy_calls=buy_calls,
        sell_calls=sell_calls,
        hold_calls=hold_calls,
        recent=[_row_to_record(r) for r in recent_rows],
    )
