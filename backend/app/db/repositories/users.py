"""
User details repository — CRUD for the user_details table.

One row per authenticated user (keyed on Cloudflare email).
Created automatically on first profile access; updated via the Profile page.

Operations:
    get_or_create(db, email)             → UserDetailSchema
    update(db, email, **fields)          → UserDetailSchema
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import insert, select, update
from sqlalchemy.ext.asyncio import AsyncConnection

from app.db.tables import user_details
from app.schemas.users import UserDetailSchema


# ── Helpers ────────────────────────────────────────────────────────

def _row_to_schema(row: Any) -> UserDetailSchema:
    d = dict(row)
    d["created_at"] = d["created_at"].isoformat() if hasattr(d.get("created_at"), "isoformat") else str(d.get("created_at", ""))
    d["updated_at"] = d["updated_at"].isoformat() if hasattr(d.get("updated_at"), "isoformat") else (d.get("updated_at") and str(d["updated_at"]))
    return UserDetailSchema.model_validate(d)


# ── Queries ────────────────────────────────────────────────────────

async def get_or_create(
    db: AsyncConnection,
    email: str,
) -> UserDetailSchema:
    """
    Return the profile for *email*, creating a blank row if one doesn't exist yet.

    This is called on every authenticated request to /api/v1/users/me so that
    new users get a profile automatically on first login.
    """
    row = (
        await db.execute(
            select(user_details).where(user_details.c.email == email)
        )
    ).mappings().first()

    if row is not None:
        return _row_to_schema(row)

    # First visit — create a blank profile
    now = datetime.now(timezone.utc)
    result = await db.execute(
        insert(user_details)
        .values(
            email=email,
            username=None,
            saved_sectors=[],
            preferences={},
            created_at=now,
            updated_at=now,
        )
        .returning(*user_details.c)
    )
    return _row_to_schema(result.mappings().one())


async def update_profile(
    db: AsyncConnection,
    email: str,
    *,
    username: str | None = None,
    saved_sectors: list[str] | None = None,
    preferences: dict[str, Any] | None = None,
) -> UserDetailSchema:
    """
    Partial update — only the fields explicitly passed are changed.

    Returns the updated profile row.
    """
    values: dict[str, Any] = {"updated_at": datetime.now(timezone.utc)}

    if username is not None:
        values["username"] = username
    if saved_sectors is not None:
        values["saved_sectors"] = saved_sectors
    if preferences is not None:
        values["preferences"] = preferences

    result = await db.execute(
        update(user_details)
        .where(user_details.c.email == email)
        .values(**values)
        .returning(*user_details.c)
    )
    row = result.mappings().first()

    # If no row existed yet (shouldn't happen in normal flow), fall back to create
    if row is None:
        return await get_or_create(db, email)

    return _row_to_schema(row)
