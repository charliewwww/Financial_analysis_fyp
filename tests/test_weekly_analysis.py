"""
End-to-end tests for workflows/weekly_analysis.py.

These tests exercise the full LangGraph pipeline with all external
dependencies mocked (network calls, LLM, database, vector DB).
They verify:
  - Happy-path: fetch → summarize → reflect → analyze → validate → score → save
  - Refetch loop: reflect returns insufficient → pipeline loops back to fetch
  - Reanalyze loop: validate returns FAILED → pipeline loops back to analyze
  - Self-correction feedback injection on re-analyze
  - check_old_predictions() logic
  - run_weekly_analysis() with LLM health check failure
  - Progress callback invocations
"""

import pytest
from unittest.mock import patch, MagicMock, call
from datetime import datetime, timezone, timedelta

from models.state import PipelineState, Article
from workflows.weekly_analysis import (
    run_sector_analysis,
    run_weekly_analysis,
    check_old_predictions,
    _run_sector_graph,
    _build_sector_graph,
    _state_to_result,
)


# ── Shared test data ─────────────────────────────────────────────

_SECTOR_ID = "ai_semiconductors"
_SECTOR = {
    "name": "AI & Semiconductors",
    "description": "Companies designing GPUs and AI chips",
    "tickers": ["NVDA", "TSM", "AMD"],
    "keywords": ["ai", "semiconductor", "gpu"],
    "supply_chain_map": {"NVDA": {"role": "GPU designer"}},
}

_FAKE_ARTICLES = [
    {
        "title": "NVIDIA beats earnings",
        "source": "CNBC",
        "link": "https://example.com/1",
        "published": "2026-01-15",
        "summary": "NVIDIA reported Q4 revenue of $22B.",
        "relevance": "ticker:NVDA",
    },
    {
        "title": "AMD announces new chip",
        "source": "Reuters",
        "link": "https://example.com/2",
        "published": "2026-01-14",
        "summary": "AMD launches MI350 AI accelerator.",
        "relevance": "ticker:AMD",
    },
]

_FAKE_PRICES = [
    {"ticker": "NVDA", "price": 130.0, "market_cap": 3.2e12},
    {"ticker": "TSM", "price": 175.0, "market_cap": 900e9},
    {"ticker": "AMD", "price": 165.0, "market_cap": 265e9},
]

_FAKE_TECHNICALS = [
    {"ticker": "NVDA", "rsi_14": 62.5, "macd": 1.2},
    {"ticker": "TSM", "rsi_14": 55.0, "macd": 0.8},
]

_FAKE_FILINGS = [
    {"ticker": "NVDA", "type": "10-K", "date": "2026-02-21", "text_total_chars": 5000},
]

_FAKE_MACRO = {
    "_meta": {"api_status": "ok", "indicators_fetched": 6, "source": "FRED",
              "fetched_at": "2026-01-01T00:00:00"},
    "fed_funds_rate": {
        "value": 5.25, "name": "Federal Funds Rate", "unit": "%",
        "date": "2026-01-01", "trend": "stable", "change": 0.0,
        "interpretation": {"stable": "Rates unchanged."},
    },
}


# ── Helpers to build mock side effects ────────────────────────────

def _make_llm_responses(sufficiency="sufficient", validation="PASSED"):
    """
    Return a list of LLM responses in the order they are called:
      1. summarize_node (call_llm_fast)
      2. reflect_node  (call_llm_fast)
      3. analyze_node  (call_llm)
      4. validate_node (call_llm)
    """
    summarize = "• NVIDIA beat earnings with $22B revenue\n• AMD launches MI350"
    reflect = f"VERDICT: {sufficiency.upper()}\nGAPS: None significant.\nREASONING: Good coverage."
    analyze = (
        "## AI & Semiconductors Analysis\n\n"
        "NVIDIA dominates the AI chip market.\n\n"
        "[SOURCE: CNBC] NVDA beat earnings.\n\n"
        "## PRICE PREDICTIONS\n"
        "**NVDA**: BULLISH | Expected move: +3% to +7%\n"
        "- Reasoning: Strong data-center demand\n"
        "- Key risk: Export controls\n"
    )
    validate = (
        f"STATUS: {validation}\n"
        "The analysis is well-reasoned with source citations.\n"
    )
    if validation == "FAILED":
        validate += "⚠️ DISCREPANCY: Made up revenue number.\n"
    return summarize, reflect, analyze, validate


