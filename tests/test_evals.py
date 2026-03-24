"""
Tests for the evals/ module — scoring, LLM judge, datasets, runner.

Tests cover:
  - Programmatic scorers produce correct values for known states
  - LLM judge response parsing handles edge cases
  - Evaluation dataset expectations pass/fail correctly
  - Score aggregation and reporting
  - Langfuse integration is skipped when disabled
"""

import pytest
import json
from unittest.mock import patch, MagicMock
from models.state import PipelineState, Article


# ── Helpers ──────────────────────────────────────────────────────

def _make_state(**overrides) -> PipelineState:
    """Create a test PipelineState with sensible defaults."""
    state = PipelineState.from_sector("ai_semiconductors", {
        "name": "AI & Semiconductors",
        "description": "Test sector",
        "tickers": ["NVDA", "TSM", "AMD"],
        "keywords": ["ai", "semiconductor"],
        "supply_chain_map": {},
    })
    state.articles = [
        Article(title=f"Article {i}", source=f"Source{i % 3}",
                link=f"https://example.com/{i}", published="2026-01-15",
                raw_summary=f"Summary {i}", relevance_tag="ticker:NVDA")
        for i in range(6)
    ]
    state.prices = [
        {"ticker": "NVDA", "price": 130.0, "market_cap": 3.2e12},
        {"ticker": "TSM", "price": 175.0, "market_cap": 900e9},
        {"ticker": "AMD", "price": 165.0, "market_cap": 265e9},
    ]
    state.technicals = [
        {"ticker": "NVDA", "rsi_14": 62.5},
        {"ticker": "TSM", "rsi_14": 55.0},
    ]
    state.filings = [{"ticker": "NVDA", "type": "10-K"}]
    state.macro_data = {
        "_meta": {"api_status": "ok", "indicators_fetched": 6},
    }
    state.analysis_text = (
        "## THESIS\nNVDA is dominant.\n"
        "## KEY DEVELOPMENTS\nEarnings beat.\n"
        "## DEEP CONTEXT\nAI boom continues.\n"
        "## MACRO\nFed holds rates.\n"
        "## SUPPLY CHAIN\nTSM key supplier.\n"
        "## RISK\nExport controls.\n"
        "## PRICE PREDICTIONS\n**NVDA**: BULLISH +5%\n"
        "## CONFIDENCE\n8/10\n"
        "[SOURCE: CNBC] NVDA beat earnings.\n"
    )
    state.validation_text = (
        "✅ NVDA price $130.0: verified\n"
        "✅ TSM price $175.0: verified\n"
        "❌ AMD market cap $300B: discrepancy (actual $265B)\n"
    )
    state.validation_status = "PASSED WITH WARNINGS"
    state.validation_retry_count = 0
    state.confidence_score = 7.5
    state.ai_predictions = [
        {"ticker": "NVDA", "direction": "BULLISH", "predicted_change": "+5%",
         "reasoning": "Strong demand", "key_risk": "Export controls"},
    ]
    state.total_duration_seconds = 45.0
    state.langfuse_trace_id = ""  # Langfuse disabled for tests

    for key, val in overrides.items():
        setattr(state, key, val)

    return state


# ═══════════════════════════════════════════════════════════════════
# SCORING TESTS
# ═══════════════════════════════════════════════════════════════════

class TestNumericalAccuracy:

    def test_with_verified_and_discrepancies(self):
        from evals.scoring import score_numerical_accuracy
        state = _make_state()
        score, comment = score_numerical_accuracy(state)
        # 2 verified, 1 discrepancy → 2/3 = 0.667
        assert abs(score - 0.667) < 0.01
        assert "2/3" in comment

    def test_no_validation_text(self):
        from evals.scoring import score_numerical_accuracy
        state = _make_state(validation_text="")
        score, comment = score_numerical_accuracy(state)
        assert score == 0.5  # Neutral when no claims
        assert "No numerical claims" in comment

    def test_all_verified(self):
        from evals.scoring import score_numerical_accuracy
        state = _make_state(validation_text="✅ NVDA: verified\n✅ TSM: verified\n")
        score, _ = score_numerical_accuracy(state)
        assert score == 1.0


