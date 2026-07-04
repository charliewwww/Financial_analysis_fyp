"""Tests for pipeline runner signal-card persistence decisions."""

from __future__ import annotations

import asyncio
import time
from types import SimpleNamespace
from typing import Any

import pytest

from app.pipeline import runner


_VALID_ANALYSIS = (
    "## Signal\nBULLISH on NVDA.\n"
    "## Thesis\nThe data centre cycle is intact.\n"
    "## Key Catalyst\nQ1 print Feb 26.\n"
    "## Key Risk\nChina export curbs.\n"
    "Conviction: 4/5\n"
)


def test_pipeline_worker_pool_supports_full_sector_board() -> None:
    assert runner.pipeline_worker_count() >= 40


def _state(validation_status: str) -> SimpleNamespace:
    return SimpleNamespace(
        analysis_text=_VALID_ANALYSIS,
        confidence_score=8,
        validation_status=validation_status,
        validation_issues=[],
        articles=[],
        sector_id="ai_semiconductors",
        sector_name="AI & Semiconductors",
    )


async def _wait_for_status(updates: list[dict[str, Any]], status: str) -> None:
    for _ in range(100):
        if any(update.get("status") == status for update in updates):
            return
        await asyncio.sleep(0.01)
    raise AssertionError(f"Timed out waiting for {status!r} update: {updates!r}")


async def _drain_events(queue: asyncio.Queue) -> list[Any]:
    events: list[Any] = []
    while True:
        item = await asyncio.wait_for(queue.get(), timeout=1)
        if item is None:
            return events
        events.append(item)


async def _run_pipeline_with_validation(
    monkeypatch: pytest.MonkeyPatch,
    validation_status: str,
    persist_result: int = 42,
) -> tuple[list[Any], list[dict[str, Any]], list[Any]]:
    import workflows.weekly_analysis as weekly_analysis

    run_id = f"test-{validation_status.lower().replace(' ', '-')}"
    queue = runner._register_queue(run_id)
    updates: list[dict[str, Any]] = []
    persisted: list[Any] = []

    def fake_run_sector_analysis(**_: Any) -> dict[str, Any]:
        return {
            "pipeline_state": _state(validation_status),
            "report_id": 7,
            "confidence": 8,
        }

    async def fake_db_update(_: str, **kwargs: Any) -> None:
        updates.append(kwargs)

    async def fake_persist_card(draft: Any, state: Any | None = None) -> int:
        persisted.append(draft)
        return persist_result

    monkeypatch.setattr(weekly_analysis, "run_sector_analysis", fake_run_sector_analysis)
    monkeypatch.setattr(runner, "_db_update", fake_db_update)
    monkeypatch.setattr(runner, "_persist_card", fake_persist_card)

    loop = asyncio.get_running_loop()
    await asyncio.to_thread(
        runner._execute_pipeline,
        run_id,
        "NVDA",
        "ai_semiconductors",
        "dev@local",
        1,
        "Supply Chain Analyst",
        "system prompt",
        1,
        1,
        "",
        loop,
    )

    events = await _drain_events(queue)
    runner.drop_queue(run_id)
    return events, updates, persisted


@pytest.mark.asyncio
async def test_failed_validation_publishes_needs_review_card(monkeypatch: pytest.MonkeyPatch) -> None:
    events, updates, persisted = await _run_pipeline_with_validation(
        monkeypatch,
        "FAILED",
    )

    await _wait_for_status(updates, "completed")

    assert len(persisted) == 1
    assert persisted[0].validation_score == "FAILED"
    assert persisted[0].status == "needs_review"
    completed_event = next(event for event in events if event.event == "pipeline_completed")
    assert completed_event.data["signal_card_id"] == 42
    assert any(
        update.get("status") == "completed" and update.get("signal_card_id") == 42
        for update in updates
    )


@pytest.mark.asyncio
async def test_passed_validation_publishes_signal_card(monkeypatch: pytest.MonkeyPatch) -> None:
    events, updates, persisted = await _run_pipeline_with_validation(
        monkeypatch,
        "PASSED WITH WARNINGS",
        persist_result=99,
    )

    await _wait_for_status(updates, "completed")

    assert len(persisted) == 1
    assert persisted[0].validation_score == "PASSED WITH WARNINGS"
    completed_event = next(event for event in events if event.event == "pipeline_completed")
    assert completed_event.data["signal_card_id"] == 99
    assert any(
        update.get("status") == "completed" and update.get("signal_card_id") == 99
        for update in updates
    )


# ══════════════════════════════════════════════════════════════════
# SSE queue reliability — bounded buffer + orphan reaping
# ══════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_register_queue_is_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(runner.settings, "sse_queue_maxsize", 32, raising=False)
    run_id = "test-bounded"
    q = runner._register_queue(run_id)
    try:
        assert q.maxsize == 32
    finally:
        runner.drop_queue(run_id)


@pytest.mark.asyncio
async def test_offer_drops_oldest_when_full(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(runner.settings, "sse_queue_maxsize", 16, raising=False)
    run_id = "test-overflow"
    q = runner._register_queue(run_id)
    try:
        # Fill beyond capacity; the buffer must stay bounded and keep newest.
        for i in range(50):
            await runner._offer(q, i)
        assert q.qsize() == 16
        drained = [q.get_nowait() for _ in range(q.qsize())]
        # Oldest items were dropped — the tail (most recent) survives.
        assert drained == list(range(34, 50))
    finally:
        runner.drop_queue(run_id)


@pytest.mark.asyncio
async def test_offer_close_sentinel_always_enqueued(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(runner.settings, "sse_queue_maxsize", 16, raising=False)
    run_id = "test-sentinel"
    q = runner._register_queue(run_id)
    try:
        for i in range(16):
            await runner._offer(q, i)
        # Queue is full; the None close sentinel must still get in.
        await runner._offer(q, None)
        items = [q.get_nowait() for _ in range(q.qsize())]
        assert items[-1] is None
    finally:
        runner.drop_queue(run_id)


@pytest.mark.asyncio
async def test_reap_orphan_queues_drops_stale(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(runner.settings, "sse_queue_orphan_ttl_seconds", 900, raising=False)
    fresh_id = "test-fresh"
    stale_id = "test-stale"
    runner._register_queue(fresh_id)
    runner._register_queue(stale_id)
    try:
        # Backdate the stale queue's creation time beyond the TTL.
        runner._queue_created_at[stale_id] = time.monotonic() - 1_000
        runner._reap_orphan_queues()
        assert runner.get_queue(stale_id) is None
        assert stale_id not in runner._queue_created_at
        assert runner.get_queue(fresh_id) is not None
    finally:
        runner.drop_queue(fresh_id)
        runner.drop_queue(stale_id)


@pytest.mark.asyncio
async def test_register_queue_reaps_orphans_on_launch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(runner.settings, "sse_queue_orphan_ttl_seconds", 900, raising=False)
    orphan_id = "test-orphan"
    runner._register_queue(orphan_id)
    runner._queue_created_at[orphan_id] = time.monotonic() - 1_000
    new_id = "test-new"
    try:
        # Registering a new queue should sweep the stale orphan away.
        runner._register_queue(new_id)
        assert runner.get_queue(orphan_id) is None
    finally:
        runner.drop_queue(orphan_id)
        runner.drop_queue(new_id)