# ═══════════════════════════════════════════════════════════════════
# Patches applied to all E2E tests — isolate from real I/O
# ═══════════════════════════════════════════════════════════════════

@pytest.fixture
def mock_externals():
    """Patch all external dependencies for a clean E2E test."""
    with (
        patch("workflows.nodes.fetch_news_for_sector", return_value=_FAKE_ARTICLES) as m_news,
        patch("workflows.nodes.get_sector_prices", return_value=_FAKE_PRICES) as m_prices,
        patch("workflows.nodes.compute_sector_technicals", return_value=_FAKE_TECHNICALS) as m_tech,
        patch("workflows.nodes.get_filings_with_text", return_value=_FAKE_FILINGS) as m_filings,
        patch("workflows.nodes.get_macro_snapshot", return_value=_FAKE_MACRO) as m_macro,
        patch("workflows.nodes.rag_is_available", return_value=False),
        patch("workflows.nodes.rag_ingest_articles"),
        patch("workflows.nodes.rag_ingest_filings"),
        patch("workflows.nodes.rag_ingest_analysis"),
        patch("workflows.nodes.save_report_from_state", return_value=42) as m_save,
        patch("database.reports_db.purge_old_reports", return_value=[]),
        patch("workflows.weekly_analysis.LANGFUSE_ENABLED", False),
        # Invalidate the cached compiled graph so each test gets a fresh one
        patch("workflows.weekly_analysis._compiled_graph", None),
    ):
        yield {
            "news": m_news,
            "prices": m_prices,
            "tech": m_tech,
            "filings": m_filings,
            "macro": m_macro,
            "save": m_save,
        }


# ═══════════════════════════════════════════════════════════════════
# E2E: Happy path — full pipeline, no loops
# ═══════════════════════════════════════════════════════════════════

class TestE2EHappyPath:

    @patch("workflows.nodes.call_llm")
    @patch("workflows.nodes.call_llm_fast")
    def test_full_pipeline_happy_path(self, mock_llm_fast, mock_llm, mock_externals):
        """Pipeline runs fetch→summarize→reflect→analyze→validate→score→save
        with no loops when data is sufficient and validation passes."""
        summarize, reflect, analyze, validate = _make_llm_responses()
        mock_llm_fast.side_effect = [summarize, reflect]
        mock_llm.side_effect = [analyze, validate]

        state = _run_sector_graph(_SECTOR_ID, _SECTOR)

        # Verify all nodes ran
        node_names = [n.node_name for n in state.node_executions]
        # fetch_node creates multiple sub-nodes; check that key pipeline nodes exist
        assert "summarize" in node_names
        assert "reflect" in node_names
        assert "analyze" in node_names
        assert "validate_numbers" in node_names
        assert "validate_reasoning" in node_names
        assert "score" in node_names
        assert "save_to_db" in node_names

        # Verify final state
        assert state.pipeline_status == "completed"
        assert state.report_id == 42
        assert state.confidence_score > 0
        assert "NVIDIA" in state.analysis_text
        assert state.validation_status in ("PASSED", "PASSED WITH WARNINGS")
        assert len(state.ai_predictions) == 1
        assert state.ai_predictions[0]["ticker"] == "NVDA"

        # Only 1 call to call_llm_fast (summarize + reflect) and 1+1 call_llm (analyze + validate)
        assert mock_llm_fast.call_count == 2
        assert mock_llm.call_count == 2

    @patch("workflows.nodes.call_llm")
    @patch("workflows.nodes.call_llm_fast")
    def test_progress_callback_invoked(self, mock_llm_fast, mock_llm, mock_externals):
        """Progress callback should be called with node labels."""
        summarize, reflect, analyze, validate = _make_llm_responses()
        mock_llm_fast.side_effect = [summarize, reflect]
        mock_llm.side_effect = [analyze, validate]

        progress_calls = []
        def progress_fn(event_type, msg):
            progress_calls.append((event_type, msg))

        _run_sector_graph(_SECTOR_ID, _SECTOR, progress_fn=progress_fn)

        # Should have "node" events for each pipeline step
        node_events = [msg for evt, msg in progress_calls if evt == "node"]
        assert len(node_events) >= 5  # fetch, summarize, reflect, analyze, validate, score, save


