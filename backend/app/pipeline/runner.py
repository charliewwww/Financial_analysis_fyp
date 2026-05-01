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
from app.pipeline.signal_extractor import (  # noqa: E402
    SignalCardDraft,
    from_pipeline_state,
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
_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="pipeline")

# ── Per-run event queues ───────────────────────────────────────────
_queues: dict[str, asyncio.Queue] = {}


# ══════════════════════════════════════════════════════════════════
# Queue management
# ══════════════════════════════════════════════════════════════════

def _register_queue(run_id: str) -> asyncio.Queue:
    q: asyncio.Queue[SSEEvent | None] = asyncio.Queue()
    _queues[run_id] = q
    return q


def get_queue(run_id: str) -> asyncio.Queue | None:
    """Return the live event queue for a run, or None if the run is finished."""
    return _queues.get(run_id)


def drop_queue(run_id: str) -> None:
    """Remove and discard the queue for a completed/failed run."""
    _queues.pop(run_id, None)


# ══════════════════════════════════════════════════════════════════
# DB helper — async update callable from the background thread
# ══════════════════════════════════════════════════════════════════

async def _db_update(run_id: str, **kwargs: Any) -> None:
    """Open a fresh async connection and update the pipeline_runs row."""
    from app.db.engine import get_engine
    from app.db.repositories import signals as repo

    async with get_engine().begin() as conn:
        await repo.update_run_status(conn, run_id, **kwargs)


async def _persist_card(draft: SignalCardDraft) -> int:
    """Insert a signal card row built from the finished PipelineState.

    Returns the new card's integer PK so the caller can wire it into the
    pipeline_runs row and the pipeline_completed SSE event.
    """
    from app.db.engine import get_engine
    from app.db.repositories.signals import create_signal_card

    payload = draft.model_dump(exclude={"created_at", "status"})
    async with get_engine().begin() as conn:
        return await create_signal_card(conn, **payload)


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
            asyncio.run_coroutine_threadsafe(q.put(event), self.loop)

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
    max_fetch_retries: int,
    max_validation_retries: int,
    loop: asyncio.AbstractEventLoop,
) -> None:
    """
    Blocking function — always called from the ThreadPoolExecutor, never
    from the event loop thread.

    1. Imports legacy modules lazily (path patch is applied at module import time).
    2. Runs run_sector_analysis() with the progress bridge.
    3. Persists terminal status to the DB.
    4. Sends None sentinel to close the SSE stream.
    """
    bridge = _ProgressBridge(run_id, loop)

    def _db(**kwargs: Any) -> None:
        asyncio.run_coroutine_threadsafe(_db_update(run_id, **kwargs), loop)

    _db(status="running", started_at=datetime.now(timezone.utc))

    try:
        # Lazy imports — executed after _REPO_ROOT is on sys.path
        from config.sectors import SECTORS  # type: ignore[import]
        from workflows.weekly_analysis import run_sector_analysis  # type: ignore[import]

        sector_cfg = SECTORS.get(sector_id)
        if sector_cfg is None:
            raise ValueError(f"Unknown sector_id: {sector_id!r}")

        # Narrow to just the requested ticker so the LLM focuses on it.
        # Fall back to the full sector list if the ticker isn't pre-defined.
        ticker_list = [t for t in sector_cfg["tickers"] if t == ticker.upper()]
        narrowed_cfg = {**sector_cfg, "tickers": ticker_list or sector_cfg["tickers"]}

        result = run_sector_analysis(
            sector_id=sector_id,
            sector=narrowed_cfg,
            progress_fn=bridge,
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
                )
                future = asyncio.run_coroutine_threadsafe(
                    _persist_card(draft), loop
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
            asyncio.run_coroutine_threadsafe(q.put(None), loop)


# ══════════════════════════════════════════════════════════════════
# Public async API
# ══════════════════════════════════════════════════════════════════

async def launch_run(
    run_id: str,
    ticker: str,
    sector_id: str,
    user_email: str | None = None,
    max_fetch_retries: int = 1,
    max_validation_retries: int = 1,
) -> None:
    """
    Register the SSE event queue for run_id and submit the blocking pipeline
    to the thread pool.  Returns immediately.

    The caller should return run_id to the HTTP client.  Progress is
    available via get_queue(run_id) and the SSE /stream endpoint.
    """
    loop = asyncio.get_running_loop()
    _register_queue(run_id)
    loop.run_in_executor(
        _executor,
        _execute_pipeline,
        run_id,
        ticker,
        sector_id,
        user_email,
        max_fetch_retries,
        max_validation_retries,
        loop,
    )


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
