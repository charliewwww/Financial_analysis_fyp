"""
Pipeline router — trigger analysis runs and stream live progress via SSE.

Endpoints (all under /api/v1/pipeline):

    POST  /runs                   Start a pipeline run → {run_id, status}
    GET   /runs                   List runs (paginated, optional ?ticker filter)
    GET   /runs/{run_id}          Poll run status (fallback for non-SSE clients)
    GET   /runs/{run_id}/stream   Server-Sent Events live progress stream

SSE event types
───────────────
    node_started        data: {node, label, progress_pct}
    node_completed      data: {node, progress_pct}
    pipeline_completed  data: {report_id, confidence, signal_card_id}
    pipeline_failed     data: {message}
    heartbeat           data: {run_id}   (sent every ~15 s to keep connection alive)

The stream closes automatically after pipeline_completed or pipeline_failed.
"""

from __future__ import annotations

import asyncio
import json
from typing import AsyncGenerator
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sse_starlette.sse import EventSourceResponse
from sqlalchemy.ext.asyncio import AsyncConnection
from typing import Annotated

from app.core.auth import CurrentUser
from app.db.engine import get_db
from app.db.repositories import signals as signal_repo
from app.pipeline import runner
from app.schemas.common import PaginatedResponse
from app.schemas.pipeline import PipelineRunSchema, RunRequest, RunSummary

router = APIRouter(prefix="/pipeline", tags=["pipeline"])

DB = Annotated[AsyncConnection, Depends(get_db)]


# ── Trigger ────────────────────────────────────────────────────────

@router.post(
    "/runs",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger a pipeline run",
    description=(
        "Starts a new pipeline run for the given ticker + sector. "
        "Returns immediately with the `run_id`. "
        "Use `GET /runs/{run_id}/stream` to follow live progress, "
        "or `GET /runs/{run_id}` to poll."
    ),
)
async def trigger_run(body: RunRequest, db: DB, user: CurrentUser) -> dict:
    run_id = str(uuid4())
    await signal_repo.create_run(
        db, run_id, body.ticker.upper(), body.sector_id, user_email=user
    )
    if body.dry_run:
        await runner.launch_dry_run(run_id=run_id, ticker=body.ticker.upper())
    else:
        await runner.launch_run(
            run_id=run_id,
            ticker=body.ticker.upper(),
            sector_id=body.sector_id,
            user_email=user,
            max_fetch_retries=body.max_fetch_retries,
            max_validation_retries=body.max_validation_retries,
        )
    return {"run_id": run_id, "status": "pending", "dry_run": body.dry_run}


# ── List ───────────────────────────────────────────────────────────

@router.get(
    "/runs",
    response_model=PaginatedResponse[RunSummary],
    summary="List pipeline runs",
    description=(
        "Paginated list of runs, newest first. "
        "Pass `?ticker=NVDA` to filter to one ticker."
    ),
)
async def list_runs(
    db: DB,
    user: CurrentUser,
    ticker: str | None = Query(default=None, description="Filter to a single ticker."),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> PaginatedResponse[RunSummary]:
    items, total = await signal_repo.list_runs(
        db, ticker=ticker, user_email=user, page=page, page_size=page_size
    )
    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        has_next=(page * page_size) < total,
    )


# ── Run detail (polling) ───────────────────────────────────────────

@router.get(
    "/runs/{run_id}",
    response_model=PipelineRunSchema,
    summary="Get run status",
    description=(
        "Returns the current state of a pipeline run. "
        "While `status == 'running'`, `current_node` updates after each node. "
        "Prefer the SSE stream for real-time UI updates."
    ),
)
async def get_run(run_id: str, db: DB) -> PipelineRunSchema:
    run = await signal_repo.get_run(db, run_id)
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run {run_id!r} not found.",
        )
    return run


# ── SSE stream ─────────────────────────────────────────────────────

@router.get(
    "/runs/{run_id}/stream",
    summary="Stream run progress (SSE)",
    description=(
        "Server-Sent Events stream for a pipeline run.  "
        "The stream closes after `pipeline_completed` or `pipeline_failed`.  "
        "A `heartbeat` event is sent every ~15 s to keep the HTTP connection alive."
    ),
)
async def stream_run(run_id: str, db: DB) -> EventSourceResponse:
    # Validate the run exists before streaming
    run = await signal_repo.get_run(db, run_id)
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run {run_id!r} not found.",
        )

    # Run already finished — emit a single terminal event and close
    if run.status in ("completed", "failed"):
        terminal_event = "pipeline_completed" if run.status == "completed" else "pipeline_failed"

        async def _finished_stream() -> AsyncGenerator:
            yield {
                "event": terminal_event,
                "data": json.dumps({"run_id": run_id, "status": run.status}),
            }

        return EventSourceResponse(_finished_stream())

    # Run is still live — consume from the in-memory queue
    q = runner.get_queue(run_id)
    if q is None:
        # Race condition: run finished between DB check and queue lookup
        async def _empty_stream() -> AsyncGenerator:
            yield {
                "event": "heartbeat",
                "data": json.dumps({"run_id": run_id}),
            }

        return EventSourceResponse(_empty_stream())

    async def _live_stream() -> AsyncGenerator:
        try:
            while True:
                # 15-second timeout → emit heartbeat, then resume waiting
                try:
                    event = await asyncio.wait_for(q.get(), timeout=15.0)
                except asyncio.TimeoutError:
                    yield {
                        "event": "heartbeat",
                        "data": json.dumps({"run_id": run_id}),
                    }
                    continue

                # None sentinel means the pipeline thread is done
                if event is None:
                    break

                yield {"event": event.event, "data": event.model_dump_json()}
        finally:
            runner.drop_queue(run_id)

    return EventSourceResponse(_live_stream())