# ═══════════════════════════════════════════════════════════════════
# E2E: Refetch loop — reflect says insufficient → loops back to fetch
# ═══════════════════════════════════════════════════════════════════

class TestE2ERefetchLoop:

    @patch("workflows.nodes.call_llm")
    @patch("workflows.nodes.call_llm_fast")
    def test_refetch_loop_then_proceed(self, mock_llm_fast, mock_llm, mock_externals):
        """When reflect returns 'insufficient', pipeline loops back to fetch once,
        then proceeds to analyze on the second reflect (sufficient)."""
        summarize = "• NVIDIA beat earnings"
        reflect_insufficient = "VERDICT: INSUFFICIENT\nGAPS: Missing AMD data.\nREASONING: Need more."
        reflect_sufficient = "VERDICT: SUFFICIENT\nGAPS: None.\nREASONING: Good coverage."
        _, _, analyze, validate = _make_llm_responses()

        # Order: summarize(1st), reflect(1st→insufficient), summarize(2nd), reflect(2nd→sufficient)
        mock_llm_fast.side_effect = [
            summarize, reflect_insufficient,
            summarize, reflect_sufficient,
        ]
        mock_llm.side_effect = [analyze, validate]

        state = _run_sector_graph(_SECTOR_ID, _SECTOR)

        # Fetch was called twice (initial + 1 retry)
        assert mock_externals["news"].call_count == 2
        assert state.fetch_retry_count == 1
        assert state.pipeline_status == "completed"
        assert state.report_id == 42

        # LLM fast called 4 times (2x summarize + 2x reflect)
        assert mock_llm_fast.call_count == 4


# ═══════════════════════════════════════════════════════════════════
# E2E: Reanalyze loop — validation fails → loops back to analyze
# ═══════════════════════════════════════════════════════════════════

class TestE2EReanalyzeLoop:

    @patch("workflows.nodes.call_llm")
    @patch("workflows.nodes.call_llm_fast")
    def test_reanalyze_on_validation_failure(self, mock_llm_fast, mock_llm, mock_externals):
        """When validation returns FAILED, pipeline loops back to analyze,
        then on 2nd attempt validation passes."""
        summarize, reflect, analyze_v1, validate_fail = _make_llm_responses(
            validation="FAILED"
        )
        _, _, analyze_v2, validate_pass = _make_llm_responses(validation="PASSED")

        mock_llm_fast.side_effect = [summarize, reflect]
        # Order: analyze(1st), validate(1st→FAILED), analyze(2nd), validate(2nd→PASSED)
        mock_llm.side_effect = [analyze_v1, validate_fail, analyze_v2, validate_pass]

        state = _run_sector_graph(_SECTOR_ID, _SECTOR)

        # Analyze ran twice, validate ran twice
        assert mock_llm.call_count == 4
        assert state.validation_retry_count == 1
        assert state.pipeline_status == "completed"

    @patch("workflows.nodes.call_llm")
    @patch("workflows.nodes.call_llm_fast")
    def test_self_correction_feedback_injected(self, mock_llm_fast, mock_llm, mock_externals):
        """On re-analyze, validation issues from the failed attempt
        must appear in the analysis prompt (self-correction P0-1)."""
        summarize, reflect, analyze_v1, validate_fail = _make_llm_responses(
            validation="FAILED"
        )

        # On the second analyze call, capture the prompt to check for feedback
        captured_prompts = []
        def _capture_llm(prompt, **kwargs):
            captured_prompts.append(prompt)
            if len(captured_prompts) <= 1:
                return analyze_v1  # First analyze
            elif len(captured_prompts) == 2:
                return validate_fail  # First validate (FAILED)
            elif len(captured_prompts) == 3:
                return "## Corrected Analysis\nFixed numbers."  # Second analyze
            else:
                return "STATUS: PASSED\nLooks good now."  # Second validate

        mock_llm_fast.side_effect = [summarize, reflect]
        mock_llm.side_effect = _capture_llm

        state = _run_sector_graph(_SECTOR_ID, _SECTOR)

        # The 3rd call (2nd analyze) should contain self-correction feedback
        assert len(captured_prompts) >= 3
        second_analyze_prompt = captured_prompts[2]
        assert "SELF-CORRECTION REQUIRED" in second_analyze_prompt
        assert "DISCREPANCY" in second_analyze_prompt


