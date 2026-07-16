"""Unit tests for app.pipeline.signal_extractor — pure functions, no DB."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.pipeline.signal_extractor import (
    SignalCardDraft,
    build_numerical_claims,
    build_raw_pipeline_state,
    build_sources,
    extract_catalyst,
    extract_conviction,
    extract_one_line,
    extract_risk,
    extract_signal,
    extract_supply_chain_impact,
    from_pipeline_state,
    is_failed_validation_status,
    normalize_validation_status,
)


# ── extract_signal ─────────────────────────────────────────────────


def test_extract_signal_under_signal_heading() -> None:
    text = "## Signal\nBULLISH on NVDA into Q1 print.\n## Other"
    assert extract_signal(text) == "BULLISH"


def test_extract_signal_under_thesis_heading() -> None:
    text = "## Thesis\nThe setup looks BEARISH given the macro backdrop.\n"
    assert extract_signal(text) == "BEARISH"


def test_extract_signal_case_insensitive() -> None:
    assert extract_signal("Conclusion: bullish") == "BULLISH"


def test_extract_signal_default_neutral() -> None:
    assert extract_signal("nothing actionable here") == "NEUTRAL"


# ── extract_conviction ─────────────────────────────────────────────


@pytest.mark.parametrize(
    "text,expected",
    [
        ("conviction: 4/5", 4),
        ("Conviction = 2", 2),
        ("our conviction 5", 5),
        ("conviction: 9", 5),  # clamped to 5
        ("conviction: 0", 1),  # clamped to 1
        ("no number here", 3),  # default
    ],
)
def test_extract_conviction(text: str, expected: int) -> None:
    assert extract_conviction(text) == expected


# ── extract_one_line ───────────────────────────────────────────────


def test_extract_one_line_under_thesis() -> None:
    text = "## Thesis\nNVDA is the cheapest hyperscaler proxy.\nMore detail follows…"
    assert extract_one_line(text).startswith("NVDA is the cheapest")


def test_extract_one_line_truncated_to_280() -> None:
    long = "a" * 400
    text = f"## Signal\n{long}\n"
    assert len(extract_one_line(text)) == 280


def test_extract_one_line_falls_back_to_first_non_heading() -> None:
    text = "# Header\nFirst real sentence."
    assert extract_one_line(text) == "First real sentence."


def test_extract_one_line_skips_metadata_lines() -> None:
    text = "## Signal\n**Date:** May 6, 2026\n**Analyst:** Risk Analyst\nNVDA demand risk is now mixed."
    assert extract_one_line(text) == "NVDA demand risk is now mixed."


def test_extract_one_line_prefers_signal_card_contract() -> None:
    text = "## SIGNAL CARD\nSignal: BULLISH\nOne-line thesis: NVDA demand is supported by sourced AI orders.\n## THESIS\nFallback."
    assert extract_one_line(text) == "NVDA demand is supported by sourced AI orders."


# ── catalyst & risk ────────────────────────────────────────────────


def test_extract_catalyst_section() -> None:
    text = "## Key Catalyst\nQ1 earnings on Feb 26.\n## Next"
    assert extract_catalyst(text) == "Q1 earnings on Feb 26."


def test_extract_catalyst_inline_label() -> None:
    text = "- **Primary Catalyst:** Blackwell demand is accelerating into the next earnings print."
    assert extract_catalyst(text).startswith("Blackwell demand")


def test_extract_risk_section() -> None:
    text = "## Risk Assessment\nGuidance miss risk.\n## Other"
    assert extract_risk(text) == "Guidance miss risk."


def test_extract_risk_inline_label() -> None:
    text = "Invalidation risk: Export controls could pressure China revenue."
    assert extract_risk(text).startswith("Export controls")


def test_extract_catalyst_missing() -> None:
    assert extract_catalyst("nothing") == ""


def test_extract_supply_chain_impact_from_signal_card_contract() -> None:
    text = "## SIGNAL CARD\nSupply-chain ripple: TSM ▲ advanced packaging demand; SMCI ▼ rack margin pressure"
    assert extract_supply_chain_impact(text, ticker="NVDA") == [
        {"ticker": "TSM", "direction": "▲", "reason": "advanced packaging demand"},
        {"ticker": "SMCI", "direction": "▼", "reason": "rack margin pressure"},
    ]


# ── sources & numerical_claims ─────────────────────────────────────


def test_build_sources_extracts_domain() -> None:
    arts = [
        SimpleNamespace(link="https://www.bloomberg.com/news/x", title="A"),
        SimpleNamespace(link="https://reuters.com/y", title="B"),
    ]
    out = build_sources(arts)
    assert out[0]["domain"] == "bloomberg.com"
    assert out[1]["title"] == "B"


def test_build_sources_uses_google_news_publisher_domain() -> None:
    arts = [
        SimpleNamespace(
            link="https://news.google.com/rss/articles/x",
            title="Nvidia demand rises",
            source="CNBC",
            publisher_url="https://www.cnbc.com",
        )
    ]
    out = build_sources(arts)
    assert out[0]["domain"] == "cnbc.com"


def test_build_sources_caps_at_10() -> None:
    arts = [SimpleNamespace(link=f"https://x.com/{i}", title=str(i)) for i in range(20)]
    assert len(build_sources(arts)) == 10


def test_build_numerical_claims_filters_dicts() -> None:
    state = SimpleNamespace(
        validation_issues=[
            {"claim": "rev +20%", "verified": True, "source": "10-Q"},
            "not a dict, ignored",  # type: ignore[list-item]
        ]
    )
    out = build_numerical_claims(state)
    assert len(out) == 1
    assert out[0]["verified"] is True


def test_build_numerical_claims_empty() -> None:
    assert build_numerical_claims(SimpleNamespace(validation_issues=None)) == []


# ── validation status helpers ─────────────────────────────────────


@pytest.mark.parametrize(
    "status,expected",
    [
        ("FAILED", True),
        ("validation failed after retry", True),
        ("PASSED", False),
        ("PASSED WITH WARNINGS", False),
        (None, False),
    ],
)
def test_is_failed_validation_status(status: str | None, expected: bool) -> None:
    assert is_failed_validation_status(status) is expected


def test_normalize_validation_status_handles_none() -> None:
    assert normalize_validation_status(None) == ""


# ── from_pipeline_state — end-to-end ───────────────────────────────


def test_from_pipeline_state_full() -> None:
    state = SimpleNamespace(
        analysis_text=(
            "## SIGNAL CARD\n"
            "Signal: BULLISH\n"
            "One-line thesis: The data centre cycle is intact.\n"
            "Key catalyst: Q1 print Feb 26.\n"
            "Invalidation risk: China export curbs.\n"
            "Supply-chain ripple: TSM ▲ packaging capacity demand\n"
            "Conviction: 4/5\n"
            "## Thesis\nThe data centre cycle is intact.\n"
        ),
        confidence_score=8,
        validation_status="PASS",
        articles=[SimpleNamespace(link="https://x.com/a", title="t")],
        validation_issues=[],
        sector_id="ai_semiconductors",
        sector_name="AI & Semiconductors",
    )
    draft = from_pipeline_state(
        state=state,
        run_id="r-1",
        ticker="NVDA",
        user_email="dev@local",
        agent_id=1,
    )
    assert isinstance(draft, SignalCardDraft)
    assert draft.signal == "BULLISH"
    assert draft.conviction == 4
    assert draft.key_catalyst.startswith("Q1 print")
    assert draft.key_risk.startswith("China export")
    assert draft.supply_chain_impact == [
        {"ticker": "TSM", "direction": "▲", "reason": "packaging capacity demand"}
    ]
    assert draft.confidence == pytest.approx(0.8)
    assert draft.agent_id == 1
    assert draft.validation_score == "PASS"
    assert draft.sources[0]["domain"] == "x.com"
    assert draft.sector_context["sector_id"] == "ai_semiconductors"


# ── build_raw_pipeline_state — token accounting ────────────────────


def test_build_raw_pipeline_state_captures_token_usage() -> None:
    state = SimpleNamespace(
        analysis_text="Signal: BULLISH",
        total_llm_prompt_tokens=15423,
        total_llm_completion_tokens=5707,
        model_override="",
        node_executions=[
            {"node_name": "fetch", "llm_model": None},
            {"node_name": "summarize", "llm_model": "deepseek-v4-flash"},
            {"node_name": "analyze", "llm_model": "deepseek-v4-pro"},
        ],
    )
    raw = build_raw_pipeline_state(state)
    assert raw["total_llm_prompt_tokens"] == 15423
    assert raw["total_llm_completion_tokens"] == 5707
    # The analyze node's model wins (it does the bulk of the work).
    assert raw["llm_model"] == "deepseek-v4-pro"


def test_build_raw_pipeline_state_defaults_when_no_tokens() -> None:
    state = SimpleNamespace(analysis_text="x")
    raw = build_raw_pipeline_state(state)
    assert raw["total_llm_prompt_tokens"] == 0
    assert raw["total_llm_completion_tokens"] == 0
    assert raw["llm_model"] == ""


def test_from_pipeline_state_handles_missing_fields() -> None:
    state = SimpleNamespace(
        analysis_text="",
        confidence_score=None,
        validation_status=None,
        articles=None,
        validation_issues=None,
    )
    draft = from_pipeline_state(
        state=state, run_id="r-2", ticker="AMD", user_email=None
    )
    assert draft.signal == "NEUTRAL"
    assert draft.conviction == 3
    assert draft.confidence == 0.0
    assert draft.sources == []
    assert draft.validation_score == ""


def test_from_pipeline_state_caps_confidence_when_evidence_missing() -> None:
    state = SimpleNamespace(
        analysis_text="## Signal\n**Date:** May 6, 2026\nBULLISH on NVDA.\nConviction: 5/5",
        confidence_score=9,
        validation_status="PASSED",
        articles=[SimpleNamespace(link="https://x.com/a", title="t")],
        validation_issues=[],
    )
    draft = from_pipeline_state(
        state=state, run_id="r-3", ticker="NVDA", user_email="dev@local"
    )
    assert draft.one_line == "BULLISH on NVDA."
    assert draft.key_catalyst == ""
    assert draft.key_risk == ""
    assert draft.confidence == pytest.approx(0.65)


def test_from_pipeline_state_caps_confidence_at_40_when_sources_missing() -> None:
    state = SimpleNamespace(
        analysis_text=(
            "## Signal\nBULLISH on NVDA.\n"
            "Primary Catalyst: Blackwell demand.\n"
            "Invalidation risk: Export controls.\n"
        ),
        confidence_score=9,
        validation_status="PASSED",
        articles=[],
        validation_issues=[],
    )
    draft = from_pipeline_state(
        state=state, run_id="r-4", ticker="NVDA", user_email="dev@local"
    )
    assert draft.confidence == pytest.approx(0.4)


# ── conviction_was_stated ──────────────────────────────────────────


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Conviction: 4/5", True),
        ("our conviction 5", True),
        ("no number here", False),
        ("", False),
    ],
)
def test_conviction_was_stated(text: str, expected: bool) -> None:
    from app.pipeline.signal_extractor import conviction_was_stated

    assert conviction_was_stated(text) is expected


def test_from_pipeline_state_marks_conviction_not_stated() -> None:
    """When the model omits conviction, the draft flags it as unstated."""
    state = SimpleNamespace(
        analysis_text="## Signal\nBULLISH on NVDA. Strong demand.",
        confidence_score=8,
        validation_status="PASSED",
        articles=[SimpleNamespace(link="https://x.com/a", title="t")],
        validation_issues=[],
    )
    draft = from_pipeline_state(
        state=state, run_id="r-5", ticker="NVDA", user_email="dev@local"
    )
    assert draft.conviction == 3  # default fallback persisted for the NOT NULL column
    assert draft.raw_pipeline_state["conviction_stated"] is False


# ── classify_signal_type ───────────────────────────────────────────


def test_classify_signal_type_fundamental_from_filings() -> None:
    from app.pipeline.signal_extractor import classify_signal_type

    out = classify_signal_type(
        analysis_text="Q1 earnings beat with revenue and margin expansion.",
        key_catalyst="Earnings beat; raised guidance",
        one_line="Fundamentals are improving",
        filings=[{"form": "10-Q"}],
        articles=[],
        technicals=[],
        anomaly_alerts=[],
    )
    assert out == "FUNDAMENTAL_SHIFT"


def test_classify_signal_type_technical_only() -> None:
    from app.pipeline.signal_extractor import classify_signal_type

    out = classify_signal_type(
        analysis_text="RSI is oversold and MACD just crossed; watch the support level.",
        key_catalyst="Oversold RSI bounce off support level",
        one_line="Technical breakout setup",
        filings=[],
        articles=[],
        technicals=[{"rsi_14": 22, "macd_bullish": True}],
        anomaly_alerts=[],
    )
    assert out == "TECHNICAL_ONLY"


def test_classify_signal_type_media_narrative() -> None:
    from app.pipeline.signal_extractor import classify_signal_type

    out = classify_signal_type(
        analysis_text="Reportedly social-media buzz and an analyst upgrade drove sentiment.",
        key_catalyst="Analyst upgrade and price target hike amid social media hype",
        one_line="Narrative-driven move on rumor",
        filings=[],
        articles=[SimpleNamespace(title=str(i)) for i in range(8)],
        technicals=[],
        anomaly_alerts=[],
    )
    assert out == "MEDIA_NARRATIVE"


def test_classify_signal_type_empty_falls_back() -> None:
    from app.pipeline.signal_extractor import classify_signal_type

    # No textual signal, but filings exist → fundamental.
    assert (
        classify_signal_type(
            analysis_text="",
            key_catalyst="",
            one_line="",
            filings=[{"form": "8-K"}],
            articles=[],
            technicals=[],
            anomaly_alerts=[],
        )
        == "FUNDAMENTAL_SHIFT"
    )
    # Nothing at all → technical-only (most conservative, least claim).
    assert (
        classify_signal_type(
            analysis_text="",
            key_catalyst="",
            one_line="",
            filings=[],
            articles=[],
            technicals=[],
            anomaly_alerts=[],
        )
        == "TECHNICAL_ONLY"
    )
