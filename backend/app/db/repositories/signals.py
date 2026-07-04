"""
Signals repository — CRUD for signal_cards and pipeline_runs.

signal_cards is the Phase 1+ primary output (one structured JSON signal per
ticker per run).  pipeline_runs tracks live execution status for SSE streaming.

Operations:
    create_run(db, run_id, ticker, sector_id)           → int (run.id)
    update_run_status(db, run_id, ...)                  → None
    get_run(db, run_id)                                 → PipelineRunSchema | None
    list_runs(db, *, ticker, page, page_size)           → (items, total)

    create_signal_card(db, data)                        → int (card.id)
    get_signal_card(db, card_id)                        → SignalCardSchema | None
    get_latest_signal(db, ticker, agent_id)             → SignalCardSchema | None
    list_signal_cards(db, *, ticker, signal, signal_type, agent_id, page, page_size)
                                                        → (items, total)
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from sqlalchemy import func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncConnection

from app.db.tables import pipeline_runs, signal_cards
from app.schemas.analysis import (
    NumericalClaimSchema,
    SignalCardSchema,
    SignalSourceSchema,
    SupplyChainImpactSchema,
)
from app.schemas.pipeline import PipelineRunSchema, RunSummary


# ── Helpers ────────────────────────────────────────────────────────

def _normalize_ts(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str):
        raw = value.strip()
        if not raw:
            return ""
        candidate = raw.replace("Z", "+00:00")
        if "T" not in candidate and " " in candidate:
            candidate = candidate.replace(" ", "T", 1)
        try:
            dt = datetime.fromisoformat(candidate)
        except ValueError:
            return raw
    else:
        return str(value)

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _coerce_mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _row_to_signal_card(r: Any) -> SignalCardSchema:
    d = dict(r)
    d["created_at"] = _normalize_ts(d.get("created_at"))
    raw_state = _coerce_mapping(d.get("raw_pipeline_state"))
    d["analysis_text"] = str(raw_state.get("analysis_text") or "")
    d["news_summary"] = str(raw_state.get("news_summary") or "")
    d["data_sufficiency"] = str(raw_state.get("data_sufficiency") or "")
    d["sufficiency_reasoning"] = str(raw_state.get("sufficiency_reasoning") or "")
    d["anomaly_alerts"] = raw_state.get("anomaly_alerts") or []
    d["article_evidence"] = raw_state.get("articles") or []
    d["price_snapshot"] = raw_state.get("prices") or []
    d["technical_snapshot"] = raw_state.get("technicals") or []
    d["reasoning_scores"] = raw_state.get("reasoning_scores") or {}
    d["confidence_breakdown"] = raw_state.get("confidence_breakdown") or {}
    d["rag_metadata"] = raw_state.get("rag_metadata") or {}
    # Legacy rows lack this flag → default True (treat their conviction as stated).
    d["conviction_stated"] = bool(raw_state.get("conviction_stated", True))

    # Deserialize JSONB → typed sub-schemas
    d["numerical_claims"] = [
        NumericalClaimSchema.model_validate(c)
        for c in (d.get("numerical_claims") or [])
    ]
    d["sources"] = [
        SignalSourceSchema.model_validate(s)
        for s in (d.get("sources") or [])
    ]
    d["supply_chain_impact"] = [
        SupplyChainImpactSchema.model_validate(i)
        for i in (d.get("supply_chain_impact") or [])
    ]

    # Exclude internal-only JSONB blobs from the API response
    d.pop("sector_context", None)
    d.pop("raw_pipeline_state", None)

    return SignalCardSchema.model_validate(d)


def _row_to_run(r: Any) -> PipelineRunSchema:
    d = dict(r)
    d["created_at"] = _normalize_ts(d.get("created_at"))
    d["started_at"] = _normalize_ts(d.get("started_at")) or None
    d["finished_at"] = _normalize_ts(d.get("finished_at")) or None
    d["node_executions"] = d.get("node_executions") or []
    return PipelineRunSchema.model_validate(d)


# ══════════════════════════════════════════════════════════════════
# pipeline_runs — live execution tracking
# ══════════════════════════════════════════════════════════════════

async def create_run(
    db: AsyncConnection,
    run_id: str,
    ticker: str,
    sector_id: str,
    agent_id: int | None = None,
    agent_name: str | None = None,
    user_email: str | None = None,
) -> int:
    """Insert a new pipeline_runs row.  Returns the integer PK."""
    result = await db.execute(
        insert(pipeline_runs)
        .values(
            run_id=run_id,
            ticker=ticker.upper(),
            sector_id=sector_id,
            agent_id=agent_id,
            agent_name=agent_name,
            status="pending",
            user_email=user_email,
            created_at=datetime.now(timezone.utc),
        )
        .returning(pipeline_runs.c.id)
    )
    return result.scalar_one()


async def update_run_status(
    db: AsyncConnection,
    run_id: str,
    *,
    status: Literal["pending", "running", "completed", "failed"],
    current_node: str | None = None,
    error: str | None = None,
    signal_card_id: int | None = None,
    node_executions: list[dict] | None = None,
    started_at: datetime | None = None,
    finished_at: datetime | None = None,
) -> None:
    """
    Update a pipeline run's status and optional metadata fields.

    Called by the pipeline orchestrator after each node completes,
    and once more when the full run finishes or fails.
    """
    values: dict[str, Any] = {"status": status}
    if current_node is not None:
        values["current_node"] = current_node
    if error is not None:
        values["error"] = error
    if signal_card_id is not None:
        values["signal_card_id"] = signal_card_id
    if node_executions is not None:
        values["node_executions"] = node_executions
    if started_at is not None:
        values["started_at"] = started_at
    if finished_at is not None:
        values["finished_at"] = finished_at

    stmt = update(pipeline_runs).where(pipeline_runs.c.run_id == run_id)
    if status in ("pending", "running"):
        stmt = stmt.where(pipeline_runs.c.status.notin_(["completed", "failed"]))

    await db.execute(stmt.values(**values))


async def get_run(db: AsyncConnection, run_id: str) -> PipelineRunSchema | None:
    """Fetch a single pipeline run by its UUID string."""
    row = (
        await db.execute(
            select(pipeline_runs).where(pipeline_runs.c.run_id == run_id)
        )
    ).mappings().first()

    return _row_to_run(row) if row else None


async def get_run_for_user(
    db: AsyncConnection,
    run_id: str,
    user_email: str | None = None,
) -> PipelineRunSchema | None:
    """Fetch one run, scoped to the requesting user when available."""
    q = select(pipeline_runs).where(pipeline_runs.c.run_id == run_id)
    if user_email:
        q = q.where(
            (pipeline_runs.c.user_email == user_email)
            | (pipeline_runs.c.user_email.is_(None))
        )
    row = (await db.execute(q)).mappings().first()
    return _row_to_run(row) if row else None


async def list_runs(
    db: AsyncConnection,
    *,
    ticker: str | None = None,
    user_email: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[RunSummary], int]:
    """Paginated list of pipeline runs, scoped to the requesting user."""
    q = select(
        pipeline_runs.c.run_id,
        pipeline_runs.c.ticker,
        pipeline_runs.c.sector_id,
        pipeline_runs.c.agent_id,
        pipeline_runs.c.agent_name,
        pipeline_runs.c.status,
        pipeline_runs.c.created_at,
        pipeline_runs.c.started_at,
        pipeline_runs.c.finished_at,
        pipeline_runs.c.current_node,
        pipeline_runs.c.error,
        pipeline_runs.c.signal_card_id,
    ).order_by(pipeline_runs.c.created_at.desc())

    count_q = select(func.count()).select_from(pipeline_runs)

    # Scope to the user.  Legacy rows (user_email IS NULL) are shared.
    if user_email:
        user_filter = (
            (pipeline_runs.c.user_email == user_email)
            | (pipeline_runs.c.user_email.is_(None))
        )
        q = q.where(user_filter)
        count_q = count_q.where(user_filter)

    if ticker:
        q = q.where(pipeline_runs.c.ticker == ticker.upper())
        count_q = count_q.where(pipeline_runs.c.ticker == ticker.upper())

    total: int = (await db.execute(count_q)).scalar_one()
    rows = (
        await db.execute(q.limit(page_size).offset((page - 1) * page_size))
    ).mappings().all()

    items = []
    for r in rows:
        d = dict(r)
        if d.get("error") and d.get("status") != "completed":
            d["status"] = "failed"
        d["created_at"] = _normalize_ts(d.get("created_at"))
        d["started_at"] = _normalize_ts(d.get("started_at")) or None
        d["finished_at"] = _normalize_ts(d.get("finished_at")) or None
        items.append(RunSummary.model_validate(d))

    return items, total


async def count_active_runs(
    db: AsyncConnection,
    *,
    user_email: str | None = None,
) -> int:
    """
    Number of runs currently pending or running for a user.

    Used to enforce a per-user concurrency cap on the trigger endpoints so a
    single client cannot flood the thread pool with hundreds of queued runs.
    """
    count_q = (
        select(func.count())
        .select_from(pipeline_runs)
        .where(pipeline_runs.c.status.in_(("pending", "running")))
    )
    if user_email:
        count_q = count_q.where(pipeline_runs.c.user_email == user_email)
    return int((await db.execute(count_q)).scalar_one())


async def count_runs_since(
    db: AsyncConnection,
    *,
    user_email: str,
    since: datetime,
) -> int:
    """
    Number of runs a user has started since a given UTC instant.

    Backs the per-user daily free-analysis quota (which resets at 00:00 UTC).
    """
    count_q = (
        select(func.count())
        .select_from(pipeline_runs)
        .where(pipeline_runs.c.user_email == user_email)
        .where(pipeline_runs.c.created_at >= since)
    )
    return int((await db.execute(count_q)).scalar_one())


async def fail_stale_runs(
    db: AsyncConnection,
    *,
    older_than_minutes: int | None = None,
    reason: str = "Run was interrupted (server restart) and did not finish.",
) -> int:
    """
    Mark pending/running runs as failed so they can't appear "stuck" forever.

    The pipeline executes in an in-process thread pool, so any run still marked
    pending/running after a restart is an orphan that can never complete. Two
    modes:

      * ``older_than_minutes=None`` — fail ALL in-flight runs. Used once at
        startup to reconcile orphans left by the previous process.
      * ``older_than_minutes=N``    — fail only runs created more than N minutes
        ago. Used by the periodic reaper to clear genuine zombies without
        touching healthy, recently-started runs.

    Returns the number of runs updated.
    """
    now = datetime.now(timezone.utc)
    stmt = update(pipeline_runs).where(
        pipeline_runs.c.status.in_(("pending", "running"))
    )
    if older_than_minutes is not None:
        cutoff = now - timedelta(minutes=older_than_minutes)
        stmt = stmt.where(pipeline_runs.c.created_at <= cutoff)
    result = await db.execute(
        stmt.values(status="failed", error=reason, finished_at=now)
    )
    return int(result.rowcount or 0)


# ══════════════════════════════════════════════════════════════════
# signal_cards — Phase 1+ primary output
# ══════════════════════════════════════════════════════════════════

async def create_signal_card(
    db: AsyncConnection,
    *,
    ticker: str,
    run_id: str | None = None,
    agent_id: int | None = None,
    signal: Literal["BULLISH", "BEARISH", "NEUTRAL"],
    conviction: int,
    one_line: str,
    key_catalyst: str = "",
    key_risk: str = "",
    confidence: float = 0.0,
    signal_type: str | None = None,
    validation_score: str = "",
    numerical_claims: list[dict] | None = None,
    sources: list[dict] | None = None,
    supply_chain_impact: list[dict] | None = None,
    sector_context: dict | None = None,
    raw_pipeline_state: dict | None = None,
    user_email: str | None = None,
    status: str = "active",
) -> int:
    """
    Insert a signal card row.  Returns the new card's integer PK.

    Called by the pipeline save node after a successful analysis run.
    """
    result = await db.execute(
        insert(signal_cards)
        .values(
            ticker=ticker.upper(),
            run_id=run_id,
            agent_id=agent_id,
            signal=signal,
            conviction=conviction,
            one_line=one_line,
            key_catalyst=key_catalyst,
            key_risk=key_risk,
            confidence=confidence,
            signal_type=signal_type,
            validation_score=validation_score,
            numerical_claims=numerical_claims or [],
            sources=sources or [],
            supply_chain_impact=supply_chain_impact or [],
            sector_context=sector_context,
            raw_pipeline_state=raw_pipeline_state,
            user_email=user_email,
            status=status,
            created_at=datetime.now(timezone.utc),
        )
        .returning(signal_cards.c.id)
    )
    return result.scalar_one()


async def get_signal_card(
    db: AsyncConnection,
    card_id: int,
    user_email: str | None = None,
) -> SignalCardSchema | None:
    """
    Fetch a single signal card by PK.

    When user_email is provided the row must belong to that user OR be a
    legacy row (user_email IS NULL).  Returns None if the card exists but
    belongs to a different user — the router translates this to a 404.
    """
    q = select(signal_cards).where(signal_cards.c.id == card_id)
    if user_email:
        q = q.where(
            (signal_cards.c.user_email == user_email)
            | (signal_cards.c.user_email.is_(None))
        )
    row = (await db.execute(q)).mappings().first()
    return _row_to_signal_card(row) if row else None


async def get_latest_signal(
    db: AsyncConnection,
    ticker: str,
    agent_id: int | None = None,
    user_email: str | None = None,
) -> SignalCardSchema | None:
    """
    Return the most recent signal card for a ticker (optionally for a specific agent).

    Scoped to user_email when provided; legacy rows (NULL) are always visible.
    """
    q = (
        select(signal_cards)
        .where(signal_cards.c.ticker == ticker.upper())
        .order_by(signal_cards.c.created_at.desc())
        .limit(1)
    )
    if agent_id is not None:
        q = q.where(signal_cards.c.agent_id == agent_id)
    if user_email:
        q = q.where(
            (signal_cards.c.user_email == user_email)
            | (signal_cards.c.user_email.is_(None))
        )

    row = (await db.execute(q)).mappings().first()
    return _row_to_signal_card(row) if row else None


async def list_signal_cards(
    db: AsyncConnection,
    *,
    ticker: str | None = None,
    signal: str | None = None,
    signal_type: str | None = None,
    agent_id: int | None = None,
    market: str | None = None,
    user_email: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[SignalCardSchema], int]:
    """
    Paginated list of signal cards with optional filters.

    Supports the Morning Brief filters (Phase 2 — User Insight Explorer):
        ticker      → "show me all signals for NVDA"
        signal      → "show me only BULLISH signals"
        signal_type → "show me only FUNDAMENTAL_SHIFT signals"
        agent_id    → "show me signals from the Supply Chain Analyst agent"
        market      → "show me only HK (or US) tickers" (hk = '*.HK' suffix)
    """
    # Exclude large JSONB blobs from list responses
    list_cols = [
        signal_cards.c.id,
        signal_cards.c.ticker,
        signal_cards.c.run_id,
        signal_cards.c.agent_id,
        signal_cards.c.signal,
        signal_cards.c.conviction,
        signal_cards.c.one_line,
        signal_cards.c.key_catalyst,
        signal_cards.c.key_risk,
        signal_cards.c.confidence,
        signal_cards.c.signal_type,
        signal_cards.c.validation_score,
        signal_cards.c.numerical_claims,
        signal_cards.c.sources,
        signal_cards.c.supply_chain_impact,
        signal_cards.c.created_at,
        signal_cards.c.status,
    ]

    q = select(*list_cols).order_by(signal_cards.c.created_at.desc())
    count_q = select(func.count()).select_from(signal_cards)

    # Scope to the requesting user; legacy rows (user_email IS NULL) are shared.
    if user_email:
        user_filter = (
            (signal_cards.c.user_email == user_email)
            | (signal_cards.c.user_email.is_(None))
        )
        q = q.where(user_filter)
        count_q = count_q.where(user_filter)

    if ticker:
        q = q.where(signal_cards.c.ticker == ticker.upper())
        count_q = count_q.where(signal_cards.c.ticker == ticker.upper())
    if signal:
        q = q.where(signal_cards.c.signal == signal.upper())
        count_q = count_q.where(signal_cards.c.signal == signal.upper())
    if signal_type:
        q = q.where(signal_cards.c.signal_type == signal_type.upper())
        count_q = count_q.where(signal_cards.c.signal_type == signal_type.upper())
    if agent_id is not None:
        q = q.where(signal_cards.c.agent_id == agent_id)
        count_q = count_q.where(signal_cards.c.agent_id == agent_id)
    if market:
        m = market.strip().lower()
        if m == "hk":
            q = q.where(signal_cards.c.ticker.like("%.HK"))
            count_q = count_q.where(signal_cards.c.ticker.like("%.HK"))
        elif m == "us":
            q = q.where(signal_cards.c.ticker.notlike("%.HK"))
            count_q = count_q.where(signal_cards.c.ticker.notlike("%.HK"))

    total: int = (await db.execute(count_q)).scalar_one()
    rows = (
        await db.execute(q.limit(page_size).offset((page - 1) * page_size))
    ).mappings().all()

    return [_row_to_signal_card(r) for r in rows], total