# ═══════════════════════════════════════════════════════════════════
# run_sector_analysis — wrapper that returns result dict
# ═══════════════════════════════════════════════════════════════════

class TestRunSectorAnalysis:

    @patch("workflows.nodes.call_llm")
    @patch("workflows.nodes.call_llm_fast")
    def test_returns_result_dict(self, mock_llm_fast, mock_llm, mock_externals):
        """run_sector_analysis() should return a well-formed result dict."""
        summarize, reflect, analyze, validate = _make_llm_responses()
        mock_llm_fast.side_effect = [summarize, reflect]
        mock_llm.side_effect = [analyze, validate]

        result = run_sector_analysis(_SECTOR_ID, _SECTOR)

        assert result["sector_id"] == _SECTOR_ID
        assert result["sector_name"] == "AI & Semiconductors"
        assert result["report_id"] == 42
        assert result["confidence"] > 0
        assert "NVIDIA" in result["analysis"]
        assert result.get("error") is None
        assert result["timing"]["total_seconds"] >= 0
        assert len(result["timing"]["steps"]) > 0

    @patch("workflows.weekly_analysis._run_sector_graph", side_effect=RuntimeError("LLM crashed"))
    def test_returns_error_on_failure(self, mock_graph, mock_externals):
        """run_sector_analysis() should return an error dict, not crash."""
        result = run_sector_analysis(_SECTOR_ID, _SECTOR)

        assert result["error"] is not None
        assert "LLM crashed" in result["error"]
        assert result["report_id"] is None


# ═══════════════════════════════════════════════════════════════════
# run_weekly_analysis — multi-sector orchestration
# ═══════════════════════════════════════════════════════════════════

class TestRunWeeklyAnalysis:

    @patch("workflows.weekly_analysis.check_old_predictions")
    @patch("workflows.weekly_analysis.check_llm_health")
    @patch("workflows.weekly_analysis.run_sector_analysis")
    def test_runs_all_sectors(self, mock_run_sector, mock_health, mock_preds):
        """Should call run_sector_analysis for each requested sector."""
        mock_run_sector.return_value = {
            "sector_id": "test", "sector_name": "Test",
            "analysis": "Some analysis", "validation": "",
            "prices": [], "report_id": 1, "confidence": 7,
            "timing": {"total_seconds": 10, "steps": []},
            "error": None,
        }

        results = run_weekly_analysis(sector_ids=["ai_semiconductors"])

        mock_health.assert_called_once()
        assert len(results) == 1
        mock_preds.assert_called_once()

    @patch("workflows.weekly_analysis.check_llm_health",
           side_effect=MagicMock(side_effect=__import__("agents.llm_client", fromlist=["LLMHealthCheckError"]).LLMHealthCheckError("Connection refused")))
    def test_aborts_on_health_check_failure(self, mock_health):
        """If LLM health check fails, should return error dicts for all sectors."""
        results = run_weekly_analysis(sector_ids=["ai_semiconductors"])

        assert len(results) == 1
        assert results[0]["error"] is not None
        assert "Connection refused" in str(results[0]["error"])

    @patch("workflows.weekly_analysis.check_old_predictions")
    @patch("workflows.weekly_analysis.check_llm_health")
    @patch("workflows.weekly_analysis.run_sector_analysis")
    def test_progress_callback(self, mock_run_sector, mock_health, mock_preds):
        """Progress callback should receive sector_start and sector_done events."""
        mock_run_sector.return_value = {
            "sector_id": "ai_semiconductors", "sector_name": "AI & Semiconductors",
            "analysis": "Analysis", "validation": "", "prices": [],
            "report_id": 1, "confidence": 7,
            "timing": {"total_seconds": 5, "steps": []},
            "error": None,
        }

        events = []
        def progress_fn(event, msg):
            events.append((event, msg))

        run_weekly_analysis(sector_ids=["ai_semiconductors"], progress_fn=progress_fn)

        event_types = [e for e, _ in events]
        assert "step" in event_types  # LLM connection check
        assert "sector_start" in event_types
        assert "sector_done" in event_types