class TestValidationQuality:

    def test_passed(self):
        from evals.scoring import score_validation_quality
        state = _make_state(validation_status="PASSED")
        score, _ = score_validation_quality(state)
        assert score == 1.0

    def test_passed_with_warnings(self):
        from evals.scoring import score_validation_quality
        state = _make_state(validation_status="PASSED WITH WARNINGS")
        score, _ = score_validation_quality(state)
        assert score == 0.5

    def test_failed(self):
        from evals.scoring import score_validation_quality
        state = _make_state(validation_status="FAILED")
        score, _ = score_validation_quality(state)
        assert score == 0.0

    def test_retry_penalty(self):
        from evals.scoring import score_validation_quality
        state = _make_state(validation_status="PASSED", validation_retry_count=2)
        score, _ = score_validation_quality(state)
        assert score == 0.8  # 1.0 - 2*0.1


class TestAnalysisCompleteness:

    def test_all_sections_present(self):
        from evals.scoring import score_analysis_completeness
        state = _make_state()
        score, comment = score_analysis_completeness(state)
        assert score == 1.0
        assert "8/8" in comment

    def test_missing_sections(self):
        from evals.scoring import score_analysis_completeness
        state = _make_state(analysis_text="## THESIS\nSome text only")
        score, comment = score_analysis_completeness(state)
        assert score < 1.0
        assert "missing" in comment.lower()

    def test_empty_analysis(self):
        from evals.scoring import score_analysis_completeness
        state = _make_state(analysis_text="")
        score, _ = score_analysis_completeness(state)
        assert score == 0.0


class TestSourceCoverage:

    def test_full_coverage(self):
        from evals.scoring import score_source_coverage
        state = _make_state()
        score, _ = score_source_coverage(state)
        assert score > 0.5  # Good data availability

    def test_no_data(self):
        from evals.scoring import score_source_coverage
        state = _make_state(
            articles=[], prices=[], technicals=[],
            filings=[], macro_data={},
        )
        score, _ = score_source_coverage(state)
        assert score == 0.0


class TestConfidenceCalibration:

    def test_well_calibrated(self):
        from evals.scoring import score_confidence_calibration
        # High confidence + good data → well calibrated
        state = _make_state(confidence_score=8.0)
        score, _ = score_confidence_calibration(state)
        assert score > 0.3

    def test_overconfident(self):
        from evals.scoring import score_confidence_calibration
        # High confidence + no data → poorly calibrated
        state = _make_state(
            confidence_score=10.0,
            articles=[], prices=[], technicals=[],
            filings=[], macro_data={},
        )
        score, _ = score_confidence_calibration(state)
        assert score < 0.3


class TestLatency:

    def test_fast(self):
        from evals.scoring import score_latency
        state = _make_state(total_duration_seconds=30.0)
        score, _ = score_latency(state)
        assert score == 1.0

    def test_slow(self):
        from evals.scoring import score_latency
        state = _make_state(total_duration_seconds=200.0)
        score, _ = score_latency(state)
        assert score < 0.5


class TestPredictionQuality:

    def test_complete_predictions(self):
        from evals.scoring import score_prediction_quality
        state = _make_state()
        score, _ = score_prediction_quality(state)
        assert score > 0.0

    def test_no_predictions(self):
        from evals.scoring import score_prediction_quality
        state = _make_state(ai_predictions=[])
        score, _ = score_prediction_quality(state)
        assert score == 0.0


class TestPushScores:

    @patch("config.settings.LANGFUSE_ENABLED", False)
    def test_computes_without_langfuse(self):
        """Scores should be computed even when Langfuse is disabled."""
        from evals.scoring import push_scores_to_langfuse
        state = _make_state()
        results = push_scores_to_langfuse(state)
        assert "overall" in results
        assert results["overall"] > 0
        assert "numerical_accuracy" in results
        assert "validation_quality" in results


