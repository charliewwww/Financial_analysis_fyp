"""
SQLAlchemy Core table definitions — full forward-looking schema for PostgreSQL.

Designed to support all four phases of the product roadmap:
    Phase 1 — Core Signal Engine    : pipeline_runs, signal_cards, predictions, reports
    Phase 2 — Credibility Layer     : supply_chain_relationships, watchlist, annotations
    Phase 3 — Skill-Based Agents    : agents, skills
    Phase 4 — Academic Validation   : all tables already present

PostgreSQL upgrades over the original SQLite schema:
  - TEXT JSON blobs  →  JSONB   (indexed, queryable, partial indexes)
  - TEXT timestamps  →  TIMESTAMPTZ  (timezone-aware, sortable natively)
  - INTEGER booleans →  BOOLEAN
  - AUTOINCREMENT    →  BigInteger with autoincrement=True

Migration strategy:
  `create_all_tables()` on first startup is idempotent (checkfirst=True).
  For schema changes after initial deploy, use Alembic.
"""

from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Float,
    Index,
    Integer,
    MetaData,
    Table,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP

# Single metadata object — import wherever DDL is needed.
metadata = MetaData()


# ══════════════════════════════════════════════════════════════════
# PHASE 1 TABLES
# ══════════════════════════════════════════════════════════════════

# ── pipeline_runs ─────────────────────────────────────────────────
# Tracks every pipeline invocation.  Required for SSE status streaming:
# the frontend polls / streams this table to render the live node timeline.
# Created before signal_cards so signal_card_id FK can reference it.

pipeline_runs = Table(
    "pipeline_runs",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("run_id", Text, nullable=False, unique=True),   # UUID string
    Column("ticker", Text, nullable=False),
    Column("sector_id", Text, nullable=False),
    # pending | running | completed | failed
    Column("status", Text, nullable=False, server_default="pending"),
    # Name of the node currently executing (null when not running)
    Column("current_node", Text),
    Column("error", Text),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False),
    Column("started_at", TIMESTAMP(timezone=True)),
    Column("finished_at", TIMESTAMP(timezone=True)),
    # FK to the signal_card produced on completion (null while running)
    Column("signal_card_id", BigInteger),
    # Full node execution timeline — updated after each node completes
    Column("node_executions", JSONB),

    # Multi-tenancy: who triggered this run.
    Column("user_email", Text),

    Index("ix_pipeline_runs_run_id", "run_id"),
    Index("ix_pipeline_runs_ticker", "ticker"),
    Index("ix_pipeline_runs_status", "status"),
    Index("ix_pipeline_runs_user_email", "user_email"),
)


# ── signal_cards ──────────────────────────────────────────────────
# PRIMARY OUTPUT for Phase 1+.
# Replaces the 2000-word essay in `reports` with a structured, validatable
# signal card per ticker.  Every field here is independently verifiable.
# Maps to the target JSON schema in the roadmap (Part 5).

signal_cards = Table(
    "signal_cards",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("ticker", Text, nullable=False),
    Column("run_id", Text),               # links back to pipeline_runs.run_id
    # NULL = system default agent; set when a user-created agent ran this
    Column("agent_id", BigInteger),

    # ── Core signal fields ────────────────────────────────────────
    Column("signal", Text, nullable=False),       # BULLISH | BEARISH | NEUTRAL
    Column("conviction", Integer),                # 1–5
    Column("one_line", Text),                     # single-sentence verdict
    Column("key_catalyst", Text),                 # top bullish driver
    Column("key_risk", Text),                     # top bearish risk
    Column("confidence", Float),                  # 0.0–1.0

    # ── Signal classification (Phase 2 — scaffolded now) ─────────
    # FUNDAMENTAL_SHIFT | MEDIA_NARRATIVE | TECHNICAL_ONLY
    # Determined by rule: SEC filing cited? → FUNDAMENTAL_SHIFT, etc.
    Column("signal_type", Text),

    # ── Validation (Phase 1 restructured loop) ────────────────────
    Column("validation_score", Text),             # e.g. "3/4 claims verified"

    # ── JSONB structured fields ───────────────────────────────────
    # supply_chain_impact: [{"ticker": "TSM", "direction": "▲", "reason": "..."}]
    Column("supply_chain_impact", JSONB),
    # sources: [{"url": "...", "title": "...", "domain": "reuters.com"}]
    Column("sources", JSONB),
    # numerical_claims: [{"claim": "...", "verified": bool, "source": "..."}]
    Column("numerical_claims", JSONB),
    # sector_context: the sector-level data used as context (hybrid model)
    Column("sector_context", JSONB),
    # Full pipeline state snapshot for provenance / debugging
    Column("raw_pipeline_state", JSONB),

    Column("created_at", TIMESTAMP(timezone=True), nullable=False),
    Column("status", Text, nullable=False, server_default="active"),

    # Multi-tenancy: every card belongs to the user who triggered the run.
    # NULL on legacy rows (pre-auth), treated as readable by everyone.
    Column("user_email", Text),

    Index("ix_signal_cards_ticker", "ticker"),
    Index("ix_signal_cards_run_id", "run_id"),
    Index("ix_signal_cards_created_at", "created_at"),
    Index("ix_signal_cards_signal", "signal"),
    Index("ix_signal_cards_signal_type", "signal_type"),
    Index("ix_signal_cards_agent_id", "agent_id"),
    Index("ix_signal_cards_user_email", "user_email"),
)


