"""
Chief Strategist memory repository — the self-refining "lessons" addendum.

After the weekly resolver scores the Chief Strategist's past verdicts, an LLM
distils recent hits/misses into calibration notes stored here and prepended to
the strategist's prompt. Keyed by user_email; a NULL-email row is the shared
house default used when a user has no personal calibration yet.

Operations:
    get_lessons(db, user_email)              → str
    upsert_lessons(db, email, lessons, ...)  → None
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import insert, select, update
from sqlalchemy.ext.asyncio import AsyncConnection

from app.db.tables import chief_strategist_memory


async def get_lessons(
    db: AsyncConnection, user_email: str | None = None
) -> str:
    """
    Return the calibration notes for a user, falling back to the shared
    house default (NULL-email row) when the user has none.
    """
    if user_email:
        row = (
            await db.execute(
                select(chief_strategist_memory.c.lessons).where(
                    chief_strategist_memory.c.user_email == user_email
                )
            )
        ).first()
        if row and (row[0] or "").strip():
            return row[0]

    shared = (
        await db.execute(
            select(chief_strategist_memory.c.lessons).where(
                chief_strategist_memory.c.user_email.is_(None)
            )
        )
    ).first()
    return shared[0] if shared and shared[0] else ""


async def upsert_lessons(
    db: AsyncConnection,
    user_email: str | None,
    lessons: str,
    sample_size: int = 0,
    hit_rate: float | None = None,
) -> None:
    """Create or update the calibration notes for a user (or the shared row)."""
    now = datetime.now(timezone.utc)
    if user_email:
        cond = chief_strategist_memory.c.user_email == user_email
    else:
        cond = chief_strategist_memory.c.user_email.is_(None)

    existing = (
        await db.execute(select(chief_strategist_memory.c.id).where(cond))
    ).first()

    if existing:
        await db.execute(
            update(chief_strategist_memory)
            .where(cond)
            .values(
                lessons=lessons,
                sample_size=sample_size,
                hit_rate=hit_rate,
                updated_at=now,
            )
        )
    else:
        await db.execute(
            insert(chief_strategist_memory).values(
                user_email=user_email,
                lessons=lessons,
                sample_size=sample_size,
                hit_rate=hit_rate,
                updated_at=now,
            )
        )