# ═══════════════════════════════════════════════════════════════════
# LLM JUDGE TESTS
# ═══════════════════════════════════════════════════════════════════

class TestJudgeResponseParsing:

    def test_valid_json(self):
        from evals.llm_judge import _parse_judge_response
        response = json.dumps({
            "reasoning_depth": {"score": 4, "justification": "Good multi-step reasoning"},
            "supply_chain_insight": {"score": 3, "justification": "Some depth"},
            "evidence_grounding": {"score": 5, "justification": "Well cited"},
            "risk_awareness": {"score": 2, "justification": "Generic risks"},
            "actionability": {"score": 4, "justification": "Clear thesis"},
            "overall_comment": "Solid analysis overall.",
        })
        result = _parse_judge_response(response)
        assert result is not None
        assert result["reasoning_depth"]["score"] == 4
        assert result["risk_awareness"]["score"] == 2

    def test_markdown_wrapped_json(self):
        from evals.llm_judge import _parse_judge_response
        response = '```json\n{"reasoning_depth": {"score": 3, "justification": "ok"}, "supply_chain_insight": {"score": 3, "justification": "ok"}, "evidence_grounding": {"score": 3, "justification": "ok"}, "risk_awareness": {"score": 3, "justification": "ok"}, "actionability": {"score": 3, "justification": "ok"}}\n```'
        result = _parse_judge_response(response)
        assert result is not None
        assert result["reasoning_depth"]["score"] == 3

    def test_missing_dimensions_filled(self):
        from evals.llm_judge import _parse_judge_response
        response = json.dumps({
            "reasoning_depth": {"score": 4, "justification": "Good"},
        })
        result = _parse_judge_response(response)
        assert result is not None
        # Missing dimensions should be filled with defaults
        assert result["supply_chain_insight"]["score"] == 3

    def test_empty_response(self):
        from evals.llm_judge import _parse_judge_response
        assert _parse_judge_response("") is None
        assert _parse_judge_response("No JSON here") is None

    def test_json_with_trailing_text(self):
        from evals.llm_judge import _parse_judge_response
        response = 'Here is my evaluation:\n{"reasoning_depth": {"score": 5, "justification": "x"}, "supply_chain_insight": {"score": 4, "justification": "x"}, "evidence_grounding": {"score": 4, "justification": "x"}, "risk_awareness": {"score": 3, "justification": "x"}, "actionability": {"score": 4, "justification": "x"}}\nThat is my assessment.'
        result = _parse_judge_response(response)
        assert result is not None
        assert result["reasoning_depth"]["score"] == 5


class TestLLMJudge:

    @patch("config.settings.LANGFUSE_ENABLED", False)
    @patch("agents.llm_client.call_llm_fast")
    def test_judge_runs_and_returns_normalized_scores(self, mock_llm):
        from evals.llm_judge import run_llm_judge
        mock_llm.return_value = json.dumps({
            "reasoning_depth": {"score": 4, "justification": "Good"},
            "supply_chain_insight": {"score": 3, "justification": "Ok"},
            "evidence_grounding": {"score": 5, "justification": "Great"},
            "risk_awareness": {"score": 2, "justification": "Weak"},
            "actionability": {"score": 4, "justification": "Clear"},
            "overall_comment": "Solid.",
        })

        state = _make_state()
        scores = run_llm_judge(state)

        assert "judge_reasoning_depth" in scores
        assert scores["judge_reasoning_depth"] == 0.75  # (4-1)/4
        assert scores["judge_risk_awareness"] == 0.25   # (2-1)/4
        assert "judge_overall" in scores
        mock_llm.assert_called_once()

    @patch("config.settings.LANGFUSE_ENABLED", False)
    @patch("agents.llm_client.call_llm_fast", side_effect=Exception("LLM down"))
    def test_judge_handles_llm_failure(self, mock_llm):
        from evals.llm_judge import run_llm_judge
        state = _make_state()
        scores = run_llm_judge(state)
        assert scores == {}