# ── predictions ───────────────────────────────────────────────────
# Accountability loop: record price at signal time, check actual 1 week later.
# Links to EITHER a signal_card (new path) OR a legacy report (old path).

predictions = Table(
    "predictions",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    # One of these will be non-null (new vs legacy path)
    Column("signal_card_id", BigInteger),   # FK → signal_cards.id (Phase 1+)
    Column("report_id", BigInteger),        # FK → reports.id (legacy compat)
    Column("ticker", Text, nullable=False),

    # ── Price at signal time ──────────────────────────────────────
    Column("price_at_report", Float),
    Column("change_1w_at_report", Float),

    # ── Actuals (populated by weekly accuracy-check job) ─────────
    Column("price_1w_later", Float),
    Column("actual_change_1w", Float),
    Column("checked_at", TIMESTAMP(timezone=True)),
    Column("prediction_correct", Boolean),

    # ── AI directional prediction ─────────────────────────────────
    Column("ai_direction", Text),           # BULLISH | BEARISH | NEUTRAL
    Column("ai_predicted_change", Text),    # "+3% to +7%"
    Column("ai_reasoning", Text),
    Column("ai_risk", Text),                # low | medium | high

    # Multi-tenancy: inherited from the parent signal_card / report.
    Column("user_email", Text),

    Index("ix_predictions_signal_card_id", "signal_card_id"),
    Index("ix_predictions_report_id", "report_id"),
    Index("ix_predictions_ticker", "ticker"),
    Index("ix_predictions_user_email", "user_email"),
    # Partial index for the weekly accuracy job — only scans unchecked rows
    Index(
        "ix_predictions_unchecked",
        "id",
        postgresql_where=text("price_1w_later IS NULL"),
    ),
)


# ── reports ───────────────────────────────────────────────────────
# KEPT FOR BACKWARD COMPATIBILITY with the existing Streamlit app data.
# New analyses produce signal_cards; old Streamlit runs produced reports.
# The frontend can read both; they render differently.

reports = Table(
    "reports",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("sector_id", Text, nullable=False),
    Column("sector_name", Text, nullable=False),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False),
    Column("status", Text, nullable=False, server_default="active"),
    Column("analysis", Text, nullable=False),
    Column("validation", Text),
    Column("news_summary", Text),
    Column("confidence_score", Float),
    Column("validation_status", Text),
    Column("data_sufficiency", Text),
    Column("news_used", Integer, nullable=False, server_default="0"),
    Column("prices_snapshot", JSONB),
    Column("technicals_snapshot", JSONB),
    Column("news_snapshot", JSONB),
    Column("filings_snapshot", JSONB),
    Column("timing_snapshot", JSONB),
    Column("pipeline_state", JSONB),

    # Multi-tenancy: who produced this report.
    Column("user_email", Text),

    Index("ix_reports_sector_id", "sector_id"),
    Index("ix_reports_created_at", "created_at"),
    Index("ix_reports_user_email", "user_email"),
)


# ══════════════════════════════════════════════════════════════════
# PHASE 2 TABLES  (schema defined now — repositories built in Piece 4)
# ══════════════════════════════════════════════════════════════════

# ── supply_chain_relationships ────────────────────────────────────
# Populated by the Supply Chain Discovery Agent (Phase 2.2).
# Replaces the hardcoded config/supply_chain_data.py.
# The agent reads 10-K filings and extracts supplier/customer/partner links.

supply_chain_relationships = Table(
    "supply_chain_relationships",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("ticker", Text, nullable=False),
    Column("related_ticker", Text, nullable=False),
    # supplier | customer | partner | competitor
    Column("relationship_type", Text, nullable=False),
    Column("confidence", Float),
    Column("source_filing", Text),        # e.g. "NVDA 10-K 2025 — Risk Factors"
    Column("discovered_at", TIMESTAMP(timezone=True), nullable=False),
    Column("updated_at", TIMESTAMP(timezone=True)),

    # A ticker pair + relationship type should be unique
    UniqueConstraint("ticker", "related_ticker", "relationship_type",
                     name="uq_scr_ticker_related_type"),
    Index("ix_scr_ticker", "ticker"),
    Index("ix_scr_related_ticker", "related_ticker"),
)