# ═══════════════════════════════════════════════════════════════════
# check_old_predictions
# ═══════════════════════════════════════════════════════════════════

class TestCheckOldPredictions:

    @patch("workflows.weekly_analysis.update_prediction_actual")
    @patch("workflows.weekly_analysis.get_stock_snapshot")
    @patch("workflows.weekly_analysis.get_unchecked_predictions")
    def test_updates_old_predictions(self, mock_unchecked, mock_snapshot, mock_update):
        """Predictions older than 7 days should be checked against current prices."""
        eight_days_ago = (datetime.now(timezone.utc) - timedelta(days=8)).isoformat()
        mock_unchecked.return_value = [
            {"id": 1, "ticker": "NVDA", "report_date": eight_days_ago},
            {"id": 2, "ticker": "AMD", "report_date": eight_days_ago},
        ]
        # Use function-based side_effect since set iteration order is arbitrary
        _prices = {"NVDA": 135.0, "AMD": 170.0}
        mock_snapshot.side_effect = lambda t: {"price": _prices[t], "error": None}

        check_old_predictions()

        assert mock_update.call_count == 2
        mock_update.assert_any_call(1, 135.0)
        mock_update.assert_any_call(2, 170.0)

    @patch("workflows.weekly_analysis.get_unchecked_predictions", return_value=[])
    def test_no_unchecked_predictions(self, mock_unchecked):
        """Should return silently when no predictions need checking."""
        check_old_predictions()  # No error

    @patch("workflows.weekly_analysis.update_prediction_actual")
    @patch("workflows.weekly_analysis.get_stock_snapshot")
    @patch("workflows.weekly_analysis.get_unchecked_predictions")
    def test_skips_recent_predictions(self, mock_unchecked, mock_snapshot, mock_update):
        """Predictions less than 7 days old should NOT be checked."""
        two_days_ago = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
        mock_unchecked.return_value = [
            {"id": 1, "ticker": "NVDA", "report_date": two_days_ago},
        ]

        check_old_predictions()

        mock_snapshot.assert_not_called()
        mock_update.assert_not_called()

    @patch("workflows.weekly_analysis.update_prediction_actual")
    @patch("workflows.weekly_analysis.get_stock_snapshot")
    @patch("workflows.weekly_analysis.get_unchecked_predictions")
    def test_handles_snapshot_failure(self, mock_unchecked, mock_snapshot, mock_update):
        """Should skip predictions where price fetch fails."""
        old_date = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
        mock_unchecked.return_value = [
            {"id": 1, "ticker": "NVDA", "report_date": old_date},
        ]
        mock_snapshot.return_value = {"error": "API down", "price": None}

        check_old_predictions()

        mock_update.assert_not_called()


# ═══════════════════════════════════════════════════════════════════
# _state_to_result — conversion helper
# ═══════════════════════════════════════════════════════════════════

class TestStateToResult:

    def test_maps_all_fields(self):
        """Result dict should contain all expected keys."""
        state = PipelineState.from_sector(_SECTOR_ID, _SECTOR)
        state.analysis_text = "Some analysis"
        state.validation_text = "Validation report"
        state.confidence_score = 7.5
        state.report_id = 99
        state.articles = [
            Article(title="a", source="s", link="l", published="p",
                    raw_summary="r", relevance_tag="t"),
            Article(title="b", source="s", link="l", published="p",
                    raw_summary="r", relevance_tag="t"),
        ]
        state.prices = _FAKE_PRICES
        state.total_duration_seconds = 25.0
        state.data_sufficiency = "sufficient"
        state.news_summary = "Summary"
        state.validation_status = "PASSED"

        result = _state_to_result(state)

        assert result["sector_id"] == _SECTOR_ID
        assert result["sector_name"] == "AI & Semiconductors"
        assert result["analysis"] == "Some analysis"
        assert result["confidence"] == 7.5
        assert result["report_id"] == 99
        assert result["news_count"] == 2
        assert result["timing"]["total_seconds"] == 25.0
        assert result["data_sufficiency"] == "sufficient"
        assert result["validation_status"] == "PASSED"
