"""
Tests for the FastAPI routes using TestClient (sync wrapper over ASGI).

These are integration-level tests: the full app is instantiated but the
database dependency is overridden and repository calls are mocked per test,
so no PostgreSQL connection is needed.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.schemas.agents import AgentRuntimeSchema, AgentSummarySchema
from app.schemas.analysis import SignalCardSchema
from app.schemas.common import PaginatedResponse
from app.schemas.pipeline import PipelineRunSchema, RunSummary
from app.schemas.reports import (
    AccuracyStats,
    PredictionSchema,
    ReportDetail,
    ReportSummary,
)
from app.schemas.users import UserDetailSchema
from app.schemas.watchlist import WatchlistItemSchema

# The email returned by the auth dependency in tests
TEST_USER = "test@example.com"


# ── App fixture ────────────────────────────────────────────────────
# We patch the lifespan's DB calls and override the get_db dependency
# so the test client never tries to connect to PostgreSQL.

@pytest.fixture(scope="module")
def client():
    """
    TestClient with the DB dependency overridden.

    The lifespan calls init_engine() → create_all_tables() on startup;
    we patch both so they're no-ops.  The get_db FastAPI dependency is
    overridden to yield a mock AsyncConnection so every route that depends
    on the DB gets a mock without hitting the engine.
    """
    with (
        patch("app.main.init_engine", return_value=None),
        patch("app.main.create_all_tables", new_callable=AsyncMock),
        patch("app.main.agent_repo.ensure_builtin_agents_for_engine", new_callable=AsyncMock),
        patch("app.main._reconcile_orphaned_runs", new_callable=AsyncMock),
        patch("app.main.dispose_engine", new_callable=AsyncMock),
        patch("app.main.start_scheduler"),
        patch("app.main.stop_scheduler"),
        # The daily free-analysis quota needs a real DB (it reads user role +
        # counts runs); these route tests use a mock DB and exercise the
        # concurrency cap instead, so disable the daily quota here. Dedicated
        # daily-quota tests run against a real in-memory DB in test_auth.py.
        patch("app.api.routes.pipeline.settings.daily_run_quota", 0),
    ):
        # Import here so patch is active during module-level side effects
        from app.core.auth import get_current_user, require_admin
        from app.db.engine import get_db
        from app.main import app

        # Override FastAPI's DB dependency with a no-op mock
        async def _mock_db():
            yield AsyncMock()

        # Override auth so tests don't need a real session cookie
        async def _mock_user():
            return TEST_USER

        # Treat the test user as an operator so admin-gated routes are reachable
        async def _mock_admin():
            return TEST_USER

        app.dependency_overrides[get_db] = _mock_db
        app.dependency_overrides[get_current_user] = _mock_user
        app.dependency_overrides[require_admin] = _mock_admin

        with TestClient(app, raise_server_exceptions=True) as c:
            yield c

        app.dependency_overrides.clear()


# ── Helpers ────────────────────────────────────────────────────────

def _signal_card_dict(**overrides) -> dict:
    base = dict(
        id=1, ticker="NVDA", signal="BULLISH", conviction=4,
        one_line="Strong AI demand", confidence=0.8,
        created_at="2025-01-15T12:00:00+00:00", status="active",
    )
    base.update(overrides)
    return base


def _prediction_dict(**overrides) -> dict:
    base = dict(id=1, ticker="NVDA")
    base.update(overrides)
    return base


def _report_summary_dict(**overrides) -> dict:
    base = dict(id=1, sector_id="ai", sector_name="AI", created_at="2025-01-01")
    base.update(overrides)
    return base


def _agent_runtime(**overrides) -> AgentRuntimeSchema:
    base = dict(
        id=1,
        name="Supply Chain Analyst",
        description="Default LangGraph analyst",
        identity_layer="system prompt",
        is_builtin=True,
        created_at="2025-01-01T00:00:00+00:00",
    )
    base.update(overrides)
    return AgentRuntimeSchema(**base)


def _agent_summary(**overrides) -> AgentSummarySchema:
    base = dict(
        id=1,
        name="Supply Chain Analyst",
        description="Default LangGraph analyst",
        is_builtin=True,
        created_at="2025-01-01T00:00:00+00:00",
    )
    base.update(overrides)
    return AgentSummarySchema(**base)


# ══════════════════════════════════════════════════════════════════
# /health
# ══════════════════════════════════════════════════════════════════

class TestHealthEndpoint:
    def test_returns_200(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_body(self, client):
        resp = client.get("/health")
        assert resp.json()["status"] == "ok"
        assert "version" in resp.json()


# ══════════════════════════════════════════════════════════════════
# /api/v1/reports
# ══════════════════════════════════════════════════════════════════

class TestReportsEndpoints:
    def test_list_reports(self, client):
        summary = ReportSummary(**_report_summary_dict())
        with patch("app.api.routes.reports.report_repo.list_reports", new_callable=AsyncMock) as m:
            m.return_value = ([summary], 1)
            resp = client.get("/api/v1/reports/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["sector_id"] == "ai"

    def test_list_reports_with_sector_filter(self, client):
        with patch("app.api.routes.reports.report_repo.list_reports", new_callable=AsyncMock) as m:
            m.return_value = ([], 0)
            resp = client.get("/api/v1/reports/?sector_id=space_rockets")
        assert resp.status_code == 200
        m.assert_called_once()
        call_kwargs = m.call_args.kwargs
        assert call_kwargs["sector_id"] == "space_rockets"

    def test_get_report_not_found(self, client):
        with patch("app.api.routes.reports.report_repo.get_report", new_callable=AsyncMock) as m:
            m.return_value = None
            resp = client.get("/api/v1/reports/9999")
        assert resp.status_code == 404

    def test_get_report_found(self, client):
        detail = ReportDetail(
            id=1, sector_id="ai", sector_name="AI",
            created_at="2025-01-01", analysis="Deep analysis",
        )
        with patch("app.api.routes.reports.report_repo.get_report", new_callable=AsyncMock) as m:
            m.return_value = detail
            resp = client.get("/api/v1/reports/1")
        assert resp.status_code == 200
        assert resp.json()["analysis"] == "Deep analysis"

    def test_get_report_predictions(self, client):
        detail = ReportDetail(
            id=1, sector_id="ai", sector_name="AI",
            created_at="2025-01-01", analysis="...",
        )
        pred = PredictionSchema(id=1, ticker="NVDA", report_id=1)
        with (
            patch("app.api.routes.reports.report_repo.get_report", new_callable=AsyncMock) as rm,
            patch("app.api.routes.reports.pred_repo.list_for_report", new_callable=AsyncMock) as pm,
        ):
            rm.return_value = detail
            pm.return_value = [pred]
            resp = client.get("/api/v1/reports/1/predictions")
        assert resp.status_code == 200
        assert resp.json()[0]["ticker"] == "NVDA"

    def test_get_report_predictions_report_not_found(self, client):
        with patch("app.api.routes.reports.report_repo.get_report", new_callable=AsyncMock) as m:
            m.return_value = None
            resp = client.get("/api/v1/reports/9999/predictions")
        assert resp.status_code == 404


# ══════════════════════════════════════════════════════════════════
# /api/v1/signals
# ══════════════════════════════════════════════════════════════════

class TestSignalsEndpoints:
    def test_list_signals(self, client):
        card = SignalCardSchema(**_signal_card_dict())
        with patch("app.api.routes.signals.signal_repo.list_signal_cards", new_callable=AsyncMock) as m:
            m.return_value = ([card], 1)
            resp = client.get("/api/v1/signals/")
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    def test_list_signals_with_filters(self, client):
        with patch("app.api.routes.signals.signal_repo.list_signal_cards", new_callable=AsyncMock) as m:
            m.return_value = ([], 0)
            resp = client.get("/api/v1/signals/?ticker=NVDA&signal=BULLISH&page=2&page_size=5")
        assert resp.status_code == 200
        kwargs = m.call_args.kwargs
        assert kwargs["ticker"] == "NVDA"
        assert kwargs["signal"] == "BULLISH"
        assert kwargs["page"] == 2
        assert kwargs["page_size"] == 5

    def test_accuracy_endpoint(self, client):
        stats = AccuracyStats(total=10, checked=8, direction_correct=6,
                              direction_incorrect=2, direction_accuracy_pct=75.0)
        with patch("app.api.routes.signals.pred_repo.get_accuracy_stats", new_callable=AsyncMock) as m:
            m.return_value = stats
            resp = client.get("/api/v1/signals/accuracy")
        assert resp.status_code == 200
        assert resp.json()["direction_accuracy_pct"] == 75.0

    def test_latest_signal_not_found(self, client):
        with patch("app.api.routes.signals.signal_repo.get_latest_signal", new_callable=AsyncMock) as m:
            m.return_value = None
            resp = client.get("/api/v1/signals/latest/AAPL")
        assert resp.status_code == 404

    def test_latest_signal_found(self, client):
        card = SignalCardSchema(**_signal_card_dict(ticker="AAPL"))
        with patch("app.api.routes.signals.signal_repo.get_latest_signal", new_callable=AsyncMock) as m:
            m.return_value = card
            resp = client.get("/api/v1/signals/latest/AAPL")
        assert resp.status_code == 200
        assert resp.json()["ticker"] == "AAPL"

    def test_get_signal_card_not_found(self, client):
        with patch("app.api.routes.signals.signal_repo.get_signal_card", new_callable=AsyncMock) as m:
            m.return_value = None
            resp = client.get("/api/v1/signals/9999")
        assert resp.status_code == 404

    def test_get_signal_card_found(self, client):
        card = SignalCardSchema(**_signal_card_dict())
        with patch("app.api.routes.signals.signal_repo.get_signal_card", new_callable=AsyncMock) as m:
            m.return_value = card
            resp = client.get("/api/v1/signals/1")
        assert resp.status_code == 200
        assert resp.json()["signal"] == "BULLISH"

    def test_signal_chat_found(self, client):
        card = SignalCardSchema(**_signal_card_dict(
            key_catalyst="Hyperscaler demand is accelerating.",
            key_risk="Export controls could limit sales.",
            numerical_claims=[{"claim": "Revenue +12%", "verified": True, "source": "10-Q"}],
            sources=[{"url": "https://example.com/a", "title": "Reuters story", "domain": "reuters.com", "summary": "AI demand rose."}],
        ))
        model_json = '{"answer":"Demand rose.","citations":["source: reuters.com"],"limitations":[],"grounded":true}'
        with (
            patch("app.api.routes.signals.signal_repo.get_signal_card", new_callable=AsyncMock) as card_mock,
            patch("app.api.routes.signals.call_llm_fast", return_value=model_json) as llm_mock,
        ):
            card_mock.return_value = card
            resp = client.post("/api/v1/signals/1/chat", json={"question": "What changed?"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["answer"] == "Demand rose."
        assert body["citations"][0]["label"] == "source: reuters.com"
        assert body["grounded"] is True
        llm_mock.assert_called_once()

    def test_signal_chat_not_found(self, client):
        with patch("app.api.routes.signals.signal_repo.get_signal_card", new_callable=AsyncMock) as m:
            m.return_value = None
            resp = client.post("/api/v1/signals/9999/chat", json={"question": "What changed?"})
        assert resp.status_code == 404

    def test_signal_chat_fallback_when_llm_fails(self, client):
        card = SignalCardSchema(**_signal_card_dict(key_risk="Export controls could limit sales."))
        with (
            patch("app.api.routes.signals.signal_repo.get_signal_card", new_callable=AsyncMock) as card_mock,
            patch("app.api.routes.signals.call_llm_fast", side_effect=RuntimeError("offline")),
        ):
            card_mock.return_value = card
            resp = client.post("/api/v1/signals/1/chat", json={"question": "What would invalidate this?"})
        assert resp.status_code == 200
        assert "Export controls" in resp.json()["answer"]
        assert resp.json()["grounded"] is True

    def test_get_signal_card_predictions(self, client):
        card = SignalCardSchema(**_signal_card_dict())
        pred = PredictionSchema(id=1, ticker="NVDA", signal_card_id=1)
        with (
            patch("app.api.routes.signals.signal_repo.get_signal_card", new_callable=AsyncMock) as cm,
            patch("app.api.routes.signals.pred_repo.list_for_signal_card", new_callable=AsyncMock) as pm,
        ):
            cm.return_value = card
            pm.return_value = [pred]
            resp = client.get("/api/v1/signals/1/predictions")
        assert resp.status_code == 200
        assert resp.json()[0]["signal_card_id"] == 1

    def test_accuracy_path_not_consumed_as_card_id(self, client):
        """
        /signals/accuracy must NOT be interpreted as /signals/{card_id}=accuracy.
        This verifies the router ordering is correct.
        """
        stats = AccuracyStats()
        with patch("app.api.routes.signals.pred_repo.get_accuracy_stats", new_callable=AsyncMock) as m:
            m.return_value = stats
            resp = client.get("/api/v1/signals/accuracy")
        assert resp.status_code == 200
        assert "total" in resp.json()

    def test_latest_path_not_consumed_as_card_id(self, client):
        """
        /signals/latest/{ticker} must NOT be routed to /signals/{card_id}={latest}.
        """
        card = SignalCardSchema(**_signal_card_dict(ticker="NVDA"))
        with patch("app.api.routes.signals.signal_repo.get_latest_signal", new_callable=AsyncMock) as m:
            m.return_value = card
            resp = client.get("/api/v1/signals/latest/NVDA")
        assert resp.status_code == 200


# ══════════════════════════════════════════════════════════════════
# /api/v1/agents
# ══════════════════════════════════════════════════════════════════

class TestAgentsEndpoints:
    def test_list_agents(self, client):
        agent = AgentSummarySchema(
            id=1,
            name="Supply Chain Analyst",
            description="Default LangGraph analyst",
            is_builtin=True,
            created_at="2025-01-01T00:00:00+00:00",
        )
        with patch("app.api.routes.agents.agent_repo.list_agents", new_callable=AsyncMock) as m:
            m.return_value = [agent]
            resp = client.get("/api/v1/agents")
        assert resp.status_code == 200
        data = resp.json()
        assert data[0]["name"] == "Supply Chain Analyst"
        assert "identity_layer" not in data[0]

    def test_create_agent_skill(self, client):
        agent = _agent_summary(
            id=5,
            name="Options Flow Analyst",
            description="Tracks volatility and dealer positioning.",
            is_builtin=False,
        )
        with patch("app.api.routes.agents.agent_repo.create_agent_with_skill", new_callable=AsyncMock) as m:
            m.return_value = agent
            resp = client.post(
                "/api/v1/agents",
                json={
                    "name": "Options Flow Analyst",
                    "description": "Tracks volatility and dealer positioning.",
                    "skill_name": "Options Flow Skill",
                    "skill_content": "Focus on options flow, implied volatility, dealer gamma, and positioning changes.",
                },
            )

        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Options Flow Analyst"
        assert data["is_builtin"] is False
        assert m.await_args.kwargs["skill_name"] == "Options Flow Skill"

    def test_create_agent_skill_conflict(self, client):
        from sqlalchemy.exc import IntegrityError

        with patch("app.api.routes.agents.agent_repo.create_agent_with_skill", new_callable=AsyncMock) as m:
            m.side_effect = IntegrityError("insert", {}, Exception("duplicate"))
            resp = client.post(
                "/api/v1/agents",
                json={
                    "name": "Options Flow Analyst",
                    "skill_content": "Focus on options flow, implied volatility, dealer gamma, and positioning changes.",
                },
            )

        assert resp.status_code == 409

    def test_create_agent_skill_passes_owner(self, client):
        agent = _agent_summary(id=7, name="Owned Analyst", is_builtin=False)
        with patch("app.api.routes.agents.agent_repo.create_agent_with_skill", new_callable=AsyncMock) as m:
            m.return_value = agent
            resp = client.post(
                "/api/v1/agents",
                json={
                    "name": "Owned Analyst",
                    "skill_content": "Focus on options flow, implied volatility, dealer gamma, and positioning changes.",
                },
            )

        assert resp.status_code == 201
        assert m.await_args.kwargs["user_email"] == TEST_USER

    def test_delete_agent_success(self, client):
        with patch("app.api.routes.agents.agent_repo.delete_agent", new_callable=AsyncMock) as m:
            m.return_value = True
            resp = client.delete("/api/v1/agents/5")

        assert resp.status_code == 204
        assert m.await_args.kwargs["user_email"] == TEST_USER

    def test_delete_agent_not_owned_returns_404(self, client):
        with patch("app.api.routes.agents.agent_repo.delete_agent", new_callable=AsyncMock) as m:
            m.return_value = False
            resp = client.delete("/api/v1/agents/999")

        assert resp.status_code == 404


# ══════════════════════════════════════════════════════════════════
# /api/v1/pipeline
# ══════════════════════════════════════════════════════════════════

class TestPipelineEndpoints:
    @pytest.fixture(autouse=True)
    def _under_run_quota(self):
        """Keep every trigger test under the concurrency cap by default.

        The mocked test DB can't run the real count query, so we patch the
        repository helper to report zero active runs. Dedicated tests below
        override this to assert the HTTP 429 path.
        """
        with patch(
            "app.api.routes.pipeline.signal_repo.count_active_runs",
            new_callable=AsyncMock,
        ) as m:
            m.return_value = 0
            yield m

    def test_list_runs_empty(self, client):
        with patch("app.api.routes.pipeline.signal_repo.list_runs", new_callable=AsyncMock) as m:
            m.return_value = ([], 0)
            resp = client.get("/api/v1/pipeline/runs")
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    def test_get_run_not_found(self, client):
        with patch("app.api.routes.pipeline.signal_repo.get_run_for_user", new_callable=AsyncMock) as m:
            m.return_value = None
            resp = client.get("/api/v1/pipeline/runs/no-such-run")
        assert resp.status_code == 404

    def test_get_run_found(self, client):
        run = PipelineRunSchema(
            id=1, run_id="abc-123", ticker="NVDA",
            sector_id="ai_semiconductors", status="completed",
            created_at="2025-01-01T00:00:00+00:00",
        )
        with patch("app.api.routes.pipeline.signal_repo.get_run_for_user", new_callable=AsyncMock) as m:
            m.return_value = run
            resp = client.get("/api/v1/pipeline/runs/abc-123")
        assert resp.status_code == 200
        assert resp.json()["status"] == "completed"

    def test_trigger_run_returns_202(self, client):
        with (
            patch("app.api.routes.pipeline.agent_repo.get_agent_for_run", new_callable=AsyncMock) as arm,
            patch("app.api.routes.pipeline.signal_repo.create_run", new_callable=AsyncMock) as crm,
            patch("app.api.routes.pipeline.runner.launch_run", new_callable=AsyncMock) as lrm,
            patch("app.api.routes.pipeline._ensure_llm_ready", new_callable=AsyncMock) as llm,
        ):
            arm.return_value = _agent_runtime()
            crm.return_value = 1
            lrm.return_value = None
            llm.return_value = None
            resp = client.post(
                "/api/v1/pipeline/runs",
                json={"ticker": "NVDA", "sector_id": "ai_semiconductors"},
            )
        assert resp.status_code == 202
        body = resp.json()
        assert "run_id" in body
        assert body["status"] == "pending"
        assert body["agent_id"] == 1
        launch_kwargs = lrm.call_args.kwargs
        assert launch_kwargs["agent_id"] == 1
        assert launch_kwargs["agent_name"] == "Supply Chain Analyst"

    def test_trigger_run_rejected_when_over_quota(self, client, _under_run_quota):
        from app.core.config import settings

        _under_run_quota.return_value = settings.pipeline_max_active_runs_per_user
        with (
            patch("app.api.routes.pipeline.agent_repo.get_agent_for_run", new_callable=AsyncMock) as arm,
            patch("app.api.routes.pipeline.signal_repo.create_run", new_callable=AsyncMock) as crm,
            patch("app.api.routes.pipeline.runner.launch_run", new_callable=AsyncMock) as lrm,
            patch("app.api.routes.pipeline._ensure_llm_ready", new_callable=AsyncMock) as llm,
        ):
            arm.return_value = _agent_runtime()
            resp = client.post(
                "/api/v1/pipeline/runs",
                json={"ticker": "NVDA", "sector_id": "ai_semiconductors"},
            )

        assert resp.status_code == 429
        assert "concurrent runs" in resp.json()["detail"]
        crm.assert_not_awaited()
        lrm.assert_not_awaited()
        llm.assert_not_awaited()

    def test_trigger_fanout_rejected_when_quota_too_low_for_board(self, client, _under_run_quota):
        from app.core.config import settings

        # One slot short of what a two-analyst board needs.
        _under_run_quota.return_value = settings.pipeline_max_active_runs_per_user - 1
        summaries = [
            _agent_summary(id=1, name="Supply Chain Analyst"),
            _agent_summary(id=2, name="Value Analyst"),
        ]
        runtimes = {
            1: _agent_runtime(id=1, name="Supply Chain Analyst"),
            2: _agent_runtime(id=2, name="Value Analyst"),
        }

        async def _get_agent(_db, agent_id, **_kwargs):
            return runtimes[agent_id]

        with (
            patch("app.api.routes.pipeline.agent_repo.list_agents", new_callable=AsyncMock) as lam,
            patch("app.api.routes.pipeline.agent_repo.get_agent", new_callable=AsyncMock) as gam,
            patch("app.api.routes.pipeline.signal_repo.create_run", new_callable=AsyncMock) as crm,
            patch("app.api.routes.pipeline.runner.launch_run", new_callable=AsyncMock) as lrm,
            patch("app.api.routes.pipeline._ensure_llm_ready", new_callable=AsyncMock) as llm,
        ):
            lam.return_value = summaries
            gam.side_effect = _get_agent
            resp = client.post("/api/v1/pipeline/runs/fanout", json={"ticker": "NVDA"})

        assert resp.status_code == 429
        crm.assert_not_awaited()
        lrm.assert_not_awaited()
        llm.assert_not_awaited()

    def test_trigger_run_fails_fast_when_llm_quota_exceeded(self, client):
        with (
            patch("app.api.routes.pipeline.agent_repo.get_agent_for_run", new_callable=AsyncMock) as arm,
            patch("app.api.routes.pipeline._ensure_llm_ready", new_callable=AsyncMock) as llm,
            patch("app.api.routes.pipeline.signal_repo.create_run", new_callable=AsyncMock) as crm,
            patch("app.api.routes.pipeline.runner.launch_run", new_callable=AsyncMock) as lrm,
        ):
            arm.return_value = _agent_runtime()
            llm.side_effect = HTTPException(
                status_code=503,
                detail="LLM provider quota exceeded. OpenRouter rejected the run before the analyst board could finish.",
            )
            resp = client.post(
                "/api/v1/pipeline/runs",
                json={"ticker": "NVDA", "sector_id": "ai_semiconductors"},
            )

        assert resp.status_code == 503
        assert "quota exceeded" in resp.json()["detail"]
        crm.assert_not_awaited()
        lrm.assert_not_awaited()

    def test_trigger_run_unknown_agent(self, client):
        with patch("app.api.routes.pipeline.agent_repo.get_agent_for_run", new_callable=AsyncMock) as arm:
            arm.return_value = None
            resp = client.post(
                "/api/v1/pipeline/runs",
                json={"ticker": "NVDA", "sector_id": "ai_semiconductors", "agent_id": 999},
            )
        assert resp.status_code == 404

    def test_trigger_fanout_infers_sector_and_launches_builtin_agents(self, client):
        summaries = [
            _agent_summary(id=1, name="Supply Chain Analyst"),
            _agent_summary(id=2, name="Value Analyst"),
        ]
        runtimes = {
            1: _agent_runtime(id=1, name="Supply Chain Analyst"),
            2: _agent_runtime(id=2, name="Value Analyst"),
        }

        async def _get_agent(_db, agent_id, **_kwargs):
            return runtimes[agent_id]

        with (
            patch("app.api.routes.pipeline.agent_repo.list_agents", new_callable=AsyncMock) as lam,
            patch("app.api.routes.pipeline.agent_repo.get_agent", new_callable=AsyncMock) as gam,
            patch("app.api.routes.pipeline.signal_repo.create_run", new_callable=AsyncMock) as crm,
            patch("app.api.routes.pipeline.runner.launch_run", new_callable=AsyncMock) as lrm,
            patch("app.api.routes.pipeline._ensure_llm_ready", new_callable=AsyncMock) as llm,
        ):
            lam.return_value = summaries
            gam.side_effect = _get_agent
            crm.return_value = 1
            lrm.return_value = None
            llm.return_value = None
            resp = client.post("/api/v1/pipeline/runs/fanout", json={"ticker": "NVDA"})

        assert resp.status_code == 202
        body = resp.json()
        assert body["ticker"] == "NVDA"
        assert body["sector_id"] == "ai_semiconductors"
        assert len(body["runs"]) == 2
        assert crm.await_count == 2
        assert lrm.await_count == 2
        launch_kwargs = lrm.call_args_list[0].kwargs
        assert launch_kwargs["agent_id"] == 1
        assert launch_kwargs["agent_name"] == "Supply Chain Analyst"

    def test_trigger_fanout_includes_custom_agents_by_default(self, client):
        summaries = [
            _agent_summary(id=1, name="Supply Chain Analyst"),
            _agent_summary(id=5, name="Options Flow Analyst", is_builtin=False),
        ]
        runtimes = {
            1: _agent_runtime(id=1, name="Supply Chain Analyst"),
            5: _agent_runtime(id=5, name="Options Flow Analyst", is_builtin=False),
        }

        async def _get_agent(_db, agent_id, **_kwargs):
            return runtimes[agent_id]

        with (
            patch("app.api.routes.pipeline.agent_repo.list_agents", new_callable=AsyncMock) as lam,
            patch("app.api.routes.pipeline.agent_repo.get_agent", new_callable=AsyncMock) as gam,
            patch("app.api.routes.pipeline.signal_repo.create_run", new_callable=AsyncMock),
            patch("app.api.routes.pipeline.runner.launch_run", new_callable=AsyncMock) as lrm,
            patch("app.api.routes.pipeline._ensure_llm_ready", new_callable=AsyncMock),
        ):
            lam.return_value = summaries
            gam.side_effect = _get_agent
            resp = client.post("/api/v1/pipeline/runs/fanout", json={"ticker": "NVDA"})

        assert resp.status_code == 202
        assert [run["agent_id"] for run in resp.json()["runs"]] == [1, 5]
        assert lrm.await_count == 2

    def test_trigger_sector_fanout_launches_all_tickers_in_one_request(self, client):
        summaries = [_agent_summary(id=1, name="Supply Chain Analyst")]

        with (
            patch("app.api.routes.pipeline.agent_repo.list_agents", new_callable=AsyncMock) as lam,
            patch("app.api.routes.pipeline.agent_repo.get_agent", new_callable=AsyncMock) as gam,
            patch("app.api.routes.pipeline.signal_repo.create_run", new_callable=AsyncMock) as crm,
            patch("app.api.routes.pipeline.runner.launch_run", new_callable=AsyncMock) as lrm,
            patch("app.api.routes.pipeline._ensure_llm_ready", new_callable=AsyncMock) as llm,
        ):
            lam.return_value = summaries
            gam.return_value = _agent_runtime(id=1, name="Supply Chain Analyst")
            resp = client.post(
                "/api/v1/pipeline/runs/sector-fanout",
                json={"sector_id": "ai_semiconductors", "tickers": ["NVDA", "AMD"]},
            )

        assert resp.status_code == 202
        body = resp.json()
        assert [item["ticker"] for item in body] == ["NVDA", "AMD"]
        assert crm.await_count == 2
        assert lrm.await_count == 2
        llm.assert_awaited_once()

    def test_trigger_sector_fanout_rejects_tickers_outside_sector(self, client):
        resp = client.post(
            "/api/v1/pipeline/runs/sector-fanout",
            json={"sector_id": "ai_semiconductors", "tickers": ["RKLB"]},
        )

        assert resp.status_code == 400
        assert "not configured" in resp.json()["detail"]

    def test_trigger_fanout_fails_fast_when_llm_quota_exceeded(self, client):
        summaries = [_agent_summary(id=1, name="Supply Chain Analyst")]

        with (
            patch("app.api.routes.pipeline.agent_repo.list_agents", new_callable=AsyncMock) as lam,
            patch("app.api.routes.pipeline.agent_repo.get_agent", new_callable=AsyncMock) as gam,
            patch("app.api.routes.pipeline._ensure_llm_ready", new_callable=AsyncMock) as llm,
            patch("app.api.routes.pipeline.signal_repo.create_run", new_callable=AsyncMock) as crm,
            patch("app.api.routes.pipeline.runner.launch_run", new_callable=AsyncMock) as lrm,
        ):
            lam.return_value = summaries
            gam.return_value = _agent_runtime(id=1, name="Supply Chain Analyst")
            llm.side_effect = HTTPException(
                status_code=503,
                detail="LLM provider quota exceeded. OpenRouter rejected the run before the analyst board could finish.",
            )
            resp = client.post("/api/v1/pipeline/runs/fanout", json={"ticker": "NVDA"})

        assert resp.status_code == 503
        assert "quota exceeded" in resp.json()["detail"]
        crm.assert_not_awaited()
        lrm.assert_not_awaited()

    def test_trigger_fanout_unknown_ticker_uses_general_sector(self, client):
        # Free-form tickers outside the curated catalog are now analysable;
        # they fall back to the synthetic "general" sector instead of 404.
        summaries = [_agent_summary(id=1, name="Supply Chain Analyst")]
        with (
            patch("app.api.routes.pipeline.agent_repo.list_agents", new_callable=AsyncMock) as lam,
            patch("app.api.routes.pipeline.agent_repo.get_agent", new_callable=AsyncMock) as gam,
            patch("app.api.routes.pipeline.signal_repo.create_run", new_callable=AsyncMock),
            patch("app.api.routes.pipeline.runner.launch_run", new_callable=AsyncMock) as lrm,
            patch("app.api.routes.pipeline._ensure_llm_ready", new_callable=AsyncMock),
        ):
            lam.return_value = summaries
            gam.return_value = _agent_runtime(id=1, name="Supply Chain Analyst")
            resp = client.post("/api/v1/pipeline/runs/fanout", json={"ticker": "ZZZZ"})

        assert resp.status_code == 202
        assert resp.json()["sector_id"] == "general"
        assert lrm.await_count == 1

    def test_trigger_fanout_unknown_agent(self, client):
        with patch("app.api.routes.pipeline.agent_repo.get_agent", new_callable=AsyncMock) as gam:
            gam.return_value = None
            resp = client.post(
                "/api/v1/pipeline/runs/fanout",
                json={"ticker": "ZZZZ", "sector_id": "custom", "agent_ids": [999]},
            )
        assert resp.status_code == 404

    def test_trigger_run_missing_sector(self, client):
        resp = client.post(
            "/api/v1/pipeline/runs",
            json={"ticker": "NVDA"},  # sector_id missing
        )
        assert resp.status_code == 422

    def test_trigger_run_missing_ticker(self, client):
        resp = client.post(
            "/api/v1/pipeline/runs",
            json={"sector_id": "ai_semiconductors"},  # ticker missing
        )
        assert resp.status_code == 422

    def test_stream_run_not_found(self, client):
        with patch("app.api.routes.pipeline.signal_repo.get_run_for_user", new_callable=AsyncMock) as m:
            m.return_value = None
            resp = client.get("/api/v1/pipeline/runs/no-such-run/stream")
        assert resp.status_code == 404


# ══════════════════════════════════════════════════════════════════
# /api/v1/users
# ══════════════════════════════════════════════════════════════════

class TestUsersEndpoints:
    def _profile_dict(self, **overrides) -> dict:
        base = dict(
            id=1,
            email=TEST_USER,
            username=None,
            saved_sectors=[],
            preferences={},
            created_at="2025-01-01T00:00:00+00:00",
        )
        base.update(overrides)
        return base

    def test_get_me_returns_profile(self, client):
        profile = UserDetailSchema(**self._profile_dict())
        with patch("app.api.routes.users.user_repo.get_or_create", new_callable=AsyncMock) as m:
            m.return_value = profile
            resp = client.get("/api/v1/users/me")
        assert resp.status_code == 200
        assert resp.json()["email"] == TEST_USER
        # Confirm the dependency passed the mocked user email to the repo
        _, call_email = m.call_args.args
        assert call_email == TEST_USER

    def test_get_me_creates_profile_on_first_visit(self, client):
        """get_or_create is always called — it handles the first-visit case."""
        profile = UserDetailSchema(**self._profile_dict(username=None))
        with patch("app.api.routes.users.user_repo.get_or_create", new_callable=AsyncMock) as m:
            m.return_value = profile
            resp = client.get("/api/v1/users/me")
        assert resp.status_code == 200
        assert resp.json()["username"] is None

    def test_patch_me_updates_username(self, client):
        updated = UserDetailSchema(**self._profile_dict(username="Alice"))
        with (
            patch("app.api.routes.users.user_repo.get_or_create", new_callable=AsyncMock) as gm,
            patch("app.api.routes.users.user_repo.update_profile", new_callable=AsyncMock) as um,
        ):
            gm.return_value = UserDetailSchema(**self._profile_dict())
            um.return_value = updated
            resp = client.patch("/api/v1/users/me", json={"username": "Alice"})
        assert resp.status_code == 200
        assert resp.json()["username"] == "Alice"

    def test_patch_me_updates_saved_sectors(self, client):
        sectors = ["semiconductors", "ev_battery"]
        updated = UserDetailSchema(**self._profile_dict(saved_sectors=sectors))
        with (
            patch("app.api.routes.users.user_repo.get_or_create", new_callable=AsyncMock) as gm,
            patch("app.api.routes.users.user_repo.update_profile", new_callable=AsyncMock) as um,
        ):
            gm.return_value = UserDetailSchema(**self._profile_dict())
            um.return_value = updated
            resp = client.patch("/api/v1/users/me", json={"saved_sectors": sectors})
        assert resp.status_code == 200
        assert resp.json()["saved_sectors"] == sectors

    def test_patch_me_username_too_long(self, client):
        resp = client.patch("/api/v1/users/me", json={"username": "x" * 65})
        assert resp.status_code == 422


# ══════════════════════════════════════════════════════════════════
# /api/v1/sectors
# ══════════════════════════════════════════════════════════════════

class TestSectorsEndpoint:
    def test_list_sectors(self, client):
        resp = client.get("/api/v1/sectors")
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, list) and body, "expected non-empty sector list"
        first = body[0]
        # contract: id + name + tickers (list of ticker strings)
        assert {"id", "name", "tickers"}.issubset(first.keys())
        assert isinstance(first["tickers"], list)
        # the curated config is included
        assert any(s["id"] == "ai_semiconductors" for s in body)


# ══════════════════════════════════════════════════════════════════
# /api/v1/supply-chain
# ══════════════════════════════════════════════════════════════════

class TestSupplyChainEndpoint:
    def test_list_supply_chain_sectors(self, client):
        resp = client.get("/api/v1/supply-chain")
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, list) and body
        assert all({"id", "name"}.issubset(s.keys()) for s in body)
        assert any(s["id"] == "ai_semiconductors" for s in body)

    def test_get_sector_supply_chain(self, client):
        resp = client.get("/api/v1/supply-chain/ai_semiconductors")
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == "ai_semiconductors"
        assert isinstance(body["companies"], list) and body["companies"]
        assert isinstance(body["key_flows"], list)
        first_co = body["companies"][0]
        assert {"ticker", "name"}.issubset(first_co.keys())

    def test_get_sector_supply_chain_404(self, client):
        resp = client.get("/api/v1/supply-chain/does_not_exist")
        assert resp.status_code == 404


# ══════════════════════════════════════════════════════════════════
# /api/v1/system/health
# ══════════════════════════════════════════════════════════════════

class TestSystemHealth:
    def test_system_health(self, client):
        resp = client.get("/api/v1/system/health")
        assert resp.status_code == 200
        body = resp.json()
        for key in (
            "llm_provider",
            "llm_model",
            "langgraph_ok",
            "chromadb_docs",
            "fred_key_set",
            "sec_edgar_configured",
        ):
            assert key in body
        assert isinstance(body["chromadb_docs"], int)
        assert isinstance(body["langgraph_ok"], bool)


# ══════════════════════════════════════════════════════════════════
# /api/v1/watchlist  — "My Favourites"
# ══════════════════════════════════════════════════════════════════

class TestWatchlistEndpoints:
    def _item(self, **overrides) -> WatchlistItemSchema:
        base = dict(
            id=1,
            ticker="NVDA",
            notes=None,
            sector_id=None,
            added_at="2025-01-01T00:00:00+00:00",
        )
        base.update(overrides)
        return WatchlistItemSchema(**base)

    def test_list_watchlist(self, client):
        with patch("app.api.routes.watchlist.watchlist_repo.list_for_user", new_callable=AsyncMock) as m:
            m.return_value = [self._item(), self._item(id=2, ticker="AMD")]
            resp = client.get("/api/v1/watchlist")
        assert resp.status_code == 200
        body = resp.json()
        assert [row["ticker"] for row in body] == ["NVDA", "AMD"]
        # scoped to the authenticated user
        assert m.await_args.args[1] == TEST_USER

    def test_add_to_watchlist(self, client):
        with patch("app.api.routes.watchlist.watchlist_repo.add", new_callable=AsyncMock) as m:
            m.return_value = self._item(ticker="TSLA")
            resp = client.post("/api/v1/watchlist", json={"ticker": "tsla"})
        assert resp.status_code == 201
        assert resp.json()["ticker"] == "TSLA"

    def test_remove_from_watchlist(self, client):
        with patch("app.api.routes.watchlist.watchlist_repo.remove", new_callable=AsyncMock) as m:
            m.return_value = True
            resp = client.delete("/api/v1/watchlist/NVDA")
        assert resp.status_code == 204

    def test_remove_from_watchlist_not_found(self, client):
        with patch("app.api.routes.watchlist.watchlist_repo.remove", new_callable=AsyncMock) as m:
            m.return_value = False
            resp = client.delete("/api/v1/watchlist/NVDA")
        assert resp.status_code == 404

