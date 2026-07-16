"""
Shared fixtures and utilities for the backend test suite.

Provides:
  - engine()  : async SQLite engine with all tables created via raw DDL
  - db()      : async DB connection per test (rolled back on teardown)

Why raw DDL instead of create_all_tables()?
  The production tables use JSONB (PostgreSQL-specific).  SQLite's type
  compiler has no visit_JSONB handler.  We reproduce the same column names
  and types using SQLite-compatible SQL here.  The Table objects imported
  from app.db.tables still work for SELECT/INSERT/UPDATE — the JSONB columns
  are stored as TEXT and deserialized by _coerce_jsonb() in the repositories.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine


# ── Raw DDL — SQLite-compatible versions of all 9 tables ──────────

_DDL = [
    """
    CREATE TABLE IF NOT EXISTS pipeline_runs (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id      TEXT NOT NULL UNIQUE,
        ticker      TEXT NOT NULL,
        sector_id   TEXT NOT NULL,
        agent_id    INTEGER,
        agent_name  TEXT,
        status      TEXT NOT NULL DEFAULT 'pending',
        current_node TEXT,
        error       TEXT,
        created_at  TEXT NOT NULL,
        started_at  TEXT,
        finished_at TEXT,
        signal_card_id INTEGER,
        node_executions TEXT,
        user_email  TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS signal_cards (
        id                 INTEGER PRIMARY KEY AUTOINCREMENT,
        ticker             TEXT NOT NULL,
        run_id             TEXT,
        agent_id           INTEGER,
        signal             TEXT NOT NULL,
        conviction         INTEGER,
        one_line           TEXT,
        key_catalyst       TEXT,
        key_risk           TEXT,
        confidence         REAL,
        signal_type        TEXT,
        validation_score   TEXT,
        supply_chain_impact TEXT,
        sources            TEXT,
        numerical_claims   TEXT,
        sector_context     TEXT,
        raw_pipeline_state TEXT,
        created_at         TEXT NOT NULL,
        status             TEXT NOT NULL DEFAULT 'active',
        user_email         TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS predictions (
        id                 INTEGER PRIMARY KEY AUTOINCREMENT,
        signal_card_id     INTEGER,
        report_id          INTEGER,
        ticker             TEXT NOT NULL,
        price_at_report    REAL,
        change_1w_at_report REAL,
        price_1w_later     REAL,
        actual_change_1w   REAL,
        checked_at         TEXT,
        prediction_correct INTEGER,
        ai_direction       TEXT,
        ai_predicted_change TEXT,
        ai_reasoning       TEXT,
        ai_risk            TEXT,
        user_email         TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS chief_verdicts (
        id               INTEGER PRIMARY KEY AUTOINCREMENT,
        ticker           TEXT NOT NULL,
        run_id           TEXT,
        user_email       TEXT,
        action           TEXT NOT NULL,
        conviction       INTEGER,
        deciding_reason  TEXT,
        summary          TEXT,
        agreement        TEXT,
        dissent          TEXT,
        risk_assessment  TEXT,
        analyst_count    INTEGER DEFAULT 0,
        analyst_snapshot TEXT,
        price_at_verdict REAL,
        price_1w_later   REAL,
        actual_change_1w REAL,
        checked_at       TEXT,
        verdict_correct  INTEGER,
        created_at       TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS chief_strategist_memory (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        user_email  TEXT UNIQUE,
        lessons     TEXT NOT NULL DEFAULT '',
        sample_size INTEGER NOT NULL DEFAULT 0,
        hit_rate    REAL,
        updated_at  TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS reports (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        sector_id           TEXT NOT NULL,
        sector_name         TEXT NOT NULL,
        created_at          TEXT NOT NULL,
        status              TEXT NOT NULL DEFAULT 'active',
        analysis            TEXT NOT NULL,
        validation          TEXT,
        news_summary        TEXT,
        confidence_score    REAL,
        validation_status   TEXT,
        data_sufficiency    TEXT,
        news_used           INTEGER NOT NULL DEFAULT 0,
        prices_snapshot     TEXT,
        technicals_snapshot TEXT,
        news_snapshot       TEXT,
        filings_snapshot    TEXT,
        timing_snapshot     TEXT,
        pipeline_state      TEXT,
        user_email          TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS supply_chain_relationships (
        id               INTEGER PRIMARY KEY AUTOINCREMENT,
        ticker           TEXT NOT NULL,
        related_ticker   TEXT NOT NULL,
        relationship_type TEXT NOT NULL,
        confidence       REAL,
        source_filing    TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS watchlist (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        user_email TEXT NOT NULL,
        ticker     TEXT NOT NULL,
        added_at   TEXT NOT NULL,
        notes      TEXT,
        sector_id  TEXT,
        UNIQUE(user_email, ticker)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS annotations (
        id             INTEGER PRIMARY KEY AUTOINCREMENT,
        signal_card_id INTEGER NOT NULL,
        user_email     TEXT NOT NULL,
        action         TEXT NOT NULL,
        note           TEXT,
        created_at     TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS agents (
        id             INTEGER PRIMARY KEY AUTOINCREMENT,
        name           TEXT NOT NULL,
        description    TEXT,
        identity_layer TEXT,
        is_builtin     INTEGER NOT NULL DEFAULT 0,
        user_email     TEXT,
        created_at     TEXT NOT NULL,
        updated_at     TEXT,
        UNIQUE(user_email, name)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS skills (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        agent_id   INTEGER NOT NULL,
        name       TEXT NOT NULL,
        skill_type TEXT NOT NULL,
        content    TEXT NOT NULL,
        version    INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL,
        updated_at TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS user_details (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        email        TEXT NOT NULL UNIQUE,
        username     TEXT,
        saved_sectors TEXT,
        preferences  TEXT,
        role         TEXT NOT NULL DEFAULT 'user',
        status       TEXT NOT NULL DEFAULT 'active',
        picture      TEXT,
        last_login_at TEXT,
        created_at   TEXT NOT NULL,
        updated_at   TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS user_sessions (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        token_hash   TEXT NOT NULL UNIQUE,
        user_email   TEXT NOT NULL,
        created_at   TEXT NOT NULL,
        expires_at   TEXT NOT NULL,
        last_seen_at TEXT,
        user_agent   TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS auth_allowlist (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        email      TEXT NOT NULL UNIQUE,
        role       TEXT NOT NULL DEFAULT 'user',
        note       TEXT,
        invited_by TEXT,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS access_requests (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        email        TEXT NOT NULL UNIQUE,
        name         TEXT,
        status       TEXT NOT NULL DEFAULT 'pending',
        requested_at TEXT NOT NULL,
        decided_at   TEXT,
        decided_by   TEXT
    )
    """,
]


@pytest_asyncio.fixture
async def engine() -> AsyncEngine:
    """One shared in-memory SQLite engine per test."""
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with eng.begin() as conn:
        for ddl in _DDL:
            await conn.execute(text(ddl))
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def db(engine: AsyncEngine) -> AsyncConnection:
    """Transactional connection per test — rolled back on teardown."""
    async with engine.begin() as conn:
        yield conn
        await conn.rollback()

