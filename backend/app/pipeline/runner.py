"""
Pipeline bridge — the async-to-sync boundary between FastAPI and the
legacy synchronous LangGraph pipeline (workflows/weekly_analysis.py).

Architecture
────────────
The legacy pipeline is fully blocking: it calls the LLM, SEC EDGAR, Yahoo
Finance, ChromaDB, etc. all on the calling thread.  We can't run it on the
asyncio event loop thread.  Instead we run it in a ThreadPoolExecutor and
use asyncio.Queue to push SSE events back to the HTTP response.

Each pipeline run gets its own asyncio.Queue[SSEEvent | None] registered in
_queues.  The sync thread pushes events via run_coroutine_threadsafe(); the
SSE route handler pops them with Queue.get().  A None sentinel signals
end-of-stream.

sys.path bridge
───────────────
The FYP repo root (parent of backend/) contains the legacy modules:
    workflows/, config/, models/, data_sources/, vectordb/, ...

We add it to sys.path at module load time so those imports work when the
FastAPI process starts from inside backend/.

Public API
──────────
    launch_run(run_id, ticker, sector_id, ...)   → None   (non-blocking)
    get_queue(run_id)                            → Queue | None
    drop_queue(run_id)                           → None
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ── sys.path: make the FYP repo root importable from backend/ ─────
# Resolve: backend/app/pipeline/runner.py
#   parents[0] = backend/app/pipeline/
#   parents[1] = backend/app/
#   parents[2] = backend/
#   parents[3] = FYP root  (contains workflows/, config/, models/, ...)
_REPO_ROOT = str(Path(__file__).resolve().parents[3])
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from app.schemas.pipeline import SSEEvent  # noqa: E402 — after path patch
from app.core.config import settings  # noqa: E402 — after path patch
from app.pipeline.signal_extractor import (  # noqa: E402
    SignalCardDraft,
    from_pipeline_state,
    is_failed_validation_status,
)

logger = logging.getLogger(__name__)

# Progress label → canonical node name (matches _NODE_LABELS in weekly_analysis.py)
_LABEL_TO_NODE: dict[str, str] = {
    "📡 Fetching data (news, prices, SEC filings, macro)…": "fetch",
    "📝 Summarizing articles…": "summarize",
    "🤔 Evaluating data sufficiency…": "reflect",
    "🧠 Running deep analysis (RAG + LLM)…": "analyze",
    "✅ Validating analysis (numbers + reasoning)…": "validate",
    "📊 Computing confidence score…": "score",
    "💾 Saving report…": "save",
}

_BASE_NODE_COUNT = 7  # fetch → save (for progress % calculation)

# ── Thread pool (shared across all runs) ──────────────────────────
_executor = ThreadPoolExecutor(
    max_workers=settings.pipeline_max_workers,
    thread_name_prefix="pipeline",
)


def pipeline_worker_count() -> int:
    """Return the configured global pipeline worker capacity."""
    return settings.pipeline_max_workers

# ── Per-run event queues ───────────────────────────────────────────
_queues: dict[str, asyncio.Queue] = {}
# Wall-clock creation time per run_id, used to reap orphaned queues whose
# SSE stream is never opened (which would otherwise leak forever).
_queue_created_at: dict[str, float] = {}


# ══════════════════════════════════════════════════════════════════
# Queue management
# ══════════════════════════════════════════════════════════════════

def _register_queue(run_id: str) -> asyncio.Queue:
    _reap_orphan_queues()
    q: asyncio.Queue[SSEEvent | None] = asyncio.Queue(
        maxsize=max(settings.sse_queue_maxsize, 16)
    )
    _queues[run_id] = q
    _queue_created_at[run_id] = time.monotonic()
    return q


def get_queue(run_id: str) -> asyncio.Queue | None:
    """Return the live event queue for a run, or None if the run is finished."""
    return _queues.get(run_id)


def drop_queue(run_id: str) -> None:
    """Remove and discard the queue for a completed/failed run."""
    _queues.pop(run_id, None)
    _queue_created_at.pop(run_id, None)


def _reap_orphan_queues() -> None:
    """
    Drop queues older than the configured TTL.

    A queue is only removed by the SSE stream handler's ``finally`` block.
    If a run's stream is never opened (client crashed, board fanout the user
    never watched), its queue would linger forever.  We sweep on each new
    launch — cheap because the live-run count is bounded by the worker pool.
    """
    ttl = settings.sse_queue_orphan_ttl_seconds
    if not _queue_created_at:
        return
    cutoff = time.monotonic() - ttl
    stale = [
        run_id
        for run_id, created in _queue_created_at.items()
        if created < cutoff
    ]
    for run_id in stale:
        logger.warning("Reaping orphaned SSE queue for run %s (>%ss old)", run_id, ttl)
        drop_queue(run_id)


def _offer_threadsafe(
    run_id: str,
    event: "SSEEvent | None",
    loop: asyncio.AbstractEventLoop,
) -> None:
    """
    Enqueue an event onto a run's bounded queue from a worker thread.

    The producer runs in the ThreadPoolExecutor, so it must not block on a
    full queue (that would stall a pipeline worker indefinitely when no SSE
    consumer is draining).  On overflow we drop the oldest event to keep the
    buffer bounded and the most recent progress visible.  The ``None`` close
    sentinel is always delivered (it evicts an old event if necessary).
    """
    q = _queues.get(run_id)
    if q is None:
        return
    asyncio.run_coroutine_threadsafe(_offer(q, event), loop)


async def _offer(q: asyncio.Queue, event: "SSEEvent | None") -> None:
    try:
        q.put_nowait(event)
    except asyncio.QueueFull:
        # Drop the oldest buffered event to make room for the newest.
        try:
            q.get_nowait()
        except asyncio.QueueEmpty:
            pass
        try:
            q.put_nowait(event)
        except asyncio.QueueFull:  # pragma: no cover — race, best-effort
            pass


# ══════════════════════════════════════════════════════════════════
# DB helper — async update callable from the background thread
# ══════════════════════════════════════════════════════════════════

async def _db_update(run_id: str, **kwargs: Any) -> None:
    """Open a fresh async connection and update the pipeline_runs row."""
    from app.db.engine import get_engine
    from app.db.repositories import signals as repo

    async with get_engine().begin() as conn:
        await repo.update_run_status(conn, run_id, **kwargs)


def _prediction_rows_from_state(state: Any) -> list[dict[str, Any]]:
    """Build prediction rows from the legacy PipelineState price snapshots."""
    ai_predictions = getattr(state, "ai_predictions", None) or []
    ai_by_ticker = {
        str(pred.get("ticker", "")).upper(): pred
        for pred in ai_predictions
        if isinstance(pred, dict) and pred.get("ticker")
    }

    rows: list[dict[str, Any]] = []
    for price in getattr(state, "prices", None) or []:
        if not isinstance(price, dict) or price.get("error") or not price.get("price"):
            continue
        ticker = str(price.get("ticker", "")).upper()
        if not ticker:
            continue
        ai = ai_by_ticker.get(ticker, {})
        rows.append({
            "ticker": ticker,
            "price_at_report": price.get("price"),
            "change_1w_at_report": price.get("change_1w_pct"),
            "ai_direction": ai.get("direction"),
            "ai_predicted_change": ai.get("predicted_change") or ai.get("predicted_change_pct"),
            "ai_reasoning": ai.get("reasoning"),
            "ai_risk": ai.get("key_risk") or ai.get("risk_level"),
        })
    return rows


async def _persist_card(draft: SignalCardDraft, state: Any | None = None) -> int:
    """Insert a signal card row built from the finished PipelineState.

    Returns the new card's integer PK so the caller can wire it into the
    pipeline_runs row and the pipeline_completed SSE event.
    """
    from app.db.engine import get_engine
    from app.db.repositories.signals import create_signal_card
    from app.db.repositories.predictions import create_for_signal_card

    payload = draft.model_dump(exclude={"created_at"})
    async with get_engine().begin() as conn:
        card_id = await create_signal_card(conn, **payload)
        if state is not None:
            await create_for_signal_card(
                conn,
                card_id,
                _prediction_rows_from_state(state),
                user_email=draft.user_email,
            )
        return card_id


async def _maybe_autogenerate_verdict(
    run_id: str,
    ticker: str,
    user_email: str | None,
) -> None:
    """
    After an analyst run finishes, auto-generate the Chief Strategist's house
    verdict for the ticker — but only once the whole board has reported.

    "Last to finish" is detected by counting OTHER pipeline_runs for the same
    ticker (and user) that are still pending/running. When none remain, this
    run was the last analyst, so the desk can issue its final call.
    """
    from sqlalchemy import and_, func, or_, select

    from app.db.engine import get_engine
    from app.db.repositories import chief_verdicts as verdict_repo
    from app.db.tables import pipeline_runs
    from app.services.chief_strategist import generate_verdict

    symbol = ticker.upper()
    try:
        async with get_engine().begin() as conn:
            # Are any sibling analyst runs for this ticker still in flight?
            scope = pipeline_runs.c.ticker == symbol
            if user_email:
                scope = and_(
                    scope,
                    or_(
                        pipeline_runs.c.user_email == user_email,
                        pipeline_runs.c.user_email.is_(None),
                    ),
                )
            active = (
                await conn.execute(
                    select(func.count())
                    .select_from(pipeline_runs)
                    .where(
                        and_(
                            scope,
                            pipeline_runs.c.run_id != run_id,
                            pipeline_runs.c.status.notin_(["completed", "failed"]),
                        )
                    )
                )
            ).scalar_one()
            if active and active > 0:
                return  # board still working — a later run will trigger this

            # Avoid duplicate verdicts when siblings finish near-simultaneously.
            existing = await verdict_repo.latest_for_ticker(conn, symbol, user_email)
            if existing is not None and existing.created_at:
                from datetime import datetime as _dt

                try:
                    created = _dt.fromisoformat(existing.created_at)
                    if created.tzinfo is None:
                        created = created.replace(tzinfo=timezone.utc)
                    age = (datetime.now(timezone.utc) - created).total_seconds()
                    if age < 90:
                        return
                except ValueError:
                    pass

            await generate_verdict(
                conn, symbol, user_email, run_id=run_id, persist=True
            )
    except Exception:  # pragma: no cover - auto-verdict is best-effort
        logger.exception("Auto-verdict generation failed for %s", symbol)


def _validation_failure_message(draft: SignalCardDraft) -> str:
    """Build a concise, user-visible explanation for needs-review cards."""
    base = (
        f"Validation failed ({draft.validation_score or 'FAILED'}); "
        "signal card was published for review but must not be treated as actionable."
    )
    raw_state = draft.raw_pipeline_state or {}
    issues = raw_state.get("validation_issues") if isinstance(raw_state, dict) else None
    if not issues:
        return base

    issue_lines: list[str] = []
    for issue in issues[:3]:
        if isinstance(issue, dict):
            text = issue.get("claim") or issue.get("message") or str(issue)
        else:
            text = str(issue)
        text = " ".join(text.split())[:240]
        if text:
            issue_lines.append(text)

    if not issue_lines:
        return base
    return f"{base} Top issues: {' | '.join(issue_lines)}"


# ══════════════════════════════════════════════════════════════════
# Progress bridge — runs inside the ThreadPoolExecutor
# ══════════════════════════════════════════════════════════════════

class _ProgressBridge:
    """
    Synchronous callable that translates progress_fn(event_type, message)
    calls from the legacy pipeline into SSEEvent puts on the run's queue.

    Called from inside the ThreadPoolExecutor — never touches the event loop
    directly.  All async operations go through run_coroutine_threadsafe().
    """

    def __init__(self, run_id: str, loop: asyncio.AbstractEventLoop) -> None:
        self.run_id = run_id
        self.loop = loop
        self._node_seq: list[str] = []

    # ── Internal helpers ──────────────────────────────────────────

    def _put(self, event: SSEEvent) -> None:
        q = _queues.get(self.run_id)
        if q is not None:
            _offer_threadsafe(self.run_id, event, self.loop)

    def _db(self, **kwargs: Any) -> None:
        """Fire-and-forget DB update from the pipeline thread."""
        asyncio.run_coroutine_threadsafe(
            _db_update(self.run_id, **kwargs), self.loop
        )

    def _progress_pct(self, n_completed: int) -> float:
        return round(min(n_completed / _BASE_NODE_COUNT * 100, 99.0), 1)

    # ── progress_fn interface (called by _node_wrapper) ───────────

    def __call__(self, event_type: str, message: str) -> None:
        if event_type != "node":
            return  # step / sector_start / sector_done → ignore for SSE

        node_name = _LABEL_TO_NODE.get(message, message)

        # Complete the previous node before announcing this one
        if self._node_seq:
            prev = self._node_seq[-1]
            self._put(SSEEvent(
                event="node_completed",
                run_id=self.run_id,
                data={
                    "node": prev,
                    "progress_pct": self._progress_pct(len(self._node_seq)),
                },
            ))

        self._node_seq.append(node_name)

        # Update the DB polling endpoint so it shows the current node
        self._db(status="running", current_node=node_name)

        self._put(SSEEvent(
            event="node_started",
            run_id=self.run_id,
            data={
                "node": node_name,
                "label": message,
                "progress_pct": self._progress_pct(len(self._node_seq) - 1),
            },
        ))

    # ── Terminal events ───────────────────────────────────────────

    def finalize_success(
        self,
        result: dict[str, Any],
        signal_card_id: int | None = None,
    ) -> None:
        """Emit the final node_completed + pipeline_completed events."""
        if self._node_seq:
            self._put(SSEEvent(
                event="node_completed",
                run_id=self.run_id,
                data={"node": self._node_seq[-1], "progress_pct": 99.0},
            ))
        self._put(SSEEvent(
            event="pipeline_completed",
            run_id=self.run_id,
            data={
                "report_id": result.get("report_id"),
                "confidence": result.get("confidence"),
                "signal_card_id": signal_card_id,
            },
        ))

    def finalize_failure(self, error: str) -> None:
        self._put(SSEEvent(
            event="pipeline_failed",
            run_id=self.run_id,
            data={"message": error},
        ))

    def node_executions_for_db(self) -> list[dict[str, Any]]:
        """Minimal node records for storage in pipeline_runs.node_executions."""
        return [{"node_name": n, "status": "completed"} for n in self._node_seq]


# ══════════════════════════════════════════════════════════════════
# Sync pipeline executor (runs inside the ThreadPoolExecutor)
# ══════════════════════════════════════════════════════════════════

def _execute_pipeline(
    run_id: str,
    ticker: str,
    sector_id: str,
    user_email: str | None,
    agent_id: int | None,
    agent_name: str,
    agent_identity: str,
    max_fetch_retries: int,
    max_validation_retries: int,
    model_override: str,
    loop: asyncio.AbstractEventLoop,
    synthesis: bool = False,
    llm_api_key: str = "",
    llm_base_url: str = "",
    llm_model: str = "",
) -> None:
    """
    Blocking function — always called from the ThreadPoolExecutor, never
    from the event loop thread.

    1. Imports legacy modules lazily (path patch is applied at module import time).
    2. Runs run_sector_analysis() with the progress bridge.
    3. Persists terminal status to the DB.
    4. Sends None sentinel to close the SSE stream.

    When ``synthesis`` is True the run analyses the WHOLE sector as one board-
    level signal (macro → trend → second-order effects) instead of narrowing to
    a single ticker.
    """
    bridge = _ProgressBridge(run_id, loop)

    def _db(**kwargs: Any) -> None:
        asyncio.run_coroutine_threadsafe(_db_update(run_id, **kwargs), loop)

    _db(status="running", started_at=datetime.now(timezone.utc))

    try:
        # Lazy imports — executed after _REPO_ROOT is on sys.path
        from config.sectors import SECTORS  # type: ignore[import]
        from workflows.weekly_analysis import run_sector_analysis  # type: ignore[import]
        from agents.llm_client import llm_credentials_override  # type: ignore[import]

        sector_cfg = SECTORS.get(sector_id)
        if sector_cfg is None and synthesis:
            # Market sectors (us_*/hk_*) live in config/markets.py, not the
            # legacy supply-chain catalog. Build a full-roster config so the
            # strategist reasons across every constituent.
            from config.markets import get_sector as _get_market_sector  # type: ignore[import]

            market_sector = _get_market_sector(sector_id)
            if market_sector is not None:
                constituents = [str(t).upper() for t in market_sector.get("constituents", [])]
                sector_cfg = {
                    "name": market_sector.get("name", sector_id),
                    "description": (
                        f"{market_sector.get('name', sector_id)} sector. "
                        f"Tracked via {market_sector.get('instrument_name', 'a sector instrument')}. "
                        f"Constituents: {', '.join(constituents)}."
                    ),
                    "tickers": constituents,
                    "supply_chain_map": {},
                    "keywords": [market_sector.get("name", sector_id), *constituents],
                }

        if sector_cfg is None:
            # Free-form ticker outside the curated catalog. Build a minimal
            # single-name "sector" so the board can still analyse it. No
            # supply-chain map is available, so second-order reasoning is
            # limited to whatever the analysts can infer from the data.
            sector_cfg = {
                "name": f"{ticker.upper()} (uncategorized)",
                "description": (
                    f"Standalone analysis for {ticker.upper()} — not part of a "
                    "curated supply-chain sector."
                ),
                "tickers": [ticker.upper()],
                "supply_chain_map": {},
                "keywords": [ticker.upper()],
            }

        if synthesis:
            # Board-wide synthesis: keep the FULL sector roster so the strategist
            # can reason about cross-company and supply-chain cascades. Swap in
            # the Sector Strategist identity so the analyze node adopts the
            # macro → trend → second-order lens.
            from app.core.builtin_agents import (  # type: ignore[import]
                SECTOR_STRATEGIST_NAME,
                SECTOR_SYNTHESIS_PROMPT,
            )

            narrowed_cfg = sector_cfg
            agent_identity = SECTOR_SYNTHESIS_PROMPT
            agent_name = agent_name or SECTOR_STRATEGIST_NAME
        else:
            # Narrow to just the requested ticker so the LLM focuses on it.
            # Fall back to the full sector list if the ticker isn't pre-defined.
            ticker_list = [t for t in sector_cfg["tickers"] if t == ticker.upper()]
            narrowed_cfg = {**sector_cfg, "tickers": ticker_list or sector_cfg["tickers"]}


        # Per-run browser-supplied credentials are scoped to this worker
        # thread for the whole synchronous pipeline, then cleared. A blank key
        # is a no-op and the server's env credentials are used instead.
        with llm_credentials_override(llm_api_key, llm_base_url, llm_model):
            result = run_sector_analysis(
                sector_id=sector_id,
                sector=narrowed_cfg,
                agent_id=agent_id,
                agent_name=agent_name,
                agent_identity=agent_identity,
                progress_fn=bridge,
                max_fetch_retries=max_fetch_retries,
                max_validation_retries=max_validation_retries,
                model_override=model_override,
            )
        if result.get("error"):
            raise RuntimeError(result["error"])

        # ── Pipeline → signal_cards bridge ────────────────────────
        # Build a SignalCardDraft from the final PipelineState and
        # persist via run_coroutine_threadsafe (we're on a worker thread).
        card_id: int | None = None
        state = result.get("pipeline_state")
        if state is not None:
            try:
                draft = from_pipeline_state(
                    state=state,
                    run_id=run_id,
                    ticker=ticker,
                    user_email=user_email,
                    agent_id=agent_id,
                )
                if is_failed_validation_status(draft.validation_score):
                    draft = draft.model_copy(update={"status": "needs_review"})
                    logger.warning(
                        "Publishing needs-review signal card for run %s due to validation status %r",
                        run_id,
                        draft.validation_score,
                    )
                future = asyncio.run_coroutine_threadsafe(
                    _persist_card(draft, state), loop
                )
                card_id = future.result(timeout=30)
            except Exception:
                logger.exception(
                    "Failed to persist signal card for run %s — "
                    "continuing without it", run_id,
                )

        bridge.finalize_success(result, signal_card_id=card_id)

        _db(
            status="completed",
            finished_at=datetime.now(timezone.utc),
            node_executions=bridge.node_executions_for_db(),
            signal_card_id=card_id,
        )

        # ── Chief Strategist auto-verdict ─────────────────────────
        # Once the last analyst for this ticker has reported, the desk issues
        # its final house call. Skipped for sector-wide synthesis runs.
        if not synthesis:
            try:
                verdict_future = asyncio.run_coroutine_threadsafe(
                    _maybe_autogenerate_verdict(run_id, ticker, user_email), loop
                )
                verdict_future.result(timeout=90)
            except Exception:  # pragma: no cover - best-effort
                logger.exception(
                    "Auto-verdict step failed for run %s", run_id
                )

    except Exception as exc:
        logger.exception("Pipeline run %s failed", run_id)
        bridge.finalize_failure(str(exc))
        _db(
            status="failed",
            error=str(exc)[:2000],  # truncate for the DB column
            finished_at=datetime.now(timezone.utc),
        )

    finally:
        # Always send sentinel so the SSE generator exits cleanly
        q = _queues.get(run_id)
        if q is not None:
            _offer_threadsafe(run_id, None, loop)


# ══════════════════════════════════════════════════════════════════
# Public async API
# ══════════════════════════════════════════════════════════════════

async def launch_run(
    run_id: str,
    ticker: str,
    sector_id: str,
    user_email: str | None = None,
    agent_id: int | None = None,
    agent_name: str = "",
    agent_identity: str = "",
    max_fetch_retries: int = 1,
    max_validation_retries: int = 1,
    model_override: str = "",
    synthesis: bool = False,
    llm_api_key: str = "",
    llm_base_url: str = "",
    llm_model: str = "",
) -> None:
    """
    Register the SSE event queue for run_id and submit the blocking pipeline
    to the thread pool.  Returns immediately.

    The caller should return run_id to the HTTP client.  Progress is
    available via get_queue(run_id) and the SSE /stream endpoint.

    When ``synthesis`` is True the run produces a single board-level sector
    synthesis card instead of narrowing to one ticker.
    """
    loop = asyncio.get_running_loop()
    _register_queue(run_id)
    future = loop.run_in_executor(
        _executor,
        _execute_pipeline,
        run_id,
        ticker,
        sector_id,
        user_email,
        agent_id,
        agent_name,
        agent_identity,
        max_fetch_retries,
        max_validation_retries,
        model_override,
        loop,
        synthesis,
        llm_api_key,
        llm_base_url,
        llm_model,
    )

    def _on_done(fut: "asyncio.Future[None]") -> None:
        # _execute_pipeline handles its own failures, but if it raised before
        # its internal try block (or the executor itself failed) the run would
        # be stuck "running" with an unclosed SSE queue. Guard against that.
        exc = fut.exception()
        if exc is None:
            return
        logger.exception("Pipeline executor for run %s crashed", run_id, exc_info=exc)
        asyncio.run_coroutine_threadsafe(
            _db_update(
                run_id,
                status="failed",
                error=str(exc)[:2000],
                finished_at=datetime.now(timezone.utc),
            ),
            loop,
        )
        q = _queues.get(run_id)
        if q is not None:
            _offer_threadsafe(run_id, None, loop)

    future.add_done_callback(_on_done)



# ══════════════════════════════════════════════════════════════════
# Dry-run simulation (no LangGraph — for local E2E testing)
# ══════════════════════════════════════════════════════════════════

# 5 simulated nodes, 2 s apart → ~10 s total stream
_DRY_RUN_NODES: list[tuple[str, str]] = [
    ("fetch",     "📡 Fetching market data (dry run)…"),
    ("summarize", "📝 Summarising articles (dry run)…"),
    ("analyze",   "🧠 Running deep analysis (dry run)…"),
    ("validate",  "✅ Validating claims (dry run)…"),
    ("save",      "💾 Saving signal card (dry run)…"),
]


async def _simulate_dry_run(run_id: str, ticker: str) -> None:
    """
    Background coroutine that fakes a 5-node pipeline over ~10 seconds.
    Pushes the same SSEEvent types the real pipeline produces, then closes
    the stream with a pipeline_completed sentinel.
    """
    await _db_update(run_id, status="running", started_at=datetime.now(timezone.utc))

    total = len(_DRY_RUN_NODES)
    for i, (node, label) in enumerate(_DRY_RUN_NODES):
        progress_start = round(i / total * 100, 1)
        progress_end   = round((i + 1) / total * 100, 1)

        await _db_update(run_id, status="running", current_node=node)

        q = _queues.get(run_id)
        if q is not None:
            await q.put(SSEEvent(
                event="node_started",
                run_id=run_id,
                data={"node": node, "label": label, "progress_pct": progress_start},
            ))

        await asyncio.sleep(2.0)

        q = _queues.get(run_id)
        if q is not None:
            await q.put(SSEEvent(
                event="node_completed",
                run_id=run_id,
                data={"node": node, "progress_pct": progress_end},
            ))

    # ── Terminal events ────────────────────────────────────────────
    q = _queues.get(run_id)
    if q is not None:
        await q.put(SSEEvent(
            event="pipeline_completed",
            run_id=run_id,
            data={"report_id": None, "confidence": 0.85, "signal_card_id": None},
        ))
        await q.put(None)  # close-stream sentinel

    await _db_update(
        run_id,
        status="completed",
        finished_at=datetime.now(timezone.utc),
        node_executions=[{"node_name": n, "status": "completed"} for n, _ in _DRY_RUN_NODES],
    )

    logger.info("Dry-run %s for %s completed.", run_id, ticker)


async def launch_dry_run(run_id: str, ticker: str) -> None:
    """
    Register the SSE queue for run_id and schedule the simulated pipeline as
    a background asyncio task.  Returns immediately like launch_run().

    This is the non-blocking entry point called by the pipeline route when
    RunRequest.dry_run is True.
    """
    _register_queue(run_id)
    asyncio.create_task(_simulate_dry_run(run_id, ticker))
