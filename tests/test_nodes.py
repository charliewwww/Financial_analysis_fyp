"""
Tests for workflows/nodes.py — score_node + conditional edge functions.

score_node is pure math (no LLM, no I/O) so it's perfect for unit tests.
Conditional edges are pure logic on PipelineState fields.
"""

import pytest
from models.state import PipelineState, Article
from workflows.nodes import score_node, should_refetch, should_reanalyze, _truncate_prompt


# ═══════════════════════════════════════════════════════════════════
# score_node — Objective confidence scoring
# ═══════════════════════════════════════════════════════════════════

class TestScoreNode:
    """
    Score breakdown (max 10):
      - News coverage:     max 2.5  (9+: 2.5, 4-8: 1.5, 1-3: 0.5, 0: 0)
      - Price data:        max 2.0  (ratio of valid/total * 2)
      - Technicals:        max 1.5  (ratio of valid/total * 1.5)
      - SEC filings:       max 0.5  (any valid = 0.5)
      - Macro data:        max 1.5  (6 indicators = full, partial = 0.5)
      - Validation result: max 2.0  (PASSED=2, WARNING=1, FAILED=0)
    """

    def test_perfect_data(self, populated_state):
        """All data present + PASSED validation → high score."""
        populated_state.validation_status = "PASSED"
        result = score_node(populated_state)
        assert result.confidence_score >= 7.0
        assert result.confidence_score <= 10.0

    def test_no_data(self):
        """Empty state → very low score."""
        state = PipelineState()
        state.validation_status = ""
        result = score_node(state)
        assert result.confidence_score <= 2.0

    def test_failed_validation_hurts_score(self, populated_state):
        """FAILED validation should give 0 for that component."""
        populated_state.validation_status = "FAILED"
        score_failed = score_node(populated_state).confidence_score

        populated_state.confidence_score = 0.0  # Reset
        populated_state.validation_status = "PASSED"
        score_passed = score_node(populated_state).confidence_score

        assert score_passed - score_failed == pytest.approx(2.0, abs=0.1)

    def test_few_articles_lower_score(self, populated_state):
        """< 4 articles should get only 0.5 news coverage points."""
        populated_state.articles = populated_state.articles[:2]
        result = score_node(populated_state)
        # With 2 articles instead of 10, score should be ~2 points lower
        assert result.confidence_score < 9.0

    def test_no_macro_data(self, populated_state):
        """Missing macro data should reduce score."""
        populated_state.macro_data = {"_meta": {"api_status": "unavailable"}}
        result = score_node(populated_state)
        assert result.confidence_score >= 5.0  # Still decent with other data

    def test_score_capped_at_10(self):
        """Score must never exceed 10."""
        state = PipelineState()
        state.articles = [
            Article(title=f"A{i}", source="S", link="L",
                    published="2024-01-01", raw_summary="T")
            for i in range(50)
        ]
        state.prices = [{"ticker": "X", "price": 100}] * 10
        state.technicals = [{"ticker": "X", "rsi_14": 50}] * 10
        state.filings = [{"ticker": "X", "type": "10-K"}]
        state.macro_data = {"_meta": {"api_status": "ok", "indicators_fetched": 20}}
        state.validation_status = "PASSED"
        result = score_node(state)
        assert result.confidence_score <= 10.0

    def test_warning_validation_partial_credit(self, populated_state):
        """PASSED WITH WARNINGS gets 1.0 for validation component."""
        populated_state.validation_status = "PASSED WITH WARNINGS"
        result = score_node(populated_state)
        assert result.confidence_score >= 5.0


# ═══════════════════════════════════════════════════════════════════
# should_refetch — conditional edge after Reflect
# ═══════════════════════════════════════════════════════════════════

class TestShouldRefetch:
    def test_sufficient_proceeds(self):
        """Sufficient data → go to analyze."""
        state = PipelineState()
        state.data_sufficiency = "sufficient"
        assert should_refetch(state) == "analyze"

    def test_marginal_proceeds(self):
        """Marginal data → go to analyze (don't loop)."""
        state = PipelineState()
        state.data_sufficiency = "marginal"
        assert should_refetch(state) == "analyze"

    def test_insufficient_with_retries_loops(self):
        """Insufficient + retries available → loop back to fetch."""
        state = PipelineState()
        state.data_sufficiency = "insufficient"
        state.fetch_retry_count = 1
        state.max_fetch_retries = 2
        assert should_refetch(state) == "fetch"

    def test_insufficient_exhausted_retries(self):
        """Insufficient but no retries left → proceed to analyze anyway."""
        state = PipelineState()
        state.data_sufficiency = "insufficient"
        state.fetch_retry_count = 3
        state.max_fetch_retries = 2
        assert should_refetch(state) == "analyze"

    def test_edge_case_retry_equals_max(self):
        """When retry_count == max_retries, one more loop is allowed."""
        state = PipelineState()
        state.data_sufficiency = "insufficient"
        state.fetch_retry_count = 1
        state.max_fetch_retries = 1
        assert should_refetch(state) == "fetch"


# ═══════════════════════════════════════════════════════════════════
# should_reanalyze — conditional edge after Validate
# ═══════════════════════════════════════════════════════════════════

class TestShouldReanalyze:
    def test_passed_proceeds(self):
        """PASSED → go to score."""
        state = PipelineState()
        state.validation_status = "PASSED"
        assert should_reanalyze(state) == "score"

    def test_passed_with_warnings_proceeds(self):
        """PASSED WITH WARNINGS → go to score."""
        state = PipelineState()
        state.validation_status = "PASSED WITH WARNINGS"
        assert should_reanalyze(state) == "score"

    def test_failed_with_retries_loops(self):
        """FAILED + retries available → loop back to analyze."""
        state = PipelineState()
        state.validation_status = "FAILED"
        state.validation_retry_count = 1
        state.max_validation_retries = 2
        assert should_reanalyze(state) == "analyze"

    def test_failed_exhausted_retries(self):
        """FAILED but no retries left → proceed to score anyway."""
        state = PipelineState()
        state.validation_status = "FAILED"
        state.validation_retry_count = 3
        state.max_validation_retries = 2
        assert should_reanalyze(state) == "score"


# ═══════════════════════════════════════════════════════════════════
# _truncate_prompt — token budget management
# ═══════════════════════════════════════════════════════════════════

class TestTruncatePrompt:
    def test_short_prompt_unchanged(self):
        """Prompt under the limit should pass through untouched."""
        prompt = "Hello world"
        result = _truncate_prompt(prompt, max_chars=1000)
        assert result == prompt

    def test_long_prompt_truncated(self):
        """Prompt over the limit should be shortened."""
        prompt = "A" * 50000
        result = _truncate_prompt(prompt, max_chars=10000)
        assert len(result) < 50000
        assert "trimmed" in result.lower()

    def test_preserves_head_and_tail(self):
        """Truncation should keep start and end of prompt."""
        head = "HEAD_MARKER " * 100
        middle = "M" * 50000
        tail = " TAIL_MARKER" * 100
        prompt = head + middle + tail
        result = _truncate_prompt(prompt, max_chars=5000)
        assert "HEAD_MARKER" in result
        assert "TAIL_MARKER" in result

    def test_exact_limit_unchanged(self):
        """Prompt exactly at the limit should not be truncated."""
        prompt = "X" * 30000
        result = _truncate_prompt(prompt, max_chars=30000)
        assert result == prompt
