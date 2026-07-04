"""
Background scheduler — the Track Record / backtester heartbeat.

Once a day (configurable) it matures outstanding calls into verified outcomes:
  * per-ticker analyst predictions  → ``prediction_resolver.resolve_predictions``
  * Chief Strategist house verdicts  → ``accuracy_resolver.run_resolution``

The job opens its own short-lived transactional connection from the engine,
runs both resolvers, and logs a summary. Any failure is swallowed and logged so
a transient data-source outage never takes the API process down.

Wired into the FastAPI lifespan (see app.main). Disabled in tests via
``settings.scheduler_enabled = False``.
"""

from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from fastapi import FastAPI

from app.core.config import settings
from app.db.engine import get_engine
from app.db.repositories import signals as signal_repo
from app.services import accuracy_resolver, prediction_resolver

logger = logging.getLogger(__name__)

_JOB_ID = "resolve_outcomes"
_REAPER_JOB_ID = "reap_stale_runs"


async def run_resolution_cycle() -> dict[str, int | bool]:
    """Resolve predictions and house verdicts in one transactional pass."""
    engine = get_engine()
    async with engine.begin() as db:
        predictions_resolved = await prediction_resolver.resolve_predictions(db)
        verdicts = await accuracy_resolver.run_resolution(db)
    summary: dict[str, int | bool] = {
        "predictions_resolved": predictions_resolved,
        "verdicts_resolved": int(verdicts.get("resolved", 0)),
        "lessons_updated": bool(verdicts.get("lessons_updated", False)),
    }
    logger.info("Outcome resolution complete: %s", summary)
    return summary


async def _safe_cycle() -> None:
    try:
        await run_resolution_cycle()
    except Exception:  # pragma: no cover - defensive: never kill the scheduler
        logger.exception("Scheduled outcome resolution failed")


async def _safe_reap() -> None:
    """Fail runs that have been in-flight too long (hung-worker safety net)."""
    try:
        engine = get_engine()
        async with engine.begin() as db:
            reaped = await signal_repo.fail_stale_runs(
                db, older_than_minutes=settings.stale_run_timeout_minutes
            )
        if reaped:
            logger.info("Reaped %d stale pipeline run(s) as failed.", reaped)
    except Exception:  # pragma: no cover - defensive: never kill the scheduler
        logger.exception("Stale-run reaper failed")


def start_scheduler(app: FastAPI) -> None:
    """Create and start the AsyncIOScheduler, storing it on app.state."""
    if not settings.scheduler_enabled:
        logger.info("Scheduler disabled (settings.scheduler_enabled=False).")
        return

    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(
        _safe_cycle,
        trigger=IntervalTrigger(hours=settings.resolution_interval_hours),
        id=_JOB_ID,
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )
    scheduler.add_job(
        _safe_reap,
        trigger=IntervalTrigger(minutes=settings.stale_run_sweep_minutes),
        id=_REAPER_JOB_ID,
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )
    scheduler.start()
    app.state.scheduler = scheduler
    logger.info(
        "Outcome-resolution scheduler started (every %sh).",
        settings.resolution_interval_hours,
    )


def stop_scheduler(app: FastAPI) -> None:
    """Shut the scheduler down if it is running."""
    scheduler = getattr(app.state, "scheduler", None)
    if scheduler is not None:
        scheduler.shutdown(wait=False)
        app.state.scheduler = None
        logger.info("Outcome-resolution scheduler stopped.")
