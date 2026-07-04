"""
Tests for backend Pydantic schemas:
  - app.schemas.common
  - app.schemas.analysis
  - app.schemas.pipeline
  - app.schemas.reports
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.agents import AgentCreateRequest
from app.schemas.analysis import (
    AIPredictionSchema,
    AnomalyAlertSchema,
    ArticleSchema,
    NodeExecutionSchema,
    NumericalClaimSchema,
    SignalCardSchema,
    SignalChatCitation,
    SignalChatRequest,
    SignalChatResponse,
    SignalSourceSchema,
    SupplyChainImpactSchema,
)
from app.schemas.common import ErrorDetail, ErrorResponse, HealthResponse, PaginatedResponse
from app.schemas.pipeline import (
    PipelineRunSchema,
    RunFanoutRequest,
    RunFanoutResponse,
    RunRequest,
    RunSectorFanoutRequest,
    RunSummary,
    SSEEvent,
)
from app.schemas.reports import AccuracyStats, PredictionSchema, ReportDetail, ReportSummary, SignalTypeBreakdown


# ══════════════════════════════════════════════════════════════════
# agents.py
# ══════════════════════════════════════════════════════════════════

class TestAgentCreateRequest:
    def test_valid_custom_skill(self):
        req = AgentCreateRequest(
            name=" Options Flow Analyst ",
            skill_content="Focus on options flow, implied volatility, dealer gamma, and positioning changes.",
        )
        assert req.name == "Options Flow Analyst"
        assert req.skill_name is None
        assert req.skill_type == "domain"

    def test_skill_content_must_be_substantial(self):
        with pytest.raises(ValidationError):
            AgentCreateRequest(name="Tiny Skill", skill_content="too short")


# ══════════════════════════════════════════════════════════════════
# common.py
# ══════════════════════════════════════════════════════════════════

class TestHealthResponse:
    def test_ok(self):
        h = HealthResponse(status="ok", version="0.1.0")
        assert h.status == "ok"
        assert h.version == "0.1.0"

    def test_defaults_empty_version(self):
        h = HealthResponse(status="ok")
        assert h.version == ""


class TestPaginatedResponse:
    def test_generic_items(self):
        p = PaginatedResponse[str](
            items=["a", "b"],
            total=10,
            page=1,
            page_size=2,
            has_next=True,
        )
        assert len(p.items) == 2
        assert p.has_next is True

    def test_empty_page(self):
        p = PaginatedResponse[int](items=[], total=0, page=1, page_size=20, has_next=False)
        assert p.total == 0
        assert p.items == []

    def test_error_detail_and_response(self):
        err = ErrorResponse(error=ErrorDetail(code="NOT_FOUND", message="missing"))
        assert err.error.code == "NOT_FOUND"


# ══════════════════════════════════════════════════════════════════
# analysis.py
# ══════════════════════════════════════════════════════════════════

class TestNodeExecutionSchema:
    def test_minimal(self):
        n = NodeExecutionSchema(node_name="fetch")
        assert n.status == "pending"
        assert n.duration_seconds == 0.0

    def test_all_fields(self):
        n = NodeExecutionSchema(
            node_name="analyze",
            started_at="2025-01-01T00:00:00",
            finished_at="2025-01-01T00:00:05",
            duration_seconds=5.0,
            status="completed",
            llm_model="gpt-4",
            llm_prompt_tokens=1000,
            llm_completion_tokens=250,
            decision="sufficient",
        )
        assert n.duration_seconds == 5.0
        assert n.decision == "sufficient"

    def test_invalid_status_rejected(self):
        with pytest.raises(ValidationError):
            NodeExecutionSchema(node_name="fetch", status="unknown_status")


class TestArticleSchema:
    def test_required_fields(self):
        a = ArticleSchema(
            title="T", source="S", link="http://x.com",
            published="2025-01-01", raw_summary="summary",
        )
        assert a.used_in_analysis is True

    def test_defaults(self):
        a = ArticleSchema(
            title="T", source="S", link="L",
            published="2025-01-01", raw_summary="R",
        )
        assert a.relevance_score == 0.0
        assert a.condensed_summary == ""


class TestSignalCardSchema:
    def _minimal(self, **overrides) -> dict:
        base = dict(
            id=1,
            ticker="NVDA",
            signal="BULLISH",
            conviction=4,
            one_line="Strong buy on AI demand",
            confidence=0.8,
            created_at="2025-01-15T12:00:00+00:00",
            status="active",
        )
        base.update(overrides)
        return base

    def test_minimal_valid(self):
        card = SignalCardSchema(**self._minimal())
        assert card.ticker == "NVDA"
        assert card.signal == "BULLISH"

    def test_conviction_range(self):
        """conviction must be 1–5."""
        with pytest.raises(ValidationError):
            SignalCardSchema(**self._minimal(conviction=0))
        with pytest.raises(ValidationError):
            SignalCardSchema(**self._minimal(conviction=6))

    def test_confidence_range(self):
        """confidence must be 0.0–1.0."""
        with pytest.raises(ValidationError):
            SignalCardSchema(**self._minimal(confidence=1.5))
        with pytest.raises(ValidationError):
            SignalCardSchema(**self._minimal(confidence=-0.1))

    def test_invalid_signal_rejected(self):
        with pytest.raises(ValidationError):
            SignalCardSchema(**self._minimal(signal="MAYBE"))

    def test_nullable_fields_default_to_none(self):
        card = SignalCardSchema(**self._minimal())
        assert card.run_id is None
        assert card.agent_id is None
        assert card.signal_type is None

    def test_nested_sub_schemas(self):
        card = SignalCardSchema(**self._minimal(
            numerical_claims=[{"claim": "Revenue +12%", "verified": True, "source": "10-K"}],
            sources=[{"url": "http://x.com", "title": "Reuters", "domain": "reuters.com"}],
            supply_chain_impact=[{"ticker": "TSM", "direction": "▲", "reason": "demand surge"}],
        ))
        assert len(card.numerical_claims) == 1
        assert card.numerical_claims[0].verified is True
        assert card.sources[0].domain == "reuters.com"
        assert card.supply_chain_impact[0].direction == "▲"


class TestNumericalClaimSchema:
    def test_required_fields(self):
        c = NumericalClaimSchema(claim="Revenue +12%", verified=True, source="10-K")
        assert c.verified is True

    def test_source_defaults_empty(self):
        c = NumericalClaimSchema(claim="X", verified=False)
        assert c.source == ""


class TestSupplyChainImpactSchema:
    def test_directions(self):
        for d in ("▲", "▼", "◆"):
            s = SupplyChainImpactSchema(ticker="TSM", direction=d, reason="reason")
            assert s.direction == d


class TestSignalChatSchemas:
    def test_request_minimal(self):
        req = SignalChatRequest(question="What changed?")
        assert req.question == "What changed?"
        assert req.history == []

    def test_request_accepts_history_and_context(self):
        req = SignalChatRequest(
            question="Why is recommendation locked?",
            context="Recommendation allowed: no",
            history=[{"role": "user", "content": "What changed?"}],
        )
        assert req.context == "Recommendation allowed: no"
        assert req.history[0].role == "user"

    def test_response_citations(self):
        citation = SignalChatCitation(
            label="source: reuters.com",
            source_type="source",
            source="reuters.com",
            url="https://example.com",
            quote="Demand rose.",
        )
        res = SignalChatResponse(answer="Demand rose.", citations=[citation], limitations=[])
        assert res.citations[0].label == "source: reuters.com"


# ══════════════════════════════════════════════════════════════════
# pipeline.py
# ══════════════════════════════════════════════════════════════════

class TestRunRequest:
    def test_valid(self):
        r = RunRequest(ticker="NVDA", sector_id="ai_semiconductors")
        assert r.ticker == "NVDA"
        assert r.agent_id is None
        assert r.max_fetch_retries == 1

    def test_retries_clamped(self):
        with pytest.raises(ValidationError):
            RunRequest(ticker="NVDA", sector_id="ai", max_fetch_retries=5)

    def test_agent_id_optional(self):
        r = RunRequest(ticker="NVDA", sector_id="ai", agent_id=42)
        assert r.agent_id == 42


class TestRunFanoutRequest:
    def test_sector_id_optional(self):
        r = RunFanoutRequest(ticker="NVDA")
        assert r.ticker == "NVDA"
        assert r.sector_id is None
        assert r.agent_ids is None

    def test_accepts_agent_ids(self):
        r = RunFanoutRequest(ticker="NVDA", agent_ids=[1, 2, 3])
        assert r.agent_ids == [1, 2, 3]

    def test_agent_ids_must_not_be_empty(self):
        with pytest.raises(ValidationError):
            RunFanoutRequest(ticker="NVDA", agent_ids=[])

    def test_response_shape(self):
        r = RunFanoutResponse(
            ticker="NVDA",
            sector_id="ai_semiconductors",
            runs=[{"run_id": "r-1", "agent_id": 1, "agent_name": "Supply Chain Analyst"}],
        )
        assert r.runs[0].status == "pending"


class TestRunSectorFanoutRequest:
    def test_valid_sector_request(self):
        r = RunSectorFanoutRequest(sector_id="ai_semiconductors", tickers=["NVDA", "AMD"])
        assert r.sector_id == "ai_semiconductors"
        assert r.tickers == ["NVDA", "AMD"]
        assert r.agent_ids is None

    def test_tickers_must_not_be_empty(self):
        with pytest.raises(ValidationError):
            RunSectorFanoutRequest(sector_id="ai_semiconductors", tickers=[])


class TestPipelineRunSchema:
    def test_minimal(self):
        run = PipelineRunSchema(
            id=1,
            run_id="abc-123",
            ticker="NVDA",
            sector_id="ai_semiconductors",
            status="pending",
            created_at="2025-01-01T00:00:00+00:00",
        )
        assert run.status == "pending"
        assert run.signal_card_id is None
        assert run.node_executions == []

    def test_invalid_status(self):
        with pytest.raises(ValidationError):
            PipelineRunSchema(
                id=1, run_id="x", ticker="T", sector_id="s",
                status="queued", created_at="2025-01-01",
            )


class TestSSEEvent:
    def test_heartbeat_serialises(self):
        evt = SSEEvent(event="heartbeat", run_id="abc-123")
        j = evt.model_dump_json()
        assert '"heartbeat"' in j
        assert "abc-123" in j

    def test_pipeline_completed(self):
        evt = SSEEvent(
            event="pipeline_completed",
            run_id="abc",
            data={"signal_card_id": 5, "confidence": 0.9},
        )
        assert evt.data["signal_card_id"] == 5

    def test_invalid_event_rejected(self):
        with pytest.raises(ValidationError):
            SSEEvent(event="unknown_event", run_id="x")


# ══════════════════════════════════════════════════════════════════
# reports.py
# ══════════════════════════════════════════════════════════════════

class TestPredictionSchema:
    def test_both_fks_optional(self):
        """Both signal_card_id and report_id must be nullable."""
        p = PredictionSchema(id=1, ticker="NVDA")
        assert p.signal_card_id is None
        assert p.report_id is None

    def test_signal_card_path(self):
        p = PredictionSchema(id=1, ticker="NVDA", signal_card_id=5)
        assert p.signal_card_id == 5
        assert p.report_id is None

    def test_report_path(self):
        p = PredictionSchema(id=1, ticker="NVDA", report_id=10)
        assert p.report_id == 10
        assert p.signal_card_id is None

    def test_unchecked_fields_null(self):
        p = PredictionSchema(id=1, ticker="AAPL")
        assert p.price_1w_later is None
        assert p.prediction_correct is None
        assert p.checked_at is None


class TestReportSummary:
    def test_defaults(self):
        r = ReportSummary(
            id=1, sector_id="ai", sector_name="AI",
            created_at="2025-01-01",
        )
        assert r.status == "active"
        assert r.news_used == 0


class TestAccuracyStats:
    def test_empty(self):
        a = AccuracyStats()
        assert a.total == 0
        assert a.direction_accuracy_pct is None

    def test_with_data(self):
        a = AccuracyStats(
            total=10, checked=8, unchecked=2,
            direction_correct=6, direction_incorrect=2,
            direction_accuracy_pct=75.0,
            avg_absolute_error_pct=2.5,
            by_signal_type={"BULLISH": SignalTypeBreakdown(total=5, correct=4, accuracy_pct=80.0)},
        )
        assert a.direction_accuracy_pct == 75.0
        assert a.by_signal_type["BULLISH"].accuracy_pct == 80.0


class TestSignalTypeBreakdown:
    def test_defaults(self):
        s = SignalTypeBreakdown()
        assert s.total == 0
        assert s.accuracy_pct is None

    def test_with_values(self):
        s = SignalTypeBreakdown(total=4, correct=3, accuracy_pct=75.0)
        assert s.correct == 3
