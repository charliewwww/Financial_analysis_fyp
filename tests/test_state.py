"""
Tests for models/state.py — PipelineState, Article, NodeExecution, NodeRunner.

These are the backbone dataclasses of the entire pipeline.
Tests are pure (no I/O, no mocks needed).
"""

import json
import time
import pytest
from models.state import PipelineState, Article, NodeExecution, NodeRunner


# ═══════════════════════════════════════════════════════════════════
# Article
# ═══════════════════════════════════════════════════════════════════

class TestArticle:
    def test_defaults(self):
        a = Article(title="X", source="S", link="L", published="2024-01-01",
                    raw_summary="text")
        assert a.condensed_summary == ""
        assert a.relevance_tag == ""
        assert a.relevance_score == 0.0
        assert a.used_in_analysis is True

    def test_to_dict(self):
        a = Article(title="X", source="S", link="L", published="2024-01-01",
                    raw_summary="text")
        d = a.to_dict()
        assert isinstance(d, dict)
        assert d["title"] == "X"
        assert "condensed_summary" in d


# ═══════════════════════════════════════════════════════════════════
# NodeExecution
# ═══════════════════════════════════════════════════════════════════

class TestNodeExecution:
    def test_defaults(self):
        ne = NodeExecution(node_name="fetch_news")
        assert ne.status == "pending"
        assert ne.llm_prompt_tokens == 0
        assert ne.error is None

    def test_to_dict(self):
        ne = NodeExecution(node_name="test", decision="sufficient")
        d = ne.to_dict()
        assert d["decision"] == "sufficient"


# ═══════════════════════════════════════════════════════════════════
# PipelineState
# ═══════════════════════════════════════════════════════════════════

class TestPipelineState:
    def test_from_sector(self):
        sector = {
            "name": "AI & Semiconductors",
            "description": "Chips and AI",
            "tickers": ["NVDA", "TSM"],
            "keywords": ["ai", "gpu"],
            "supply_chain_map": {"NVDA": {"role": "designer"}},
        }
        state = PipelineState.from_sector("ai_semiconductors", sector)
        assert state.sector_id == "ai_semiconductors"
        assert state.sector_name == "AI & Semiconductors"
        assert state.sector_tickers == ["NVDA", "TSM"]
        assert len(state.run_id) == 8
        assert state.pipeline_status == "pending"
        assert state.confidence_score == 0.0

    def test_from_sector_missing_optionals(self):
        """from_sector should not crash if optional keys are missing."""
        state = PipelineState.from_sector("test", {"name": "Test"})
        assert state.sector_tickers == []
        assert state.sector_supply_chain_map == {}

    def test_to_dict_round_trip(self):
        state = PipelineState(sector_id="test", sector_name="Test Sector")
        state.articles = [
            Article(title="A", source="S", link="L",
                    published="2024-01-01", raw_summary="T"),
        ]
        d = state.to_dict()
        assert isinstance(d, dict)
        assert len(d["articles"]) == 1
        assert d["articles"][0]["title"] == "A"

    def test_to_json(self):
        state = PipelineState(sector_id="test")
        j = state.to_json()
        parsed = json.loads(j)
        assert parsed["sector_id"] == "test"

    def test_default_retry_limits(self):
        state = PipelineState()
        assert state.max_fetch_retries == 1
        assert state.max_validation_retries == 1
        assert state.fetch_retry_count == 0
        assert state.validation_retry_count == 0


# ═══════════════════════════════════════════════════════════════════
# NodeRunner (context manager)
# ═══════════════════════════════════════════════════════════════════

class TestNodeRunner:
    def test_basic_timing(self):
        state = PipelineState()
        with NodeRunner(state, "test_node") as node:
            time.sleep(0.05)
            node.decision = "ok"

        assert len(state.node_executions) == 1
        ne = state.node_executions[0]
        assert ne.node_name == "test_node"
        assert ne.status == "completed"
        assert ne.decision == "ok"
        assert ne.duration_seconds >= 0.04  # Allow small timing variance

    def test_exception_handling(self):
        state = PipelineState()
        with pytest.raises(ValueError):
            with NodeRunner(state, "fail_node") as node:
                raise ValueError("boom")

        assert len(state.node_executions) == 1
        ne = state.node_executions[0]
        assert ne.status == "failed"
        assert "boom" in ne.error

    def test_token_accumulation(self):
        state = PipelineState()
        with NodeRunner(state, "node_a") as node:
            node.llm_prompt_tokens = 100
            node.llm_completion_tokens = 50

        with NodeRunner(state, "node_b") as node:
            node.llm_prompt_tokens = 200
            node.llm_completion_tokens = 75

        assert state.total_llm_prompt_tokens == 300
        assert state.total_llm_completion_tokens == 125