# ═══════════════════════════════════════════════════════════════════
# DATASETS TESTS
# ═══════════════════════════════════════════════════════════════════

class TestEvalDatasets:

    def test_default_dataset_structure(self):
        from evals.datasets import get_default_dataset
        cases = get_default_dataset()
        assert len(cases) >= 2
        for case in cases:
            assert case.case_id
            assert case.sector_id
            assert case.sector_config.get("name")
            assert case.sector_config.get("tickers")

    def test_evaluate_result_all_pass(self):
        from evals.datasets import get_default_dataset, evaluate_result
        case = get_default_dataset()[1]  # completeness_check — less strict
        state = _make_state(
            confidence_score=5.0,
            validation_status="PASSED",
            pipeline_status="completed",
        )

        result = evaluate_result(case, state, {"overall": 0.7}, {}, 30.0)
        assert result.passed
        assert all(result.checks.values())

    def test_evaluate_result_low_confidence_fails(self):
        from evals.datasets import get_default_dataset, evaluate_result
        case = get_default_dataset()[0]  # high_data — requires confidence >= 5.0
        state = _make_state(
            confidence_score=1.0,  # Below minimum
            pipeline_status="completed",
        )

        result = evaluate_result(case, state, {}, {}, 30.0)
        assert not result.passed
        assert not result.checks["confidence_in_range"]


# ═══════════════════════════════════════════════════════════════════
# RUNNER TESTS
# ═══════════════════════════════════════════════════════════════════

class TestEvalRunner:

    def test_format_eval_report(self):
        from evals.runner import format_eval_report
        from evals.datasets import EvalResult

        results = [
            EvalResult(
                case_id="test_case_1",
                passed=True,
                checks={"confidence_in_range": True, "pipeline_completed": True},
                details={"confidence_in_range": "7.5", "pipeline_completed": "completed"},
                scores={"overall": 0.75, "numerical_accuracy": 0.8},
                judge_scores={"judge_overall": 0.6},
                duration_seconds=30.0,
            ),
        ]

        report = format_eval_report(results)
        assert "Evaluation Report" in report
        assert "test_case_1" in report
        assert "PASS" in report
        assert "0.75" in report


# ═══════════════════════════════════════════════════════════════════
# PREDICTION ACCURACY SCORING
# ═══════════════════════════════════════════════════════════════════

class TestPredictionAccuracy:

    @patch("config.settings.LANGFUSE_ENABLED", False)
    def test_correct_predictions(self):
        from evals.scoring import score_prediction_accuracy
        predictions = [
            {"ticker": "NVDA", "ai_direction": "BULLISH", "price_at_report": 100.0},
            {"ticker": "AMD", "ai_direction": "BEARISH", "price_at_report": 100.0},
        ]
        actuals = {"NVDA": 110.0, "AMD": 90.0}  # Both correct

        score, comment = score_prediction_accuracy("trace123", predictions, actuals)
        assert score == 1.0
        assert "2/2" in comment

    @patch("config.settings.LANGFUSE_ENABLED", False)
    def test_mixed_predictions(self):
        from evals.scoring import score_prediction_accuracy
        predictions = [
            {"ticker": "NVDA", "ai_direction": "BULLISH", "price_at_report": 100.0},
            {"ticker": "AMD", "ai_direction": "BULLISH", "price_at_report": 100.0},
        ]
        actuals = {"NVDA": 110.0, "AMD": 90.0}  # NVDA correct, AMD wrong

        score, comment = score_prediction_accuracy("trace123", predictions, actuals)
        assert score == 0.5
        assert "1/2" in comment

    @patch("config.settings.LANGFUSE_ENABLED", False)
    def test_no_predictions(self):
        from evals.scoring import score_prediction_accuracy
        score, _ = score_prediction_accuracy("trace123", [], {})
        assert score == 0.5  # Neutral
