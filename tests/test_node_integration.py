"""
Integration tests for workflows/nodes.py — fetch, summarize, reflect,
analyze, validate, save, and _parse_predictions.

Every external call (LLM, HTTP, database, vectordb) is mocked so these
tests run fast, offline, and deterministically.  They verify that each
node correctly wires inputs → processing → state mutations.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from models.state import PipelineState, Article
from workflows.nodes import (
    fetch_node,
    summarize_node,
    reflect_node,
    analyze_node,
    validate_node,
    save_node,
    _parse_predictions,
)


# ═══════════════════════════════════════════════════════════════════
# Shared helpers
# ═══════════════════════════════════════════════════════════════════

def _sector_state(**overrides) -> PipelineState:
    """Minimal PipelineState with sector metadata populated."""
    state = PipelineState.from_sector("ai_semiconductors", {
        "name": "AI & Semiconductors",
        "description": "Test sector for GPU and chip companies",
        "tickers": ["NVDA", "TSM", "AMD"],
        "keywords": ["ai", "semiconductor", "gpu"],
        "supply_chain_map": {"NVDA": {"role": "GPU designer"}},
    })
    for k, v in overrides.items():
        setattr(state, k, v)
    return state


_FAKE_ARTICLES = [
    {
        "title": f"Article {i}",
        "source": "CNBC",
        "link": f"https://example.com/{i}",
        "published": "2024-06-01",
        "summary": f"Summary of article {i}",
        "relevance": "ticker:NVDA",
    }
    for i in range(5)
]

_FAKE_PRICES = [
    {"ticker": "NVDA", "price": 130.0, "market_cap": 3.2e12},
    {"ticker": "TSM", "price": 175.0, "market_cap": 900e9},
    {"ticker": "AMD", "price": 165.0, "market_cap": 265e9},
]

_FAKE_TECHNICALS = [
    {"ticker": "NVDA", "rsi_14": 62.5, "macd": 1.2},
    {"ticker": "TSM", "rsi_14": 55.0, "macd": 0.8},
    {"ticker": "AMD", "rsi_14": 70.0, "macd": -0.3},
]

_FAKE_FILINGS = [
    {"ticker": "NVDA", "type": "10-K", "date": "2024-02-21", "text_total_chars": 5000},
]

_FAKE_MACRO = {
    "_meta": {"api_status": "ok", "indicators_fetched": 6, "source": "FRED", "fetched_at": "2024-06-01T00:00:00"},
    "fed_funds_rate": {
        "value": 5.25, "name": "Federal Funds Rate", "unit": "%",
        "date": "2024-06-01", "trend": "stable", "change": 0.0,
        "interpretation": {"stable": "Rates unchanged."},
    },
}


# ═══════════════════════════════════════════════════════════════════
# fetch_node
# ═══════════════════════════════════════════════════════════════════

class TestFetchNode:
    """Verify fetch_node populates state from all five data sources."""

    @patch("workflows.nodes.rag_is_available", return_value=False)
    @patch("workflows.nodes._fetch_macro", return_value=_FAKE_MACRO)
    @patch("workflows.nodes._fetch_filings", return_value=_FAKE_FILINGS)
    @patch("workflows.nodes._fetch_technicals", return_value=_FAKE_TECHNICALS)
    @patch("workflows.nodes._fetch_prices", return_value=_FAKE_PRICES)
    @patch("workflows.nodes._fetch_news", return_value=_FAKE_ARTICLES)
    def test_populates_all_fields(self, m_news, m_prices, m_tech, m_fil, m_macro, m_rag):
        state = _sector_state()
        result = fetch_node(state)

        assert len(result.articles) == 5
        assert len(result.prices) == 3
        assert len(result.technicals) == 3
        assert len(result.filings) == 1
        assert result.macro_data["_meta"]["api_status"] == "ok"
        assert result.fetch_metadata["total_articles"] == 5

    @patch("workflows.nodes.rag_is_available", return_value=False)
    @patch("workflows.nodes._fetch_macro", return_value={})
    @patch("workflows.nodes._fetch_filings", return_value=[])
    @patch("workflows.nodes._fetch_technicals", return_value=[])
    @patch("workflows.nodes._fetch_prices", return_value=[])
    @patch("workflows.nodes._fetch_news", return_value=[])
    def test_empty_data_no_crash(self, *mocks):
        """Node should handle zero data gracefully."""
        state = _sector_state()
        result = fetch_node(state)
        assert result.articles == []
        assert result.prices == []

    @patch("workflows.nodes.rag_is_available", return_value=False)
    @patch("workflows.nodes._fetch_macro", side_effect=RuntimeError("API down"))
    @patch("workflows.nodes._fetch_filings", return_value=[])
    @patch("workflows.nodes._fetch_technicals", return_value=[])
    @patch("workflows.nodes._fetch_prices", return_value=_FAKE_PRICES)
    @patch("workflows.nodes._fetch_news", return_value=_FAKE_ARTICLES)
    def test_partial_failure_continues(self, m_news, m_prices, m_tech, m_fil, m_macro, m_rag):
        """If one source crashes, others still populate the state."""
        state = _sector_state()
        result = fetch_node(state)
        assert len(result.articles) == 5
        assert len(result.prices) == 3
        # macro failed → should get empty dict instead of crash
        assert result.macro_data == {}

    @patch("workflows.nodes.rag_is_available", return_value=False)
    @patch("workflows.nodes._fetch_macro", return_value=_FAKE_MACRO)
    @patch("workflows.nodes._fetch_filings", return_value=[])
    @patch("workflows.nodes._fetch_technicals", return_value=[])
    @patch("workflows.nodes._fetch_prices", return_value=[])
    @patch("workflows.nodes._fetch_news", return_value=_FAKE_ARTICLES)
    def test_refetch_broadens_keywords(self, m_news, *mocks):
        """Second fetch attempt should add extra keywords."""
        state = _sector_state(fetch_retry_count=1)
        fetch_node(state)
        call_args = m_news.call_args[0][0]
        # Broadened keywords should include sector name words
        assert len(call_args["keywords"]) > 3  # More than the original 3


# ═══════════════════════════════════════════════════════════════════
# summarize_node
# ═══════════════════════════════════════════════════════════════════

class TestSummarizeNode:

    @patch("workflows.nodes.call_llm_fast")
    def test_produces_summary(self, mock_llm):
        mock_llm.return_value = (
            "Brief summary of the semiconductor sector.\n\n"
            "- NVIDIA beat Q4 earnings [SOURCE: CNBC]\n"
            "- TSM raised revenue guidance [SOURCE: Reuters]\n"
            "- AMD launched new MI300X chip [SOURCE: MarketWatch]\n"
        )
        state = _sector_state(
            articles=[
                Article(title=f"Art {i}", source="CNBC", link="http://x",
                        published="2024-01-15", raw_summary="text")
                for i in range(5)
            ],
        )
        result = summarize_node(state)

        assert result.news_summary != ""
        assert len(result.summary_bullet_points) >= 3
        mock_llm.assert_called_once()

    def test_no_articles_returns_default(self):
        """Empty articles → default summary without LLM call."""
        state = _sector_state(articles=[])
        result = summarize_node(state)
        assert "No articles" in result.news_summary


# ═══════════════════════════════════════════════════════════════════
# reflect_node
# ═══════════════════════════════════════════════════════════════════

class TestReflectNode:

    @patch("workflows.nodes.call_llm_fast")
    def test_sufficient(self, mock_llm):
        mock_llm.return_value = (
            "VERDICT: SUFFICIENT\n"
            "GAPS: None\n"
            "REASONING: Plenty of data from multiple sources."
        )
        state = _sector_state(
            articles=[Article(title="A", source="S", link="L",
                              published="2024-01-01", raw_summary="T")] * 10,
            prices=_FAKE_PRICES,
            technicals=_FAKE_TECHNICALS,
            filings=_FAKE_FILINGS,
            macro_data=_FAKE_MACRO,
            news_summary="Good coverage.",
        )
        result = reflect_node(state)
        assert result.data_sufficiency == "sufficient"
        assert result.fetch_retry_count == 0  # Not incremented for sufficient

    @patch("workflows.nodes.call_llm_fast")
    def test_insufficient_increments_retry(self, mock_llm):
        mock_llm.return_value = (
            "VERDICT: INSUFFICIENT\n"
            "GAPS:\n- Missing macro data\n- Only 1 source\n"
            "REASONING: Not enough diversity."
        )
        state = _sector_state(
            articles=[],
            prices=[],
            technicals=[],
            filings=[],
            macro_data={},
            news_summary="",
            fetch_retry_count=0,
        )
        result = reflect_node(state)
        assert result.data_sufficiency == "insufficient"
        assert result.fetch_retry_count == 1  # Incremented

    @patch("workflows.nodes.call_llm_fast")
    def test_marginal(self, mock_llm):
        mock_llm.return_value = "VERDICT: MARGINAL\nGAPS: Limited filing data.\nREASONING: Acceptable."
        state = _sector_state(
            articles=[Article(title="A", source="S", link="L",
                              published="2024-01-01", raw_summary="T")],
            prices=_FAKE_PRICES,
            technicals=[],
            filings=[],
            macro_data=_FAKE_MACRO,
            news_summary="Some coverage.",
        )
        result = reflect_node(state)
        assert result.data_sufficiency == "marginal"


# ═══════════════════════════════════════════════════════════════════
# analyze_node
# ═══════════════════════════════════════════════════════════════════

class TestAnalyzeNode:

    @patch("workflows.nodes.rag_is_available", return_value=False)
    @patch("workflows.nodes.call_llm")
    def test_produces_analysis(self, mock_llm, mock_rag):
        mock_llm.return_value = (
            "## AI & Semiconductors Analysis\n\n"
            "NVIDIA dominates the AI chip market.\n\n"
            "## PRICE PREDICTIONS\n"
            "**NVDA**: BULLISH | Expected move: +3% to +7%\n"
            "- Reasoning: Strong data-center demand\n"
            "- Key risk: Export controls\n"
        )
        state = _sector_state(
            articles=[
                Article(title="NVDA beats", source="CNBC", link="http://x",
                        published="2024-01-15", raw_summary="Revenue $22B",
                        used_in_analysis=True),
            ],
            prices=_FAKE_PRICES,
            technicals=_FAKE_TECHNICALS,
            filings=[],
            macro_data=_FAKE_MACRO,
            news_summary="NVIDIA beat earnings.",
        )
        result = analyze_node(state)

        assert "NVIDIA" in result.analysis_text
        assert result.analysis_prompt_used != ""
        assert len(result.ai_predictions) == 1
        assert result.ai_predictions[0]["ticker"] == "NVDA"
        assert result.ai_predictions[0]["direction"] == "BULLISH"

    @patch("workflows.nodes.rag_is_available", return_value=True)
    @patch("workflows.nodes.rag_query")
    @patch("workflows.nodes.format_rag_context", return_value="Prior analysis: market was bullish.")
    @patch("workflows.nodes.call_llm")
    def test_includes_rag_context(self, mock_llm, mock_fmt, mock_rq, mock_avail):
        mock_rq.return_value = {
            "total_results": 3,
            "query_time_seconds": 0.5,
            "news": [{"doc": "old news"}],
            "filings": [],
            "analyses": [{"doc": "old analysis"}],
        }
        mock_llm.return_value = "## Analysis\nWith historical context..."
        state = _sector_state(
            articles=[
                Article(title="A", source="S", link="L", published="2024-01-01",
                        raw_summary="T", used_in_analysis=True),
            ],
            prices=_FAKE_PRICES,
            technicals=_FAKE_TECHNICALS,
            filings=[],
            macro_data={},
            news_summary="Summary.",
        )
        result = analyze_node(state)

        mock_rq.assert_called_once()
        assert result.rag_context != ""
        assert "Prior analysis" in result.analysis_prompt_used

    @patch("workflows.nodes.rag_is_available", return_value=False)
    @patch("workflows.nodes.call_llm")
    def test_injects_validation_feedback_on_retry(self, mock_llm, mock_rag):
        """On re-analyze (validation_retry_count > 0), validation issues
        must be injected into the prompt so the LLM can self-correct."""
        mock_llm.return_value = "## Corrected Analysis\nFixed the numbers."
        state = _sector_state(
            articles=[
                Article(title="A", source="S", link="L", published="2024-01-01",
                        raw_summary="T", used_in_analysis=True),
            ],
            prices=_FAKE_PRICES,
            technicals=_FAKE_TECHNICALS,
            filings=[],
            macro_data={},
            news_summary="Summary.",
            validation_retry_count=1,
            validation_status="FAILED",
            validation_issues=[
                "⚠️ NVDA: price claimed=999.00 actual=130.00 (off by +668.5%)",
                "⚠️ DISCREPANCY: AMD PE ratio not cited",
            ],
        )
        result = analyze_node(state)

        # Validation issues must appear in the prompt sent to the LLM
        assert "SELF-CORRECTION REQUIRED" in result.analysis_prompt_used
        assert "claimed=999.00" in result.analysis_prompt_used
        assert "AMD PE ratio" in result.analysis_prompt_used
        # The correction block should be the very first thing in the prompt
        assert result.analysis_prompt_used.startswith("## ⚠️ SELF-CORRECTION")

    @patch("workflows.nodes.rag_is_available", return_value=False)
    @patch("workflows.nodes.call_llm")
    def test_no_feedback_on_first_attempt(self, mock_llm, mock_rag):
        """On first attempt (validation_retry_count == 0), no correction
        block should be injected."""
        mock_llm.return_value = "## Analysis\nFirst attempt."
        state = _sector_state(
            articles=[
                Article(title="A", source="S", link="L", published="2024-01-01",
                        raw_summary="T", used_in_analysis=True),
            ],
            prices=_FAKE_PRICES,
            technicals=_FAKE_TECHNICALS,
            filings=[],
            macro_data={},
            news_summary="Summary.",
            validation_retry_count=0,
        )
        result = analyze_node(state)
        assert "SELF-CORRECTION" not in result.analysis_prompt_used


# ═══════════════════════════════════════════════════════════════════
# validate_node
# ═══════════════════════════════════════════════════════════════════

class TestValidateNode:

    @patch("workflows.nodes.call_llm")
    def test_passed(self, mock_llm):
        mock_llm.return_value = (
            "VERDICT: PASSED\n"
            "The analysis is well-reasoned with proper source citations."
        )
        state = _sector_state(
            analysis_text="NVDA trades at $130. RSI is 62.5.",
            prices=_FAKE_PRICES,
            technicals=_FAKE_TECHNICALS,
        )
        result = validate_node(state)
        assert result.validation_status in ("PASSED", "PASSED WITH WARNINGS")
        assert result.validation_text != ""

    @patch("workflows.nodes.call_llm")
    def test_failed_increments_retry(self, mock_llm):
        mock_llm.return_value = "VERDICT: FAILED\n⚠️ DISCREPANCY: Completely fabricated numbers."
        state = _sector_state(
            analysis_text="NVDA trades at $999.",
            prices=_FAKE_PRICES,
            technicals=_FAKE_TECHNICALS,
            validation_retry_count=0,
        )
        result = validate_node(state)
        assert result.validation_status == "FAILED"
        assert result.validation_retry_count == 1

    @patch("workflows.nodes.call_llm")
    def test_validation_issues_collected(self, mock_llm):
        mock_llm.return_value = (
            "VERDICT: PASSED WITH WARNINGS\n"
            "⚠️ DISCREPANCY: AMD PE ratio not cited\n"
        )
        state = _sector_state(
            analysis_text="AMD is strong. NVDA at $130.",
            prices=_FAKE_PRICES,
            technicals=_FAKE_TECHNICALS,
        )
        result = validate_node(state)
        assert result.validation_status == "PASSED WITH WARNINGS"
        assert any("DISCREPANCY" in iss for iss in result.validation_issues)


# ═══════════════════════════════════════════════════════════════════
# save_node
# ═══════════════════════════════════════════════════════════════════

class TestSaveNode:

    @patch("workflows.nodes.rag_is_available", return_value=False)
    @patch("workflows.nodes.save_report_from_state", return_value=42)
    def test_saves_and_sets_report_id(self, mock_save, mock_rag):
        state = _sector_state(
            analysis_text="Analysis text...",
            validation_text="Validation text...",
            confidence_score=7.5,
        )
        result = save_node(state)
        assert result.report_id == 42
        mock_save.assert_called_once()

    @patch("workflows.nodes.rag_is_available", return_value=True)
    @patch("workflows.nodes.rag_ingest_analysis", return_value=3)
    @patch("workflows.nodes.save_report_from_state", return_value=99)
    def test_ingests_into_vectordb(self, mock_save, mock_ingest, mock_rag):
        state = _sector_state(
            analysis_text="Long analysis text " * 100,
            confidence_score=8.0,
        )
        result = save_node(state)
        mock_ingest.assert_called_once()
        assert result.report_id == 99


# ═══════════════════════════════════════════════════════════════════
# _parse_predictions
# ═══════════════════════════════════════════════════════════════════

class TestParsePredictions:

    def test_parses_bullish(self):
        text = (
            "## PRICE PREDICTIONS\n"
            "**NVDA**: BULLISH | Expected move: +3% to +7%\n"
            "- Reasoning: Strong data-center demand\n"
            "- Key risk: Export controls\n"
        )
        preds = _parse_predictions(text, ["NVDA", "TSM"])
        assert len(preds) == 1
        assert preds[0]["ticker"] == "NVDA"
        assert preds[0]["direction"] == "BULLISH"
        assert "data-center" in preds[0]["reasoning"].lower()

    def test_parses_bracket_bold_format(self):
        """Real LLM output format: *   **[LITE]**: **BEARISH** | Expected move: ..."""
        text = (
            "## PRICE PREDICTIONS (1-WEEK OUTLOOK)\n\n"
            "*   **[LITE]**: **BEARISH** | Expected move: -3% to -6%\n"
            "    *   **Reasoning:** RSI is at 91.1, extreme overbought.\n"
            "    *   **Key risk:** Partnership announcement.\n\n"
            "*   **[CIEN]**: **NEUTRAL** | Expected move: +1% to -1%\n"
            "    *   **Reasoning:** Index inclusion is priced in.\n"
            "    *   **Key risk:** Broader market rally.\n"
        )
        preds = _parse_predictions(text, ["LITE", "CIEN"])
        assert len(preds) == 2
        assert preds[0]["ticker"] == "LITE"
        assert preds[0]["direction"] == "BEARISH"
        assert "91.1" in preds[0]["reasoning"]
        assert "**" not in preds[0]["reasoning"]  # Bold markers stripped
        assert preds[1]["ticker"] == "CIEN"
        assert preds[1]["direction"] == "NEUTRAL"

    def test_parses_multiple_tickers(self):
        text = (
            "## PRICE PREDICTIONS\n"
            "**NVDA**: BULLISH | Expected move: +5%\n"
            "- Reasoning: AI demand\n"
            "- Key risk: Competition\n\n"
            "**TSM**: NEUTRAL | Expected move: -1% to +2%\n"
            "- Reasoning: Stable fab utilization\n"
            "- Key risk: Geopolitical\n\n"
            "**AMD**: BEARISH | Expected move: -3% to -5%\n"
            "- Reasoning: Market share loss\n"
            "- Key risk: GPU pricing war\n"
        )
        preds = _parse_predictions(text, ["NVDA", "TSM", "AMD"])
        assert len(preds) == 3
        directions = {p["ticker"]: p["direction"] for p in preds}
        assert directions == {"NVDA": "BULLISH", "TSM": "NEUTRAL", "AMD": "BEARISH"}

    def test_no_prediction_section(self):
        text = "## Analysis\nNVDA looks strong. No prediction section here."
        preds = _parse_predictions(text, ["NVDA"])
        assert preds == []

    def test_stops_at_next_section(self):
        text = (
            "## PRICE PREDICTIONS\n"
            "**NVDA**: BULLISH | Expected move: +5%\n"
            "- Reasoning: demand\n\n"
            "## RISK ASSESSMENT\n"
            "**AMD**: BEARISH | Expected move: -3%\n"
        )
        preds = _parse_predictions(text, ["NVDA", "AMD"])
        # AMD line is in a different section — should not be parsed
        assert len(preds) == 1
        assert preds[0]["ticker"] == "NVDA"
