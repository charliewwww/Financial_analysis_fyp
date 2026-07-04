"""
Tests for app.services.prediction_resolver — the Track Record engine.

Uses an in-memory SQLite database (the shared `db` fixture) and an injected
price fetcher so no network access is required.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import insert

from app.db.repositories import predictions as pred_repo
from app.db.tables import predictions, signal_cards
from app.services import prediction_resolver


async def _insert_signal_card(db, *, created_at, ticker="NVDA") -> int:
    result = await db.execute(
        insert(signal_cards)
        .values(
            ticker=ticker,
            signal="BULLISH",
            conviction=4,
            one_line="Strong buy",
            confidence=0.8,
            created_at=created_at,
            status="active",
            numerical_claims=json.dumps([]),
            sources=json.dumps([]),
            supply_chain_impact=json.dumps([]),
        )
        .returning(signal_cards.c.id)
    )
    return result.scalar_one()


async def _insert_prediction(db, **overrides) -> int:
    vals = dict(ticker="NVDA", price_at_report=500.0, ai_direction="BULLISH")
    vals.update(overrides)
    result = await db.execute(
        insert(predictions).values(**vals).returning(predictions.c.id)
    )
    return result.scalar_one()


class TestResolvePredictions:
    @pytest.mark.asyncio
    async def test_matured_bullish_prediction_is_scored_correct(self, db):
        old = datetime.now(timezone.utc) - timedelta(days=8)
        cid = await _insert_signal_card(db, created_at=old)
        pid = await _insert_prediction(
            db, signal_card_id=cid, price_at_report=500.0, ai_direction="BULLISH"
        )

        resolved = await prediction_resolver.resolve_predictions(
            db, price_fetcher=lambda _t: 550.0
        )

        assert resolved == 1
        rows = await pred_repo.list_for_signal_card(db, cid)
        scored = next(r for r in rows if r.id == pid)
        assert scored.price_1w_later == 550.0
        assert scored.actual_change_1w == 10.0
        assert scored.prediction_correct is True

    @pytest.mark.asyncio
    async def test_immature_prediction_is_skipped(self, db):
        recent = datetime.now(timezone.utc) - timedelta(days=2)
        cid = await _insert_signal_card(db, created_at=recent)
        await _insert_prediction(db, signal_card_id=cid)

        resolved = await prediction_resolver.resolve_predictions(
            db, price_fetcher=lambda _t: 550.0
        )

        assert resolved == 0
        unchecked = await pred_repo.list_unchecked(db)
        assert len(unchecked) == 1

    @pytest.mark.asyncio
    async def test_unavailable_price_leaves_prediction_unchecked(self, db):
        old = datetime.now(timezone.utc) - timedelta(days=8)
        cid = await _insert_signal_card(db, created_at=old)
        await _insert_prediction(db, signal_card_id=cid)

        resolved = await prediction_resolver.resolve_predictions(
            db, price_fetcher=lambda _t: None
        )

        assert resolved == 0
        unchecked = await pred_repo.list_unchecked(db)
        assert len(unchecked) == 1

    @pytest.mark.asyncio
    async def test_legacy_prediction_without_source_date_is_resolved(self, db):
        # No signal_card_id / report_id → source_date is NULL → treated as mature.
        await _insert_prediction(db, price_at_report=100.0, ai_direction="BEARISH")

        resolved = await prediction_resolver.resolve_predictions(
            db, price_fetcher=lambda _t: 90.0
        )

        assert resolved == 1

    @pytest.mark.asyncio
    async def test_price_is_fetched_once_per_ticker(self, db):
        old = datetime.now(timezone.utc) - timedelta(days=8)
        cid = await _insert_signal_card(db, created_at=old)
        await _insert_prediction(db, signal_card_id=cid, ticker="NVDA")
        await _insert_prediction(db, signal_card_id=cid, ticker="NVDA")

        calls: list[str] = []

        def fetch(ticker: str) -> float:
            calls.append(ticker)
            return 550.0

        resolved = await prediction_resolver.resolve_predictions(db, price_fetcher=fetch)

        assert resolved == 2
        assert calls == ["NVDA"]  # cached across both rows