# ── watchlist ─────────────────────────────────────────────────────
# Tickers the user is actively tracking.
# Phase 2/3: triggers overnight analysis runs and supply chain discovery.

watchlist = Table(
    "watchlist",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    # Multi-tenancy: each user has their own watchlist.
    # The unique constraint is now (user_email, ticker) not just ticker.
    Column("user_email", Text, nullable=False),
    Column("ticker", Text, nullable=False),
    Column("added_at", TIMESTAMP(timezone=True), nullable=False),
    Column("notes", Text),
    # Optional sector hint — used as context for hybrid analysis
    Column("sector_id", Text),

    UniqueConstraint("user_email", "ticker", name="uq_watchlist_user_ticker"),
    Index("ix_watchlist_user_email", "user_email"),
)


# ── annotations ───────────────────────────────────────────────────
# User notes and overrides on signal cards (Phase 2 — User Insight Explorer).
# Feeds the personal track record: "you flagged NVDA BULLISH 7 days ago, +8.2%."

annotations = Table(
    "annotations",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("signal_card_id", BigInteger, nullable=False),  # FK → signal_cards.id
    # Multi-tenancy: the user who annotated this card.
    Column("user_email", Text, nullable=False),
    # AGREED | IGNORED | NOTED
    Column("action", Text, nullable=False),
    Column("note", Text),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False),

    Index("ix_annotations_signal_card_id", "signal_card_id"),
    Index("ix_annotations_user_email", "user_email"),
)


# ══════════════════════════════════════════════════════════════════
# PHASE 3 TABLES  (schema defined now — repositories built in Piece 6)
# ══════════════════════════════════════════════════════════════════

# ── agents ────────────────────────────────────────────────────────
# Agent definitions.  Each agent = fixed identity_layer + one or more skills.
# Built-in agents (is_builtin=True): Value, Momentum, Supply Chain, Risk Analyst.
# User-created agents (is_builtin=False): premium feature.

agents = Table(
    "agents",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("name", Text, nullable=False),
    Column("description", Text),
    # Fixed Markdown — guardrails, compliance, output format. Cannot be edited by users.
    Column("identity_layer", Text),
    Column("is_builtin", Boolean, nullable=False, server_default="false"),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False),
    Column("updated_at", TIMESTAMP(timezone=True)),

    Index("ix_agents_name", "name"),
)


# ── skills ────────────────────────────────────────────────────────
# Skill documents (Markdown) attached to an agent.
# skill_type:
#   "domain"     — analytical focus / reasoning approach (user-editable)
#   "prediction" — PREDICTION_SKILL.md, auto-evolved from verified track record
#
# Multiple skills compose: an agent can hold 3–5 skills simultaneously.
# The self-improving loop (Phase 3.3) rewrites the "prediction" skill monthly.

skills = Table(
    "skills",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("agent_id", BigInteger, nullable=False),   # FK → agents.id
    Column("name", Text, nullable=False),
    # domain | prediction
    Column("skill_type", Text, nullable=False),
    # The Markdown document injected into the agent's context after identity_layer
    Column("content", Text, nullable=False),
    # Incremented every time the skill is updated (prediction skills auto-bump)
    Column("version", Integer, nullable=False, server_default="1"),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False),
    Column("updated_at", TIMESTAMP(timezone=True), nullable=False),

    Index("ix_skills_agent_id", "agent_id"),
    Index("ix_skills_skill_type", "skill_type"),
)


# ══════════════════════════════════════════════════════════════════
# USER PROFILE TABLE
# ══════════════════════════════════════════════════════════════════

# ── user_details ─────────────────────────────────────────────────
# One row per authenticated user (keyed on Cloudflare email).
# Created on first login / profile update.  Stores display preferences
# and saved sector filters so the frontend can restore them.

user_details = Table(
    "user_details",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    # Primary identity — the email injected by Cloudflare Access.
    Column("email", Text, nullable=False, unique=True),
    # Optional display name the user sets in the Profile page.
    Column("username", Text),
    # Comma-separated sector_id values the user has saved as favourites.
    # Stored as JSONB array: ["semiconductors", "ev_battery"].
    Column("saved_sectors", JSONB),
    # UI / notification preferences as a freeform JSONB object.
    # Example: {"email_digest": true, "default_page_size": 20}
    Column("preferences", JSONB),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False),
    Column("updated_at", TIMESTAMP(timezone=True)),

    Index("ix_user_details_email", "email", unique=True),
)


