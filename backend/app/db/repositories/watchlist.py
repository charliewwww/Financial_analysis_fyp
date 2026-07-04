"""
Watchlist repository — CRUD for the watchlist ("My Favourites") table.

One row per (user_email, ticker). Tickers are stored upper-cased so the
unique constraint behaves predictably across casing.

Operations:
    list_for_user(db, email)                 → list[WatchlistItemSchema]
    add(db, email, ticker, notes, sector_id) → WatchlistItemSchema
    remove(db, email, ticker)                → bool

Kept DB-agnostic (no ON CONFLICT) so it works on both PostgreSQL (production)
and the in-memory SQLite used by the test suite.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, insert, select, update
from sqlalchemy.ext.asyncio import AsyncConnection

from app.db.tables import watchlist
from app.schemas.watchlist import WatchlistItemSchema


def _row_to_schema(row: Any) -> WatchlistItemSchema:
    d = dict(row)
    added = d.get("added_at")
    d["added_at"] = added.isoformat() if hasattr(added, "isoformat") else str(added or "")
    return WatchlistItemSchema.model_validate(d)


async def list_for_user(db: AsyncConnection, email: str) -> list[WatchlistItemSchema]:
    rows = (
        await db.execute(
            select(watchlist)
            .where(watchlist.c.user_email == email)
            .order_by(watchlist.c.added_at.desc())
        )
    ).mappings().all()
    return [_row_to_schema(r) for r in rows]


async def add(
    db: AsyncConnection,
    email: str,
    ticker: str,
    *,
    notes: str | None = None,
    sector_id: str | None = None,
) -> WatchlistItemSchema:
    """Add (or update notes/sector for) a favourite ticker — idempotent on (user, ticker)."""
    symbol = ticker.strip().upper()
    existing = (
        await db.execute(
            select(watchlist).where(
                (watchlist.c.user_email == email) & (watchlist.c.ticker == symbol)
            )
        )
    ).mappings().first()

    if existing is not None:
        result = await db.execute(
            update(watchlist)
            .where(
                (watchlist.c.user_email == email) & (watchlist.c.ticker == symbol)
            )
            .values(notes=notes, sector_id=sector_id)
            .returning(*watchlist.c)
        )
        return _row_to_schema(result.mappings().one())

    result = await db.execute(
        insert(watchlist)
        .values(
            user_email=email,
            ticker=symbol,
            added_at=datetime.now(timezone.utc),
            notes=notes,
            sector_id=sector_id,
        )
        .returning(*watchlist.c)
    )
    return _row_to_schema(result.mappings().one())


async def remove(db: AsyncConnection, email: str, ticker: str) -> bool:
    symbol = ticker.strip().upper()
    result = await db.execute(
        delete(watchlist).where(
            (watchlist.c.user_email == email) & (watchlist.c.ticker == symbol)
        )
    )
    return bool(result.rowcount)
