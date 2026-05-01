"""Unit tests for app.pipeline.signal_extractor — pure functions, no DB."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.pipeline.signal_extractor import (
    SignalCardDraft,
    build_numerical_claims,
    build_sources,
    extract_catalyst,
    extract_conviction,
    extract_one_line,
    extract_risk,
    extract_signal,
    from_pipeline_state,
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


# ── catalyst & risk ────────────────────────────────────────────────


def test_extract_catalyst_section() -> None:
    text = "## Key Catalyst\nQ1 earnings on Feb 26.\n## Next"
    assert extract_catalyst(text) == "Q1 earnings on Feb 26."


def test_extract_risk_section() -> None:
    text = "## Risk Assessment\nGuidance miss risk.\n## Other"
    assert extract_risk(text) == "Guidance miss risk."


def test_extract_catalyst_missing() -> None:
    assert extract_catalyst("nothing") == ""


# ── sources & numerical_claims ─────────────────────────────────────


def test_build_sources_extracts_domain() -> None:
    arts = [
        SimpleNamespace(link="https://www.bloomberg.com/news/x", title="A"),
        SimpleNamespace(link="https://reuters.com/y", title="B"),
    ]
    out = build_sources(arts)
    assert out[0]["domain"] == "www.bloomberg.com"
    assert out[1]["title"] == "B"


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


# ── from_pipeline_state — end-to-end ───────────────────────────────


def test_from_pipeline_state_full() -> None:
    state = SimpleNamespace(
        analysis_text=(
            "## Signal\nBULLISH on NVDA.\n"
            "## Thesis\nThe data centre cycle is intact.\n"
            "## Key Catalyst\nQ1 print Feb 26.\n"
            "## Key Risk\nChina export curbs.\n"
            "Conviction: 4/5\n"
        ),
        confidence_score=8,
        validation_status="PASS",
        articles=[SimpleNamespace(link="https://x.com/a", title="t")],
        validation_issues=[],
        sector_id="ai_semiconductors",
        sector_name="AI & Semiconductors",
    )
    draft = from_pipeline_state(
        state=state, run_id="r-1", ticker="NVDA", user_email="dev@local"
    )
    assert isinstance(draft, SignalCardDraft)
    assert draft.signal == "BULLISH"
    assert draft.conviction == 4
    assert draft.key_catalyst.startswith("Q1 print")
    assert draft.key_risk.startswith("China export")
    assert draft.confidence == pytest.approx(0.8)
    assert draft.validation_score == "PASS"
    assert draft.sources[0]["domain"] == "x.com"
    assert draft.sector_context["sector_id"] == "ai_semiconductors"


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
