"""
Accuracy resolver — closes the Chief Strategist's accountability loop.

Fetches the actual 1-week price for verdicts that are now old enough, scores
them, then asks an LLM to distil recent hits and misses into a short
"calibration notes" addendum stored in chief_strategist_memory. Those notes are
prepended to the Chief Strategist prompt on the next run, so the desk literally
learns from its own track record.

The price fetch is injected so the resolver is unit-testable without network.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Callable

from sqlalchemy.ext.asyncio import AsyncConnection

from agents.llm_client import call_llm_fast
from app.db.repositories import chief_strategist_memory as memory_repo
from app.db.repositories import chief_verdicts as verdict_repo

logger = logging.getLogger(__name__)

# A verdict must be at least this old before its 1-week outcome is meaningful.
_RESOLVE_AFTER_DAYS = 7

PriceFetcher = Callable[[str], float | None]


def _default_price_fetcher(ticker: str) -> float | None:
    """Fetch the latest close from Yahoo Finance (blocking)."""
    from data_sources.yahoo_finance import get_stock_snapshot  # type: ignore[import]

    snapshot = get_stock_snapshot(ticker)
    if snapshot.get("error"):
        return None
    price = snapshot.get("price")
    return float(price) if isinstance(price, (int, float)) and price > 0 else None


def _verdict_age_days(created_at: Any) -> float | None:
    if created_at is None:
        return None
    if isinstance(created_at, str):
        try:
            created = datetime.fromisoformat(created_at)
        except ValueError:
            return None
    elif isinstance(created_at, datetime):
        created = created_at
    else:
        return None
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - created).total_seconds() / 86400.0


async def resolve_chief_verdicts(
    db: AsyncConnection,
    *,
    price_fetcher: PriceFetcher | None = None,
    min_age_days: float = _RESOLVE_AFTER_DAYS,
) -> int:
    """
    Resolve every due, unchecked verdict against its actual 1-week price.

    Returns the number of verdicts scored.
    """
    fetch = price_fetcher or _default_price_fetcher
    unchecked = await verdict_repo.list_unchecked(db)

    resolved = 0
    for row in unchecked:
        age = _verdict_age_days(row.get("created_at"))
        if age is not None and age < min_age_days:
            continue
        ticker = str(row.get("ticker") or "").upper()
        if not ticker:
            continue
        try:
            price = await asyncio.to_thread(fetch, ticker)
        except Exception:  # pragma: no cover - network is best-effort
            logger.exception("Price fetch failed while resolving verdict %s", row.get("id"))
            price = None
        if price is None:
            continue
        await verdict_repo.update_actual_price(db, int(row["id"]), price)
        resolved += 1

    return resolved


def _build_lessons_prompt(records: list[Any]) -> str:
    lines: list[str] = [
        "Here is the Chief Strategist's recent resolved track record "
        "(each line: action, conviction, ticker, actual 1-week move, outcome):",
        "",
    ]
    for r in records:
        outcome = "CORRECT" if r.verdict_correct else "WRONG"
        change = (
            f"{r.actual_change_1w:+.1f}%" if r.actual_change_1w is not None else "n/a"
        )
        lines.append(
            f"- {r.action} (conv {r.conviction}) {r.ticker}: moved {change} → {outcome}. "
            f"Reason given: {r.deciding_reason or 'n/a'}"
        )
    return "\n".join(lines)


_LESSONS_SYSTEM_PROMPT = (
    "You are the Chief Strategist reviewing your own past calls to get sharper. "
    "From the resolved track record below, write 3-5 short, concrete CALIBRATION "
    "LESSONS that will improve your future BUY/SELL/HOLD verdicts. Focus on "
    "recurring mistakes (e.g. over-weighting low-probability tail risks, "
    "over-trusting a single analyst, mis-sizing conviction). Each lesson must be "
    "one actionable sentence. Output ONLY the bullet list, no preamble."
)


async def refresh_chief_lessons(
    db: AsyncConnection,
    user_email: str | None = None,
    *,
    min_samples: int = 4,
) -> str | None:
    """
    Summarise recent resolved verdicts into calibration notes and persist them.

    Returns the new lessons text, or ``None`` when there is not enough resolved
    history yet.
    """
    accuracy = await verdict_repo.get_accuracy(
        db, user_email=user_email, recent_limit=20
    )
    resolved = [r for r in accuracy.recent if r.price_1w_later is not None]
    if len(resolved) < min_samples:
        return None

    prompt = _build_lessons_prompt(resolved)
    try:
        lessons = await asyncio.to_thread(
            call_llm_fast,
            prompt,
            _LESSONS_SYSTEM_PROMPT,
            temperature=0.3,
            max_tokens=400,
            langfuse_name="chief_strategist_self_refine",
            langfuse_metadata={"samples": len(resolved)},
        )
    except Exception:  # pragma: no cover - best-effort
        logger.exception("Chief Strategist self-refine LLM call failed")
        return None

    lessons = (lessons or "").strip()
    if not lessons:
        return None

    await memory_repo.upsert_lessons(
        db,
        user_email,
        lessons,
        sample_size=len(resolved),
        hit_rate=accuracy.hit_rate,
    )
    return lessons


async def run_resolution(
    db: AsyncConnection,
    *,
    price_fetcher: PriceFetcher | None = None,
    min_age_days: float = _RESOLVE_AFTER_DAYS,
    refresh_lessons: bool = True,
) -> dict[str, Any]:
    """Resolve due verdicts then refresh the self-refining lessons addendum."""
    resolved = await resolve_chief_verdicts(
        db, price_fetcher=price_fetcher, min_age_days=min_age_days
    )
    lessons: str | None = None
    if refresh_lessons:
        lessons = await refresh_chief_lessons(db)
    return {"resolved": resolved, "lessons_updated": lessons is not None}
