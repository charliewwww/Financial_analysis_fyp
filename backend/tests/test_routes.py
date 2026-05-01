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
from fastapi.testclient import TestClient

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
        patch("app.main.dispose_engine", new_callable=AsyncMock),
    ):
        # Import here so patch is active during module-level side effects
        from app.core.auth import get_current_user
        from app.db.engine import get_db
        from app.main import app

        # Override FastAPI's DB dependency with a no-op mock
        async def _mock_db():
            yield AsyncMock()

        # Override auth so tests don't need a Cloudflare header
        async def _mock_user():
            return TEST_USER

        app.dependency_overrides[get_db] = _mock_db
        app.dependency_overrides[get_current_user] = _mock_user

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
# /api/v1/pipeline
# ══════════════════════════════════════════════════════════════════

class TestPipelineEndpoints:
    def test_list_runs_empty(self, client):
        with patch("app.api.routes.pipeline.signal_repo.list_runs", new_callable=AsyncMock) as m:
            m.return_value = ([], 0)
            resp = client.get("/api/v1/pipeline/runs")
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    def test_get_run_not_found(self, client):
        with patch("app.api.routes.pipeline.signal_repo.get_run", new_callable=AsyncMock) as m:
            m.return_value = None
            resp = client.get("/api/v1/pipeline/runs/no-such-run")
        assert resp.status_code == 404

    def test_get_run_found(self, client):
        run = PipelineRunSchema(
            id=1, run_id="abc-123", ticker="NVDA",
            sector_id="ai_semiconductors", status="completed",
            created_at="2025-01-01T00:00:00+00:00",
        )
        with patch("app.api.routes.pipeline.signal_repo.get_run", new_callable=AsyncMock) as m:
            m.return_value = run
            resp = client.get("/api/v1/pipeline/runs/abc-123")
        assert resp.status_code == 200
        assert resp.json()["status"] == "completed"

    def test_trigger_run_returns_202(self, client):
        with (
            patch("app.api.routes.pipeline.signal_repo.create_run", new_callable=AsyncMock) as crm,
            patch("app.api.routes.pipeline.runner.launch_run", new_callable=AsyncMock) as lrm,
        ):
            crm.return_value = 1
            lrm.return_value = None
            resp = client.post(
                "/api/v1/pipeline/runs",
                json={"ticker": "NVDA", "sector_id": "ai_semiconductors"},
            )
        assert resp.status_code == 202
        body = resp.json()
        assert "run_id" in body
        assert body["status"] == "pending"

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
        with patch("app.api.routes.pipeline.signal_repo.get_run", new_callable=AsyncMock) as m:
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