# ══════════════════════════════════════════════════════════════════
# DDL HELPER
# ══════════════════════════════════════════════════════════════════

async def create_all_tables(engine) -> None:
    """
    Create all tables if they don't exist.  Idempotent — safe on every startup.

    PostgreSQL: uses SQLAlchemy metadata.create_all (JSONB + TIMESTAMPTZ).
    SQLite (local dev): runs raw DDL that mirrors the production schema but
        uses TEXT for JSONB columns and plain TEXT for timestamps.
        This matches the strategy used in backend/tests/conftest.py.

    For production schema changes (column renames, new indexes) use Alembic.
    """
    is_sqlite = str(engine.url).startswith("sqlite")

    if is_sqlite:
        _SQLITE_DDL = [
            """CREATE TABLE IF NOT EXISTS pipeline_runs (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id          TEXT NOT NULL UNIQUE,
                ticker          TEXT NOT NULL,
                sector_id       TEXT NOT NULL,
                status          TEXT NOT NULL DEFAULT 'pending',
                current_node    TEXT,
                error           TEXT,
                created_at      TEXT NOT NULL,
                started_at      TEXT,
                finished_at     TEXT,
                signal_card_id  INTEGER,
                node_executions TEXT,
                user_email      TEXT
            )""",
            """CREATE TABLE IF NOT EXISTS signal_cards (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker              TEXT NOT NULL,
                run_id              TEXT,
                agent_id            INTEGER,
                signal              TEXT NOT NULL,
                conviction          INTEGER,
                one_line            TEXT,
                key_catalyst        TEXT,
                key_risk            TEXT,
                confidence          REAL,
                signal_type         TEXT,
                validation_score    TEXT,
                supply_chain_impact TEXT,
                sources             TEXT,
                numerical_claims    TEXT,
                sector_context      TEXT,
                raw_pipeline_state  TEXT,
                created_at          TEXT NOT NULL,
                status              TEXT NOT NULL DEFAULT 'active',
                user_email          TEXT
            )""",
            """CREATE TABLE IF NOT EXISTS predictions (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                signal_card_id      INTEGER,
                report_id           INTEGER,
                ticker              TEXT NOT NULL,
                price_at_report     REAL,
                change_1w_at_report REAL,
                price_1w_later      REAL,
                actual_change_1w    REAL,
                checked_at          TEXT,
                prediction_correct  INTEGER,
                ai_direction        TEXT,
                ai_predicted_change TEXT,
                ai_reasoning        TEXT,
                ai_risk             TEXT,
                user_email          TEXT
            )""",
            """CREATE TABLE IF NOT EXISTS reports (
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
            )""",
            """CREATE TABLE IF NOT EXISTS supply_chain_relationships (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker            TEXT NOT NULL,
                related_ticker    TEXT NOT NULL,
                relationship_type TEXT NOT NULL,
                confidence        REAL,
                source_filing     TEXT,
                discovered_at     TEXT NOT NULL,
                updated_at        TEXT,
                UNIQUE(ticker, related_ticker, relationship_type)
            )""",
            """CREATE TABLE IF NOT EXISTS watchlist (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                user_email TEXT NOT NULL,
                ticker     TEXT NOT NULL,
                added_at   TEXT NOT NULL,
                notes      TEXT,
                sector_id  TEXT,
                UNIQUE(user_email, ticker)
            )""",
            """CREATE TABLE IF NOT EXISTS annotations (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                signal_card_id INTEGER NOT NULL,
                user_email     TEXT NOT NULL,
                action         TEXT NOT NULL,
                note           TEXT,
                created_at     TEXT NOT NULL
            )""",
            """CREATE TABLE IF NOT EXISTS agents (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                name           TEXT NOT NULL UNIQUE,
                description    TEXT,
                identity_layer TEXT,
                is_builtin     INTEGER NOT NULL DEFAULT 0,
                created_at     TEXT NOT NULL,
                updated_at     TEXT
            )""",
            """CREATE TABLE IF NOT EXISTS skills (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_id   INTEGER NOT NULL,
                name       TEXT NOT NULL,
                skill_type TEXT NOT NULL,
                content    TEXT NOT NULL,
                version    INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )""",
            """CREATE TABLE IF NOT EXISTS user_details (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                email         TEXT NOT NULL UNIQUE,
                username      TEXT,
                saved_sectors TEXT,
                preferences   TEXT,
                created_at    TEXT NOT NULL,
                updated_at    TEXT
            )""",
        ]
        async with engine.begin() as conn:
            for ddl in _SQLITE_DDL:
                await conn.execute(text(ddl))
    else:
        async with engine.begin() as conn:
            await conn.run_sync(metadata.create_all, checkfirst=True)
