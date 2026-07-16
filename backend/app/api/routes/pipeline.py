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
from datetime import datetime, timezone
from typing import AsyncGenerator
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sse_starlette.sse import EventSourceResponse
from sqlalchemy.ext.asyncio import AsyncConnection
from typing import Annotated

from app.core.auth import CurrentUser, is_admin
from app.core.config import settings
from app.core.models_catalog import is_allowed_model
from app.db.engine import get_db
from app.db.repositories import agents as agent_repo
from app.db.repositories import signals as signal_repo
from app.pipeline import runner
from app.schemas.common import PaginatedResponse
from app.schemas.agents import AgentRuntimeSchema
from app.schemas.pipeline import (
    PipelineRunSchema,
    RunFanoutItem,
    RunFanoutRequest,
    RunFanoutResponse,
    RunRequest,
    RunSectorFanoutRequest,
    RunSectorSynthesisRequest,
    RunSummary,
    RunSynthesisResponse,
)

from config.sectors import SECTORS
from config.markets import get_sector as get_market_sector

router = APIRouter(prefix="/pipeline", tags=["pipeline"])

DB = Annotated[AsyncConnection, Depends(get_db)]


def _normalize_ticker(ticker: str) -> str:
    return ticker.strip().upper().replace(" ", "")


def _sector_constituents(sector_id: str) -> list[str] | None:
    """Configured tickers for a sector id, checked across both the legacy
    supply-chain catalog (config/sectors.py) and the market catalog
    (config/markets.py — e.g. ``hk_tech``, ``us_technology``).

    Returns ``None`` if the id is unknown to both.
    """
    legacy = SECTORS.get(sector_id)
    if legacy is not None:
        return [_normalize_ticker(str(t)) for t in legacy.get("tickers", [])]
    market_sector = get_market_sector(sector_id)
    if market_sector is not None:
        return [_normalize_ticker(str(t)) for t in market_sector.get("constituents", [])]
    return None


def _infer_sector_id(ticker: str) -> str | None:
    for sector_id, sector in SECTORS.items():
        tickers = {str(item).upper() for item in sector.get("tickers", [])}
        if ticker in tickers:
            return sector_id
    return None


def _sector_label(sector_id: str) -> str:
    """Human-readable display name for a sector id, used as the synthesis
    signal-card "ticker" label. Falls back to the id when unknown."""
    legacy = SECTORS.get(sector_id)
    if legacy is not None:
        return str(legacy.get("name", sector_id))
    market_sector = get_market_sector(sector_id)
    if market_sector is not None:
        return str(market_sector.get("name", sector_id))
    return sector_id


def _friendly_llm_health_error(exc: Exception) -> str:
    message = str(exc)
    lower = message.lower()
    if "key limit exceeded" in lower or "quota" in lower or "limit exceeded" in lower:
        return (
            "LLM provider quota exceeded. OpenRouter rejected the run before the "
            "analyst board could finish. Switch to an OpenRouter :free model, "
            "add credits, rotate the API key, or use local Ollama before rerunning."
        )
    if "api key" in lower or "403" in lower or "unauthorized" in lower:
        return (
            "LLM provider authentication failed. Check the OpenRouter API key or "
            "switch to local Ollama before rerunning."
        )
    return "LLM provider is not reachable right now. Check provider health, then rerun the analyst board."


async def _ensure_llm_ready() -> None:
    try:
        from agents.llm_client import check_llm_health

        await asyncio.to_thread(check_llm_health, timeout=10)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_friendly_llm_health_error(exc),
        ) from exc


async def _resolve_fanout_agents(
    db: AsyncConnection,
    agent_ids: list[int] | None,
    user_email: str,
) -> list[AgentRuntimeSchema]:
    if agent_ids is None:
        summaries = await agent_repo.list_agents(db, user_email=user_email)
        agent_ids = [agent.id for agent in summaries]

    seen: set[int] = set()
    agents: list[AgentRuntimeSchema] = []
    for agent_id in agent_ids:
        if agent_id in seen:
            continue
        seen.add(agent_id)
        agent = await agent_repo.get_agent(db, agent_id, user_email=user_email)
        if agent is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Agent {agent_id!r} not found.",
            )
        agents.append(agent)

    if not agents:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No agents available for fanout.",
        )
    return agents


def _resolve_model_override(model: str | None, *, allow_custom: bool = False) -> str:
    """Validate an optional per-run model against the curated allow-list.

    Returns "" when no override was requested. Rejects any model that is not
    in the allow-list so the browser cannot inject an arbitrary model string —
    unless ``allow_custom`` is set, which happens when the user supplies their
    own API key (it is their own provider, so any model name is permitted).
    """
    if not model or not model.strip():
        return ""
    candidate = model.strip()
    if not allow_custom and not is_allowed_model(candidate):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Model {candidate!r} is not in the allowed model list.",
        )
    return candidate


