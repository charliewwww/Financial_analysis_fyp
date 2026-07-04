"""
Authentication repository — sessions, the invite allow-list, and the waitlist.

All functions are async and dialect-agnostic (portable across PostgreSQL and
SQLite). Timestamps are stored as timezone-aware datetimes; reads tolerate both
native datetimes (PostgreSQL) and ISO strings (SQLite TEXT columns).

Tables (see app/db/tables.py):
    user_sessions    — one row per active sign-in (opaque token, stored hashed)
    auth_allowlist   — private-beta invite list (who may sign in)
    access_requests  — waitlist of not-yet-invited sign-in attempts
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, insert, select, update
from sqlalchemy.ext.asyncio import AsyncConnection

from app.db.tables import access_requests, auth_allowlist, user_sessions


# ── Helpers ────────────────────────────────────────────────────────

def _norm(email: str) -> str:
    return email.strip().lower()


def _parse_dt(value: Any) -> datetime | None:
    """Coerce a stored timestamp (datetime or ISO string) to an aware datetime."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


# ══════════════════════════════════════════════════════════════════
# SESSIONS
# ══════════════════════════════════════════════════════════════════

async def create_session(
    db: AsyncConnection,
    *,
    token_hash: str,
    user_email: str,
    expires_at: datetime,
    user_agent: str | None = None,
) -> None:
    """Persist a new session keyed by the SHA-256 hash of its opaque token."""
    now = datetime.now(timezone.utc)
    await db.execute(
        insert(user_sessions).values(
            token_hash=token_hash,
            user_email=_norm(user_email),
            created_at=now,
            expires_at=expires_at,
            last_seen_at=now,
            user_agent=user_agent,
        )
    )


async def get_valid_session(
    db: AsyncConnection,
    token_hash: str,
) -> dict[str, Any] | None:
    """
    Return the session row for *token_hash* if it exists and is not expired.

    Expired sessions are treated as absent (and best-effort deleted).
    """
    row = (
        await db.execute(
            select(user_sessions).where(user_sessions.c.token_hash == token_hash)
        )
    ).mappings().first()
    if row is None:
        return None

    expires = _parse_dt(row["expires_at"])
    if expires is not None and expires <= datetime.now(timezone.utc):
        await delete_session(db, token_hash)
        return None

    return dict(row)


async def touch_session(db: AsyncConnection, token_hash: str) -> None:
    """Update last_seen_at for an active session (best-effort liveness stamp)."""
    await db.execute(
        update(user_sessions)
        .where(user_sessions.c.token_hash == token_hash)
        .values(last_seen_at=datetime.now(timezone.utc))
    )


async def delete_session(db: AsyncConnection, token_hash: str) -> None:
    """Revoke a single session (logout)."""
    await db.execute(
        delete(user_sessions).where(user_sessions.c.token_hash == token_hash)
    )


async def delete_user_sessions(db: AsyncConnection, user_email: str) -> None:
    """Revoke every session for a user (sign out everywhere / on suspend)."""
    await db.execute(
        delete(user_sessions).where(user_sessions.c.user_email == _norm(user_email))
    )


async def purge_expired_sessions(db: AsyncConnection) -> int:
    """Delete all expired sessions. Returns the number removed."""
    result = await db.execute(
        delete(user_sessions).where(
            user_sessions.c.expires_at <= datetime.now(timezone.utc)
        )
    )
    return int(result.rowcount or 0)


# ══════════════════════════════════════════════════════════════════
# ALLOW-LIST  (invites)
# ══════════════════════════════════════════════════════════════════

async def get_allow_entry(
    db: AsyncConnection,
    email: str,
) -> dict[str, Any] | None:
    """Return the allow-list row for *email*, or None if not invited."""
    row = (
        await db.execute(
            select(auth_allowlist).where(auth_allowlist.c.email == _norm(email))
        )
    ).mappings().first()
    return dict(row) if row is not None else None


async def is_allowed(db: AsyncConnection, email: str) -> bool:
    """True if *email* is on the invite allow-list."""
    return (await get_allow_entry(db, email)) is not None


async def add_to_allowlist(
    db: AsyncConnection,
    *,
    email: str,
    role: str = "user",
    note: str | None = None,
    invited_by: str | None = None,
) -> None:
    """Invite an email (idempotent upsert). ``role`` may pre-assign 'admin'."""
    normalized = _norm(email)
    existing = await get_allow_entry(db, normalized)
    if existing is not None:
        await db.execute(
            update(auth_allowlist)
            .where(auth_allowlist.c.email == normalized)
            .values(role=role, note=note, invited_by=invited_by)
        )
        return
    await db.execute(
        insert(auth_allowlist).values(
            email=normalized,
            role=role,
            note=note,
            invited_by=invited_by,
            created_at=datetime.now(timezone.utc),
        )
    )


async def remove_from_allowlist(db: AsyncConnection, email: str) -> None:
    """Revoke an invite. Existing sessions are not touched here."""
    await db.execute(
        delete(auth_allowlist).where(auth_allowlist.c.email == _norm(email))
    )


async def list_allowlist(db: AsyncConnection) -> list[dict[str, Any]]:
    """All invited emails, newest first."""
    rows = (
        await db.execute(
            select(auth_allowlist).order_by(auth_allowlist.c.created_at.desc())
        )
    ).mappings().all()
    return [dict(r) for r in rows]


# ══════════════════════════════════════════════════════════════════
# ACCESS REQUESTS  (waitlist)
# ══════════════════════════════════════════════════════════════════

async def upsert_access_request(
    db: AsyncConnection,
    *,
    email: str,
    name: str | None = None,
) -> None:
    """
    Record a sign-in attempt by a not-yet-invited user (idempotent).

    A previously decided request is reset to 'pending' so a fresh attempt is
    visible to admins again; an existing pending request is left as-is.
    """
    normalized = _norm(email)
    existing = (
        await db.execute(
            select(access_requests).where(access_requests.c.email == normalized)
        )
    ).mappings().first()

    if existing is not None:
        await db.execute(
            update(access_requests)
            .where(access_requests.c.email == normalized)
            .values(name=name or existing["name"], status="pending")
        )
        return

    await db.execute(
        insert(access_requests).values(
            email=normalized,
            name=name,
            status="pending",
            requested_at=datetime.now(timezone.utc),
        )
    )


async def list_access_requests(
    db: AsyncConnection,
    *,
    status: str | None = None,
) -> list[dict[str, Any]]:
    """All waitlist requests (optionally filtered by status), newest first."""
    query = select(access_requests).order_by(access_requests.c.requested_at.desc())
    if status is not None:
        query = query.where(access_requests.c.status == status)
    rows = (await db.execute(query)).mappings().all()
    return [dict(r) for r in rows]


async def set_request_status(
    db: AsyncConnection,
    email: str,
    *,
    status: str,
    decided_by: str | None = None,
) -> None:
    """Mark a waitlist request approved or denied."""
    await db.execute(
        update(access_requests)
        .where(access_requests.c.email == _norm(email))
        .values(
            status=status,
            decided_at=datetime.now(timezone.utc),
            decided_by=decided_by,
        )
    )
