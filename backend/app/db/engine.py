"""
Async database engine — PostgreSQL via asyncpg + SQLAlchemy Core.

Replaces the synchronous sqlite3 connection in database/reports_db.py.

Design:
  - One AsyncEngine per process (created at startup, disposed at shutdown)
  - FastAPI dependency `get_db` yields a transactional AsyncConnection per request
  - All callers use SQLAlchemy Core constructs (select/insert/update) —
    no ORM sessions, no lazy loading surprises

Usage in a route:
    from app.db.engine import get_db
    from sqlalchemy.ext.asyncio import AsyncConnection

    @router.get("/example")
    async def example(db: AsyncConnection = Depends(get_db)):
        result = await db.execute(select(reports_table))
        return result.mappings().all()
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine

from app.core.config import settings

if TYPE_CHECKING:
    pass

# ── Module-level engine singleton ──────────────────────────────────
# Populated by init_engine() during lifespan startup.
# Using a sentinel rather than None so type-checkers know the type.
_engine: AsyncEngine | None = None


def _normalize_async_db_url(url: str) -> str:
    """Coerce a plain PostgreSQL URL to the asyncpg driver SQLAlchemy needs.

    Managed hosts (Render, Railway, Heroku, …) hand out sync-style URLs like
    ``postgres://…`` or ``postgresql://…``. SQLAlchemy's async engine requires an
    explicit async driver, so upgrade the scheme to ``postgresql+asyncpg://``.
    URLs that already name a driver (``postgresql+asyncpg://``) or use SQLite are
    returned unchanged.
    """
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]
    if url.startswith("postgresql://"):
        url = "postgresql+asyncpg://" + url[len("postgresql://") :]
    return url


def init_engine() -> AsyncEngine:
    """
    Create the module-level AsyncEngine from settings.database_url.

    Called once in the FastAPI lifespan, not at import time, so unit tests
    can override settings before the engine is constructed.

    SQLite (local dev): pool_size and max_overflow are not supported by
    StaticPool / NullPool; we omit them and let SQLAlchemy pick defaults.
    """
    global _engine
    db_url = _normalize_async_db_url(settings.database_url)
    is_sqlite = db_url.startswith("sqlite")
    kwargs: dict = {"echo": False}
    if not is_sqlite:
        kwargs.update(
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
        )
    _engine = create_async_engine(db_url, **kwargs)
    return _engine


def get_engine() -> AsyncEngine:
    """Return the module-level engine. Raises if called before lifespan startup."""
    if _engine is None:
        raise RuntimeError(
            "Database engine has not been initialised. "
            "Ensure init_engine() is called during the FastAPI lifespan."
        )
    return _engine


async def dispose_engine() -> None:
    """Gracefully close all pooled connections. Called during lifespan shutdown."""
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None


# ── FastAPI dependency ─────────────────────────────────────────────

async def get_db() -> AsyncGenerator[AsyncConnection, None]:
    """
    FastAPI dependency that yields a transactional AsyncConnection.

    The connection is automatically committed on a clean exit and rolled
    back on any exception — identical behaviour to the original
    `with _get_conn() as conn:` pattern in reports_db.py.

    Declare in routes as:
        db: Annotated[AsyncConnection, Depends(get_db)]
    """
    async with get_engine().begin() as conn:
        yield conn
