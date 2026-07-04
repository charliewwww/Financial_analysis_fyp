"""
Tests for app.db.repositories.* using an in-memory SQLite database.

Covers:
  - reports repository  (create, list, get)
  - signals repository  (create_run, update_run_status, get_run, list_runs,
                         create_signal_card, get_signal_card, get_latest_signal,
                         list_signal_cards)
  - predictions repository  (list_for_report, list_for_signal_card,
                              update_actual_price, get_accuracy_stats)
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from sqlalchemy import insert, text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.db.repositories import agents as agent_repo
from app.db.repositories import predictions as pred_repo
from app.db.repositories import reports as report_repo
from app.db.repositories import signals as signal_repo
from app.db.repositories import users as user_repo
from app.db.repositories import chief_verdicts as verdict_repo
from app.db.tables import pipeline_runs, predictions, reports, signal_cards
from app.schemas.reports import PredictionSchema


# ══════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════

_NOW = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)


async def _insert_report(db: AsyncConnection, **overrides) -> int:
    vals = dict(
        sector_id="ai_semiconductors",
        sector_name="AI & Semiconductors",
        created_at=_NOW,
        status="active",
        analysis="Full analysis text",
        news_used=5,
    )
    vals.update(overrides)
    result = await db.execute(
        insert(reports).values(**vals).returning(reports.c.id)
    )
    return result.scalar_one()


async def _insert_signal_card(db: AsyncConnection, **overrides) -> int:
    vals = dict(
        ticker="NVDA",
        signal="BULLISH",
        conviction=4,
        one_line="Strong buy",
        confidence=0.8,
        created_at=_NOW,
        status="active",
        numerical_claims=json.dumps([]),
        sources=json.dumps([]),
        supply_chain_impact=json.dumps([]),
    )
    vals.update(overrides)
    result = await db.execute(
        insert(signal_cards).values(**vals).returning(signal_cards.c.id)
    )
    return result.scalar_one()


async def _insert_prediction(db: AsyncConnection, **overrides) -> int:
    vals = dict(
        ticker="NVDA",
        price_at_report=500.0,
        ai_direction="BULLISH",
    )
    vals.update(overrides)
    result = await db.execute(
        insert(predictions).values(**vals).returning(predictions.c.id)
    )
    return result.scalar_one()


# ══════════════════════════════════════════════════════════════════
# Agents repository
# ══════════════════════════════════════════════════════════════════

class TestAgentsRepository:
    @pytest.mark.asyncio
    async def test_ensure_builtin_agents_seeds_catalog(self, db):
        await agent_repo.ensure_builtin_agents(db)
        rows = (await db.execute(text("SELECT name FROM agents ORDER BY id"))).all()
        names = [row[0] for row in rows]
        assert names == [
            "Supply Chain Analyst",
            "Value Analyst",
            "Momentum Analyst",
            "Risk Analyst",
        ]

    @pytest.mark.asyncio
    async def test_ensure_builtin_agents_is_idempotent(self, db):
        await agent_repo.ensure_builtin_agents(db)
        await agent_repo.ensure_builtin_agents(db)
        total = (await db.execute(text("SELECT COUNT(*) FROM agents"))).scalar_one()
        assert total == 4

    @pytest.mark.asyncio
    async def test_get_agent_for_run_defaults_to_supply_chain(self, db):
        agent = await agent_repo.get_agent_for_run(db, None)
        assert agent is not None
        assert agent.name == "Supply Chain Analyst"
        assert agent.identity_layer

    @pytest.mark.asyncio
    async def test_get_agent_for_run_unknown_returns_none(self, db):
        agent = await agent_repo.get_agent_for_run(db, 9999)
        assert agent is None

    @pytest.mark.asyncio
    async def test_list_agents_omits_identity_layer(self, db):
        items = await agent_repo.list_agents(db)
        assert len(items) == 4
        assert not hasattr(items[0], "identity_layer")

    @pytest.mark.asyncio
    async def test_create_agent_with_skill_persists_custom_runtime_prompt(self, db):
        agent = await agent_repo.create_agent_with_skill(
            db,
            name="Options Flow Analyst",
            description="Tracks volatility, flow, and dealer positioning.",
            skill_name="Options Flow Skill",
            skill_type="domain",
            skill_content=(
                "Focus on options volume, implied volatility term structure, dealer gamma, "
                "and whether positioning changes the risk/reward for the next market move."
            ),
        )

        assert agent.name == "Options Flow Analyst"
        assert agent.is_builtin is False

        skill_count = (await db.execute(text("SELECT COUNT(*) FROM skills WHERE agent_id = :agent_id"), {"agent_id": agent.id})).scalar_one()
        assert skill_count == 1

        runtime = await agent_repo.get_agent(db, agent.id)
        assert runtime is not None
        assert "Options Flow Skill" in runtime.identity_layer
        assert "dealer gamma" in runtime.identity_layer


# ══════════════════════════════════════════════════════════════════
# Reports repository
# ══════════════════════════════════════════════════════════════════

class TestReportsRepository:
    @pytest.mark.asyncio
    async def test_list_reports_empty(self, db):
        items, total = await report_repo.list_reports(db)
        assert items == []
        assert total == 0

    @pytest.mark.asyncio
    async def test_list_reports_returns_items(self, db):
        await _insert_report(db)
        await _insert_report(db, sector_id="space_rockets", sector_name="Space")
        items, total = await report_repo.list_reports(db)
        assert total == 2
        assert len(items) == 2

    @pytest.mark.asyncio
    async def test_list_reports_filters_by_sector(self, db):
        await _insert_report(db, sector_id="ai_semiconductors")
        await _insert_report(db, sector_id="space_rockets", sector_name="Space")
        items, total = await report_repo.list_reports(db, sector_id="space_rockets")
        assert total == 1
        assert items[0].sector_id == "space_rockets"

    @pytest.mark.asyncio
    async def test_list_reports_filters_by_market(self, db):
        await _insert_report(db, sector_id="us_technology", sector_name="US Tech")
        await _insert_report(db, sector_id="hk_tech", sector_name="HK Tech")
        await _insert_report(db, sector_id="ai_semiconductors", sector_name="Legacy")

        hk_items, hk_total = await report_repo.list_reports(db, market="hk")
        assert hk_total == 1
        assert hk_items[0].sector_id == "hk_tech"

        # US view includes legacy (non-prefixed) sector ids, excludes hk_*
        us_items, us_total = await report_repo.list_reports(db, market="us")
        assert us_total == 2
        assert all(not r.sector_id.startswith("hk_") for r in us_items)

    @pytest.mark.asyncio
    async def test_list_reports_pagination(self, db):
        for _ in range(5):
            await _insert_report(db)
        items, total = await report_repo.list_reports(db, page=1, page_size=2)
        assert total == 5
        assert len(items) == 2

    @pytest.mark.asyncio
    async def test_get_report_not_found(self, db):
        result = await report_repo.get_report(db, 9999)
        assert result is None

    @pytest.mark.asyncio
    async def test_get_report_returns_detail(self, db):
        rid = await _insert_report(db, analysis="Deep analysis here")
        detail = await report_repo.get_report(db, rid)
        assert detail is not None
        assert detail.analysis == "Deep analysis here"
        assert detail.sector_id == "ai_semiconductors"
        assert detail.predictions == []

    @pytest.mark.asyncio
    async def test_get_report_includes_predictions(self, db):
        rid = await _insert_report(db)
        await _insert_prediction(db, report_id=rid)
        await _insert_prediction(db, report_id=rid, ticker="AMD")
        detail = await report_repo.get_report(db, rid)
        assert len(detail.predictions) == 2
        tickers = {p.ticker for p in detail.predictions}
        assert "NVDA" in tickers
        assert "AMD" in tickers


# ══════════════════════════════════════════════════════════════════
# Signals repository — pipeline_runs
# ══════════════════════════════════════════════════════════════════

class TestSignalsRepository_Runs:
    @pytest.mark.asyncio
    async def test_create_and_get_run(self, db):
        run_pk = await signal_repo.create_run(db, "run-001", "NVDA", "ai_semiconductors")
        assert isinstance(run_pk, int)
        run = await signal_repo.get_run(db, "run-001")
        assert run is not None
        assert run.run_id == "run-001"
        assert run.ticker == "NVDA"
        assert run.status == "pending"

    @pytest.mark.asyncio
    async def test_get_run_not_found(self, db):
        result = await signal_repo.get_run(db, "does-not-exist")
        assert result is None

    @pytest.mark.asyncio
    async def test_update_run_status(self, db):
        await signal_repo.create_run(db, "run-002", "AMD", "ai_semiconductors")
        await signal_repo.update_run_status(db, "run-002", status="running", current_node="fetch")
        run = await signal_repo.get_run(db, "run-002")
        assert run.status == "running"
        assert run.current_node == "fetch"

    @pytest.mark.asyncio
    async def test_update_run_to_completed(self, db):
        await signal_repo.create_run(db, "run-003", "NVDA", "ai_semiconductors")
        finished = datetime.now(timezone.utc)
        await signal_repo.update_run_status(
            db, "run-003",
            status="completed",
            finished_at=finished,
            node_executions=[{"node_name": "save", "status": "completed"}],
        )
        run = await signal_repo.get_run(db, "run-003")
        assert run.status == "completed"
        assert run.finished_at is not None

    @pytest.mark.asyncio
    async def test_update_run_to_failed(self, db):
        await signal_repo.create_run(db, "run-004", "TSLA", "ev")
        await signal_repo.update_run_status(
            db, "run-004", status="failed", error="LLM timeout"
        )
        run = await signal_repo.get_run(db, "run-004")
        assert run.status == "failed"
        assert run.error == "LLM timeout"

    @pytest.mark.asyncio
    async def test_terminal_run_status_cannot_be_overwritten_by_late_running_update(self, db):
        await signal_repo.create_run(db, "run-terminal", "NVDA", "ai_semiconductors")
        await signal_repo.update_run_status(
            db,
            "run-terminal",
            status="failed",
            current_node="summarize",
            error="LLM provider quota exceeded",
        )
        await signal_repo.update_run_status(
            db,
            "run-terminal",
            status="running",
            current_node="summarize",
        )

        run = await signal_repo.get_run(db, "run-terminal")
        assert run.status == "failed"
        assert run.current_node == "summarize"
        assert run.error == "LLM provider quota exceeded"

    @pytest.mark.asyncio
    async def test_list_runs_treats_errored_running_rows_as_failed(self, db):
        await signal_repo.create_run(db, "run-legacy-error", "NVDA", "ai_semiconductors")
        await signal_repo.update_run_status(
            db,
            "run-legacy-error",
            status="running",
            current_node="summarize",
            error="LLM provider quota exceeded",
        )

        items, total = await signal_repo.list_runs(db, ticker="NVDA")
        assert total == 1
        assert items[0].status == "failed"
        assert items[0].error == "LLM provider quota exceeded"

    @pytest.mark.asyncio
    async def test_list_runs_empty(self, db):
        items, total = await signal_repo.list_runs(db)
        assert items == []
        assert total == 0

    @pytest.mark.asyncio
    async def test_list_runs_filters_by_ticker(self, db):
        await signal_repo.create_run(db, "r1", "NVDA", "ai")
        await signal_repo.create_run(db, "r2", "AMD", "ai")
        await signal_repo.create_run(db, "r3", "NVDA", "ai")
        items, total = await signal_repo.list_runs(db, ticker="NVDA")
        assert total == 2
        for item in items:
            assert item.ticker == "NVDA"

    @pytest.mark.asyncio
    async def test_list_runs_pagination(self, db):
        for i in range(6):
            await signal_repo.create_run(db, f"r-{i}", "NVDA", "ai")
        items, total = await signal_repo.list_runs(db, page=1, page_size=4)
        assert total == 6
        assert len(items) == 4


# ══════════════════════════════════════════════════════════════════
# Signals repository — signal_cards
# ══════════════════════════════════════════════════════════════════

class TestSignalsRepository_Cards:
    @pytest.mark.asyncio
    async def test_create_and_get_signal_card(self, db):
        card_id = await signal_repo.create_signal_card(
            db,
            ticker="NVDA",
            signal="BULLISH",
            conviction=5,
            one_line="Strong AI demand",
            confidence=0.9,
        )
        assert isinstance(card_id, int)
        card = await signal_repo.get_signal_card(db, card_id)
        assert card is not None
        assert card.ticker == "NVDA"
        assert card.signal == "BULLISH"
        assert card.conviction == 5

    @pytest.mark.asyncio
    async def test_get_signal_card_not_found(self, db):
        result = await signal_repo.get_signal_card(db, 9999)
        assert result is None

    @pytest.mark.asyncio
    async def test_signal_card_with_sub_schemas(self, db):
        card_id = await signal_repo.create_signal_card(
            db,
            ticker="TSM",
            signal="BEARISH",
            conviction=3,
            one_line="Demand weakness",
            confidence=0.6,
            numerical_claims=[{"claim": "Revenue -5%", "verified": True, "source": "10-Q"}],
            sources=[{"url": "http://x.com", "title": "Reuters", "domain": "reuters.com"}],
            supply_chain_impact=[{"ticker": "NVDA", "direction": "▼", "reason": "upstream cut"}],
        )
        card = await signal_repo.get_signal_card(db, card_id)
        assert len(card.numerical_claims) == 1
        assert card.numerical_claims[0].verified is True
        assert card.sources[0].domain == "reuters.com"
        assert card.supply_chain_impact[0].direction == "▼"

    @pytest.mark.asyncio
    async def test_get_latest_signal_none(self, db):
        result = await signal_repo.get_latest_signal(db, "AAPL")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_latest_signal_returns_newest(self, db):
        # Insert two cards; the second should be returned as latest
        await signal_repo.create_signal_card(
            db, ticker="NVDA", signal="NEUTRAL",
            conviction=2, one_line="First", confidence=0.5,
        )
        await signal_repo.create_signal_card(
            db, ticker="NVDA", signal="BULLISH",
            conviction=5, one_line="Latest", confidence=0.9,
        )
        card = await signal_repo.get_latest_signal(db, "NVDA")
        assert card is not None
        assert card.one_line == "Latest"

    @pytest.mark.asyncio
    async def test_list_signal_cards_empty(self, db):
        items, total = await signal_repo.list_signal_cards(db)
        assert items == []
        assert total == 0

    @pytest.mark.asyncio
    async def test_list_signal_cards_filter_by_signal(self, db):
        await signal_repo.create_signal_card(
            db, ticker="NVDA", signal="BULLISH",
            conviction=4, one_line="Bullish", confidence=0.8,
        )
        await signal_repo.create_signal_card(
            db, ticker="AMD", signal="BEARISH",
            conviction=2, one_line="Bearish", confidence=0.4,
        )
        items, total = await signal_repo.list_signal_cards(db, signal="BULLISH")
        assert total == 1
        assert items[0].ticker == "NVDA"

    @pytest.mark.asyncio
    async def test_list_signal_cards_filter_by_ticker(self, db):
        for ticker in ["NVDA", "AMD", "NVDA"]:
            await signal_repo.create_signal_card(
                db, ticker=ticker, signal="NEUTRAL",
                conviction=3, one_line="X", confidence=0.5,
            )
        items, total = await signal_repo.list_signal_cards(db, ticker="NVDA")
        assert total == 2

    @pytest.mark.asyncio
    async def test_list_signal_cards_pagination(self, db):
        for _ in range(5):
            await signal_repo.create_signal_card(
                db, ticker="NVDA", signal="BULLISH",
                conviction=4, one_line="X", confidence=0.8,
            )
        items, total = await signal_repo.list_signal_cards(db, page=1, page_size=3)
        assert total == 5
        assert len(items) == 3

    @pytest.mark.asyncio
    async def test_list_signal_cards_filter_by_market(self, db):
        await signal_repo.create_signal_card(
            db, ticker="NVDA", signal="BULLISH",
            conviction=4, one_line="US name", confidence=0.8,
        )
        await signal_repo.create_signal_card(
            db, ticker="0700.HK", signal="BULLISH",
            conviction=4, one_line="HK name", confidence=0.8,
        )

        hk_items, hk_total = await signal_repo.list_signal_cards(db, market="hk")
        assert hk_total == 1
        assert hk_items[0].ticker == "0700.HK"

        us_items, us_total = await signal_repo.list_signal_cards(db, market="us")
        assert us_total == 1
        assert us_items[0].ticker == "NVDA"

        _, all_total = await signal_repo.list_signal_cards(db)
        assert all_total == 2


# ══════════════════════════════════════════════════════════════════
# Predictions repository
# ══════════════════════════════════════════════════════════════════

class TestPredictionsRepository:
    @pytest.mark.asyncio
    async def test_list_for_report_empty(self, db):
        rid = await _insert_report(db)
        result = await pred_repo.list_for_report(db, rid)
        assert result == []

    @pytest.mark.asyncio
    async def test_list_for_report_returns_predictions(self, db):
        rid = await _insert_report(db)
        await _insert_prediction(db, report_id=rid, ticker="NVDA")
        await _insert_prediction(db, report_id=rid, ticker="AMD")
        result = await pred_repo.list_for_report(db, rid)
        assert len(result) == 2
        tickers = {p.ticker for p in result}
        assert tickers == {"NVDA", "AMD"}

    @pytest.mark.asyncio
    async def test_list_for_signal_card_empty(self, db):
        cid = await _insert_signal_card(db)
        result = await pred_repo.list_for_signal_card(db, cid)
        assert result == []

    @pytest.mark.asyncio
    async def test_list_for_signal_card_returns_predictions(self, db):
        cid = await _insert_signal_card(db)
        await _insert_prediction(db, signal_card_id=cid)
        result = await pred_repo.list_for_signal_card(db, cid)
        assert len(result) == 1
        assert result[0].ticker == "NVDA"

    @pytest.mark.asyncio
    async def test_list_unchecked(self, db):
        cid = await _insert_signal_card(db)
        # unchecked prediction (no price_1w_later)
        await _insert_prediction(db, signal_card_id=cid, ticker="NVDA")
        # checked prediction (price_1w_later set)
        await db.execute(
            insert(predictions).values(
                ticker="AMD", signal_card_id=cid,
                price_at_report=100.0, price_1w_later=105.0,
                ai_direction="BULLISH",
            )
        )
        unchecked = await pred_repo.list_unchecked(db)
        assert len(unchecked) == 1
        assert unchecked[0]["ticker"] == "NVDA"

    @pytest.mark.asyncio
    async def test_update_actual_price_bullish_correct(self, db):
        cid = await _insert_signal_card(db)
        pid = await _insert_prediction(
            db, signal_card_id=cid, ticker="NVDA",
            price_at_report=500.0, ai_direction="BULLISH",
        )
        await pred_repo.update_actual_price(db, pid, actual_price=520.0)
        rows = await pred_repo.list_for_signal_card(db, cid)
        p = rows[0]
        assert p.price_1w_later == 520.0
        assert p.prediction_correct is True
        assert p.actual_change_1w == pytest.approx(4.0, abs=0.05)

    @pytest.mark.asyncio
    async def test_update_actual_price_bullish_wrong(self, db):
        cid = await _insert_signal_card(db)
        pid = await _insert_prediction(
            db, signal_card_id=cid, ticker="NVDA",
            price_at_report=500.0, ai_direction="BULLISH",
        )
        await pred_repo.update_actual_price(db, pid, actual_price=480.0)
        rows = await pred_repo.list_for_signal_card(db, cid)
        assert rows[0].prediction_correct is False

    @pytest.mark.asyncio
    async def test_update_actual_price_bearish_correct(self, db):
        cid = await _insert_signal_card(db)
        pid = await _insert_prediction(
            db, signal_card_id=cid, ticker="TSM",
            price_at_report=200.0, ai_direction="BEARISH",
        )
        await pred_repo.update_actual_price(db, pid, actual_price=190.0)
        rows = await pred_repo.list_for_signal_card(db, cid)
        assert rows[0].prediction_correct is True

    @pytest.mark.asyncio
    async def test_update_actual_price_neutral_correct(self, db):
        """NEUTRAL is correct if |actual_change| < 2%."""
        cid = await _insert_signal_card(db)
        pid = await _insert_prediction(
            db, signal_card_id=cid, ticker="MSFT",
            price_at_report=300.0, ai_direction="NEUTRAL",
        )
        # 0.5% change → neutral correct
        await pred_repo.update_actual_price(db, pid, actual_price=301.5)
        rows = await pred_repo.list_for_signal_card(db, cid)
        assert rows[0].prediction_correct is True

    @pytest.mark.asyncio
    async def test_update_actual_price_nonexistent_noop(self, db):
        """Updating a non-existent prediction ID should not raise."""
        await pred_repo.update_actual_price(db, 9999, actual_price=100.0)

    @pytest.mark.asyncio
    async def test_get_accuracy_stats_empty(self, db):
        stats = await pred_repo.get_accuracy_stats(db)
        assert stats.total == 0
        assert stats.checked == 0
        assert stats.direction_accuracy_pct is None

    @pytest.mark.asyncio
    async def test_get_accuracy_stats_with_data(self, db):
        cid = await _insert_signal_card(db)
        # Insert 3 checked predictions: 2 correct, 1 incorrect
        for is_correct in [True, True, False]:
            pid = await _insert_prediction(
                db, signal_card_id=cid,
                price_at_report=100.0, ai_direction="BULLISH",
            )
            await pred_repo.update_actual_price(
                db, pid,
                actual_price=105.0 if is_correct else 95.0,
            )
        stats = await pred_repo.get_accuracy_stats(db)
        assert stats.total == 3
        assert stats.checked == 3
        assert stats.unchecked == 0
        assert stats.direction_correct == 2
        assert stats.direction_incorrect == 1
        assert stats.direction_accuracy_pct == pytest.approx(66.67, abs=0.1)


# ══════════════════════════════════════════════════════════════════
# User-scoping: reports and signals are filtered by user_email
# ══════════════════════════════════════════════════════════════════

class TestUserScoping:
    """
    Verify that list/get functions only return rows belonging to the
    requesting user, and that legacy rows (user_email=NULL) are visible
    to every user.
    """

    @pytest.mark.asyncio
    async def test_list_reports_scoped_to_user(self, db):
        await _insert_report(db, user_email="alice@example.com", sector_name="Alice sector")
        await _insert_report(db, user_email="bob@example.com", sector_name="Bob sector")
        items, total = await report_repo.list_reports(db, user_email="alice@example.com")
        assert total == 1
        assert items[0].sector_name == "Alice sector"

    @pytest.mark.asyncio
    async def test_list_reports_legacy_rows_visible_to_all(self, db):
        """Rows with user_email=NULL are shared across all users."""
        await _insert_report(db, user_email=None, sector_name="Legacy")
        items, total = await report_repo.list_reports(db, user_email="alice@example.com")
        assert total == 1
        assert items[0].sector_name == "Legacy"

    @pytest.mark.asyncio
    async def test_get_report_owned_by_other_user_returns_none(self, db):
        rid = await _insert_report(db, user_email="bob@example.com")
        result = await report_repo.get_report(db, rid, user_email="alice@example.com")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_report_legacy_row_visible(self, db):
        rid = await _insert_report(db, user_email=None)
        result = await report_repo.get_report(db, rid, user_email="alice@example.com")
        assert result is not None

    @pytest.mark.asyncio
    async def test_list_signal_cards_scoped_to_user(self, db):
        await signal_repo.create_signal_card(
            db, ticker="NVDA", signal="BULLISH",
            conviction=4, one_line="Alice card", confidence=0.8,
            user_email="alice@example.com",
        )
        await signal_repo.create_signal_card(
            db, ticker="AMD", signal="BEARISH",
            conviction=2, one_line="Bob card", confidence=0.4,
            user_email="bob@example.com",
        )
        items, total = await signal_repo.list_signal_cards(
            db, user_email="alice@example.com"
        )
        assert total == 1
        assert items[0].ticker == "NVDA"

    @pytest.mark.asyncio
    async def test_list_signal_cards_legacy_rows_visible(self, db):
        """Cards with no user_email are always included."""
        await signal_repo.create_signal_card(
            db, ticker="NVDA", signal="BULLISH",
            conviction=4, one_line="Legacy card", confidence=0.8,
            user_email=None,
        )
        items, total = await signal_repo.list_signal_cards(
            db, user_email="alice@example.com"
        )
        assert total == 1

    @pytest.mark.asyncio
    async def test_get_signal_card_owned_by_other_returns_none(self, db):
        cid = await signal_repo.create_signal_card(
            db, ticker="NVDA", signal="BULLISH",
            conviction=4, one_line="Bob card", confidence=0.8,
            user_email="bob@example.com",
        )
        result = await signal_repo.get_signal_card(db, cid, user_email="alice@example.com")
        assert result is None

    @pytest.mark.asyncio
    async def test_list_runs_scoped_to_user(self, db):
        await signal_repo.create_run(
            db, "run-1", "NVDA", "ai_semis", user_email="alice@example.com"
        )
        await signal_repo.create_run(
            db, "run-2", "AMD", "ai_semis", user_email="bob@example.com"
        )
        items, total = await signal_repo.list_runs(db, user_email="alice@example.com")
        assert total == 1
        assert items[0].ticker == "NVDA"


# ══════════════════════════════════════════════════════════════════
# Chief verdicts — market scoping for the House Call accuracy panel
# ══════════════════════════════════════════════════════════════════

class TestChiefVerdictMarketScope:
    @staticmethod
    async def _seed(db, ticker: str) -> None:
        await verdict_repo.create(
            db,
            {
                "ticker": ticker,
                "action": "BUY",
                "conviction": 4,
                "deciding_reason": "test",
                "summary": "test",
                "analyst_count": 1,
            },
        )

    @pytest.mark.asyncio
    async def test_get_accuracy_filters_by_market(self, db):
        await self._seed(db, "NVDA")
        await self._seed(db, "0700.HK")

        hk = await verdict_repo.get_accuracy(db, market="hk")
        assert hk.total == 1
        assert hk.recent[0].ticker == "0700.HK"

        us = await verdict_repo.get_accuracy(db, market="us")
        assert us.total == 1
        assert us.recent[0].ticker == "NVDA"

        every = await verdict_repo.get_accuracy(db)
        assert every.total == 2


# ══════════════════════════════════════════════════════════════════
# User details repository
# ══════════════════════════════════════════════════════════════════

class TestUserDetailsRepository:
    @pytest.mark.asyncio
    async def test_get_or_create_creates_new_profile(self, db):
        profile = await user_repo.get_or_create(db, "alice@example.com")
        assert profile.email == "alice@example.com"
        assert profile.username is None
        assert profile.saved_sectors == []
        assert profile.preferences == {}

    @pytest.mark.asyncio
    async def test_get_or_create_returns_existing_profile(self, db):
        await user_repo.get_or_create(db, "alice@example.com")
        # Second call should return the existing row, not create a duplicate
        profile = await user_repo.get_or_create(db, "alice@example.com")
        assert profile.email == "alice@example.com"

    @pytest.mark.asyncio
    async def test_update_profile_username(self, db):
        await user_repo.get_or_create(db, "alice@example.com")
        updated = await user_repo.update_profile(
            db, "alice@example.com", username="Alice"
        )
        assert updated.username == "Alice"

    @pytest.mark.asyncio
    async def test_update_profile_saved_sectors(self, db):
        await user_repo.get_or_create(db, "alice@example.com")
        updated = await user_repo.update_profile(
            db, "alice@example.com",
            saved_sectors=["semiconductors", "ev_battery"],
        )
        assert updated.saved_sectors == ["semiconductors", "ev_battery"]

    @pytest.mark.asyncio
    async def test_update_profile_preferences(self, db):
        await user_repo.get_or_create(db, "alice@example.com")
        prefs = {"email_digest": True, "default_page_size": 20}
        updated = await user_repo.update_profile(
            db, "alice@example.com", preferences=prefs
        )
        assert updated.preferences["email_digest"] is True

    @pytest.mark.asyncio
    async def test_update_profile_partial_only_touches_provided_fields(self, db):
        await user_repo.get_or_create(db, "alice@example.com")
        await user_repo.update_profile(db, "alice@example.com", username="Alice")
        # Now update only saved_sectors; username should be preserved
        updated = await user_repo.update_profile(
            db, "alice@example.com",
            saved_sectors=["semiconductors"],
        )
        assert updated.username == "Alice"
        assert updated.saved_sectors == ["semiconductors"]

    @pytest.mark.asyncio
    async def test_two_users_have_independent_profiles(self, db):
        await user_repo.get_or_create(db, "alice@example.com")
        await user_repo.get_or_create(db, "bob@example.com")
        await user_repo.update_profile(db, "alice@example.com", username="Alice")
        await user_repo.update_profile(db, "bob@example.com", username="Bob")
        alice = await user_repo.get_or_create(db, "alice@example.com")
        bob = await user_repo.get_or_create(db, "bob@example.com")
        assert alice.username == "Alice"
        assert bob.username == "Bob"
