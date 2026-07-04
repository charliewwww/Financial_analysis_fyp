"""
Prediction resolver — closes the per-analyst accountability loop.

Mirrors ``accuracy_resolver`` (which handles the Chief Strategist's house
verdicts) but for the per-ticker ``predictions`` table. For each unchecked
prediction whose parent signal/report is at least ``min_age_days`` old, it
fetches the current price and records it as the realised ~1-week outcome, then
``update_actual_price`` computes directional correctness.

Approach matches the verdict resolver: a prediction roughly one week old is
scored against the price *now* as a proxy for "one week later". The price fetch
is injected so the resolver is unit-testable without network access.

This is the engine behind the Track Record page: it is what turns a confident
directional call into a verified hit or miss over time.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Callable

from sqlalchemy.ext.asyncio import AsyncConnection

from app.db.repositories import predictions as pred_repo

logger = logging.getLogger(__name__)

# A prediction must be at least this old before its 1-week outcome is meaningful.
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


def _age_days(value: Any) -> float | None:
    """Age in days of a timestamp that may be a datetime or ISO string."""
    if value is None:
        return None
    if isinstance(value, str):
        try:
            created = datetime.fromisoformat(value)
        except ValueError:
            return None
    elif isinstance(value, datetime):
        created = value
    else:
        return None
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - created).total_seconds() / 86400.0


async def resolve_predictions(
    db: AsyncConnection,
    *,
    price_fetcher: PriceFetcher | None = None,
    min_age_days: float = _RESOLVE_AFTER_DAYS,
) -> int:
    """
    Resolve every due, unchecked prediction against its actual ~1-week price.

    Predictions whose parent signal/report is younger than ``min_age_days`` are
    skipped (their outcome has not matured). Predictions with no known source
    date (legacy rows) are resolved, since they are by definition old.

    Returns the number of predictions scored.
    """
    fetch = price_fetcher or _default_price_fetcher
    unchecked = await pred_repo.list_unchecked(db)

    # Cache one price per ticker for this batch — avoids redundant network hits
    # when several analysts predicted the same name on the same day.
    price_cache: dict[str, float | None] = {}
    resolved = 0

    for row in unchecked:
        age = _age_days(row.get("source_date"))
        if age is not None and age < min_age_days:
            continue
        ticker = str(row.get("ticker") or "").upper()
        if not ticker:
            continue

        if ticker not in price_cache:
            try:
                price_cache[ticker] = await asyncio.to_thread(fetch, ticker)
            except Exception:  # pragma: no cover - network is best-effort
                logger.exception(
                    "Price fetch failed while resolving prediction %s", row.get("id")
                )
                price_cache[ticker] = None

        price = price_cache[ticker]
        if price is None:
            continue

        await pred_repo.update_actual_price(db, int(row["id"]), price)
        resolved += 1

    return resolved