def _sector_tickers(sector_id: str, requested: list[str] | None = None) -> list[str]:
    configured = _sector_constituents(sector_id)
    if configured is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sector {sector_id!r} not found.",
        )

    if requested is None:
        return configured

    configured_set = set(configured)
    tickers: list[str] = []
    for raw_ticker in requested:
        ticker = _normalize_ticker(raw_ticker)
        if not ticker or ticker in tickers:
            continue
        if ticker not in configured_set:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Ticker {ticker!r} is not configured for sector {sector_id!r}.",
            )
        tickers.append(ticker)

    if not tickers:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No valid tickers supplied for sector fanout.",
        )
    return tickers


async def _enforce_run_quota(db: AsyncConnection, user: str, additional: int) -> None:
    """
    Reject a trigger request that would exceed the user's limits, BEFORE any
    run rows are created. Two limits apply:

    1. Daily free-analysis quota (``DAILY_RUN_QUOTA``) — the app provides the AI,
       so each user gets a fixed number of analyses per UTC day. Operators are
       exempt; 0 disables the cap.
    2. Per-user concurrency cap (``PIPELINE_MAX_ACTIVE_RUNS_PER_USER``) — stops a
       single client flooding the shared thread pool.

    ``additional`` is the number of runs the incoming request would create
    (1 for a single run, N analysts for a board fanout, etc.).
    """
    # 1. Daily free-analysis quota (operators exempt).
    daily_cap = settings.daily_run_quota
    if daily_cap > 0 and not await is_admin(db, user):
        start_of_day = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        used_today = await signal_repo.count_runs_since(
            db, user_email=user, since=start_of_day
        )
        if used_today + additional > daily_cap:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=(
                    f"Daily free-analysis limit reached ({used_today}/{daily_cap} "
                    "used today). It resets at 00:00 UTC."
                ),
            )

    # 2. Per-user concurrency cap.
    cap = settings.pipeline_max_active_runs_per_user
    active = await signal_repo.count_active_runs(db, user_email=user)
    if active + additional > cap:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                f"Too many concurrent runs: {active} active, this request adds "
                f"{additional}, limit is {cap}. Wait for runs to finish and retry."
            ),
        )


async def _launch_agent_fanout(
    *,
    db: AsyncConnection,
    user: str,
    ticker: str,
    sector_id: str,
    agents: list[AgentRuntimeSchema],
    dry_run: bool,
    max_fetch_retries: int,
    max_validation_retries: int,
    model_override: str = "",
    llm_api_key: str = "",
    llm_base_url: str = "",
    llm_model: str = "",
) -> RunFanoutResponse:
    runs: list[RunFanoutItem] = []

    for agent in agents:
        run_id = str(uuid4())
        await signal_repo.create_run(
            db,
            run_id,
            ticker,
            sector_id,
            agent_id=agent.id,
            agent_name=agent.name,
            user_email=user,
        )
        if dry_run:
            await runner.launch_dry_run(run_id=run_id, ticker=ticker)
        else:
            await runner.launch_run(
                run_id=run_id,
                ticker=ticker,
                sector_id=sector_id,
                user_email=user,
                agent_id=agent.id,
                agent_name=agent.name,
                agent_identity=agent.identity_layer,
                max_fetch_retries=max_fetch_retries,
                max_validation_retries=max_validation_retries,
                model_override=model_override,
                llm_api_key=llm_api_key,
                llm_base_url=llm_base_url,
                llm_model=llm_model,
            )
        runs.append(
            RunFanoutItem(
                run_id=run_id,
                agent_id=agent.id,
                agent_name=agent.name,
            )
        )

    return RunFanoutResponse(
        ticker=ticker,
        sector_id=sector_id,
        dry_run=dry_run,
        runs=runs,
    )


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
    agent = await agent_repo.get_agent_for_run(db, body.agent_id, user_email=user)
    if agent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent {body.agent_id!r} not found.",
        )

    await _enforce_run_quota(db, user, additional=1)

    if not body.dry_run:
        await _ensure_llm_ready()

    model_override = _resolve_model_override(body.model, allow_custom=bool(body.api_key))
    run_id = str(uuid4())
    await signal_repo.create_run(
        db,
        run_id,
        body.ticker.upper(),
        body.sector_id,
        agent_id=agent.id,
        agent_name=agent.name,
        user_email=user,
    )
    if body.dry_run:
        await runner.launch_dry_run(run_id=run_id, ticker=body.ticker.upper())
    else:
        await runner.launch_run(
            run_id=run_id,
            ticker=body.ticker.upper(),
            sector_id=body.sector_id,
            user_email=user,
            agent_id=agent.id,
            agent_name=agent.name,
            agent_identity=agent.identity_layer,
            max_fetch_retries=body.max_fetch_retries,
            max_validation_retries=body.max_validation_retries,
            model_override=model_override,
            llm_api_key=body.api_key or "",
            llm_base_url=body.base_url or "",
            llm_model=model_override,
        )
    return {
        "run_id": run_id,
        "status": "pending",
        "dry_run": body.dry_run,
        "agent_id": agent.id,
    }


@router.post(
    "/runs/fanout",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=RunFanoutResponse,
    summary="Trigger Board of Analysts fanout",
    description=(
        "Starts one pipeline run per selected analyst agent for the same ticker. "
        "When `sector_id` is omitted, known tickers are mapped from the sector catalog."
    ),
)
async def trigger_run_fanout(
    body: RunFanoutRequest,
    db: DB,
    user: CurrentUser,
) -> RunFanoutResponse:
    ticker = _normalize_ticker(body.ticker)
    # Any ticker is analysable. When it isn't part of a curated sector we fall
    # back to the synthetic "general" sector so the board still runs; the
    # runner builds a lightweight on-the-fly config for it.
    sector_id = body.sector_id or _infer_sector_id(ticker) or "general"

    agents = await _resolve_fanout_agents(db, body.agent_ids, user)
    await _enforce_run_quota(db, user, additional=len(agents))
    model_override = _resolve_model_override(body.model, allow_custom=bool(body.api_key))
    if not body.dry_run:
        await _ensure_llm_ready()

    return await _launch_agent_fanout(
        db=db,
        user=user,
        ticker=ticker,
        sector_id=sector_id,
        agents=agents,
        dry_run=body.dry_run,
        max_fetch_retries=body.max_fetch_retries,
        max_validation_retries=body.max_validation_retries,
        model_override=model_override,
        llm_api_key=body.api_key or "",
        llm_base_url=body.base_url or "",
        llm_model=model_override,
    )


@router.post(
    "/runs/sector-fanout",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=list[RunFanoutResponse],
    summary="Trigger sector-wide Board of Analysts fanout",
    description=(
        "Starts one board fanout per ticker in a sector using a single API request. "
        "This avoids browser-side request bursts and performs LLM readiness checks once."
    ),
)
async def trigger_sector_fanout(
    body: RunSectorFanoutRequest,
    db: DB,
    user: CurrentUser,
) -> list[RunFanoutResponse]:
    tickers = _sector_tickers(body.sector_id, body.tickers)
    agents = await _resolve_fanout_agents(db, body.agent_ids, user)
    await _enforce_run_quota(db, user, additional=len(tickers) * len(agents))
    model_override = _resolve_model_override(body.model, allow_custom=bool(body.api_key))
    if not body.dry_run:
        await _ensure_llm_ready()

    responses: list[RunFanoutResponse] = []
    for ticker in tickers:
        responses.append(
            await _launch_agent_fanout(
                db=db,
                user=user,
                ticker=ticker,
                sector_id=body.sector_id,
                agents=agents,
                dry_run=body.dry_run,
                max_fetch_retries=body.max_fetch_retries,
                max_validation_retries=body.max_validation_retries,
                model_override=model_override,
                llm_api_key=body.api_key or "",
                llm_base_url=body.base_url or "",
                llm_model=model_override,
            )
        )
    return responses


@router.post(
    "/runs/sector-synthesis",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=RunSynthesisResponse,
    summary="Trigger a board-level sector synthesis",
    description=(
        "Runs ONE sector-wide synthesis (macro → trend → second-order effects "
        "across constituents) instead of fanning out per ticker. Produces a "
        "single signal card labelled with the sector name."
    ),
)
async def trigger_sector_synthesis(
    body: RunSectorSynthesisRequest,
    db: DB,
    user: CurrentUser,
) -> RunSynthesisResponse:
    # Validate the sector exists (also rejects unknown ids early).
    _sector_tickers(body.sector_id)
    await _enforce_run_quota(db, user, additional=1)
    label = _sector_label(body.sector_id)
    ticker_label = label.upper()
    model_override = _resolve_model_override(body.model, allow_custom=bool(body.api_key))
    await _ensure_llm_ready()

    run_id = str(uuid4())
    await signal_repo.create_run(
        db,
        run_id,
        ticker_label,
        body.sector_id,
        agent_id=None,
        agent_name="Sector Strategist",
        user_email=user,
    )
    await runner.launch_run(
        run_id=run_id,
        ticker=ticker_label,
        sector_id=body.sector_id,
        user_email=user,
        agent_id=None,
        agent_name="Sector Strategist",
        agent_identity="",
        max_fetch_retries=body.max_fetch_retries,
        max_validation_retries=body.max_validation_retries,
        model_override=model_override,
        synthesis=True,
        llm_api_key=body.api_key or "",
        llm_base_url=body.base_url or "",
        llm_model=model_override,
    )
    return RunSynthesisResponse(
        run_id=run_id,
        sector_id=body.sector_id,
        sector_label=label,
    )


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
async def get_run(run_id: str, db: DB, user: CurrentUser) -> PipelineRunSchema:
    run = await signal_repo.get_run_for_user(db, run_id, user_email=user)
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
async def stream_run(run_id: str, db: DB, user: CurrentUser) -> EventSourceResponse:
    # Validate the run exists before streaming
    run = await signal_repo.get_run_for_user(db, run_id, user_email=user)
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
