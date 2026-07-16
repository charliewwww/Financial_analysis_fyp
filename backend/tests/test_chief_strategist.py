"""Unit tests for chief_strategist parsing + rule-based fallback (pure, no DB)."""

from __future__ import annotations

from app.schemas.analysis import ChiefVerdictAnalystView
from app.services.chief_strategist import (
    _extract_json_object,
    _rule_based_verdict,
)


def _analyst(signal: str, conviction: int = 3, name: str = "Analyst") -> ChiefVerdictAnalystView:
    return ChiefVerdictAnalystView(
        agent_id=None,
        agent_name=name,
        signal=signal,
        conviction=conviction,
        one_line="",
    )


# ── _extract_json_object ───────────────────────────────────────────


def test_extract_plain_json() -> None:
    assert _extract_json_object('{"action": "BUY", "conviction": 4}') == {
        "action": "BUY",
        "conviction": 4,
    }


def test_extract_fenced_json() -> None:
    raw = '```json\n{"action": "SELL"}\n```'
    assert _extract_json_object(raw) == {"action": "SELL"}


def test_extract_json_with_leading_prose() -> None:
    # The historical "Expecting value: line 1 column 1" failure mode.
    raw = 'Here is my verdict based on the bench:\n{"action": "HOLD", "conviction": 2}'
    assert _extract_json_object(raw) == {"action": "HOLD", "conviction": 2}


def test_extract_json_with_trailing_prose() -> None:
    raw = '{"action": "BUY"}\n\nLet me know if you need more detail.'
    assert _extract_json_object(raw) == {"action": "BUY"}


def test_extract_json_ignores_braces_inside_strings() -> None:
    raw = '{"summary": "risk is {contained}", "action": "BUY"}'
    assert _extract_json_object(raw) == {"summary": "risk is {contained}", "action": "BUY"}


def test_extract_returns_empty_on_garbage() -> None:
    assert _extract_json_object("no json here") == {}
    assert _extract_json_object("") == {}
    # Truncated / unterminated JSON returns {} (caller falls back).
    assert _extract_json_object('{"action": "BUY", "summary": "cut off here') == {}


# ── _rule_based_verdict ────────────────────────────────────────────


def test_rule_based_bullish_majority_buys() -> None:
    analysts = [_analyst("BULLISH", 4), _analyst("BULLISH", 3), _analyst("BEARISH", 2)]
    verdict = _rule_based_verdict("NVDA", analysts, "2026-01-01T00:00:00+00:00")
    assert verdict.action == "BUY"
    assert verdict.agreement == "split"
    assert "2 bullish" in verdict.deciding_reason
    # The user-facing message must NOT expose the internal failure.
    assert "unavailable" not in verdict.deciding_reason.lower()
    assert "model" not in verdict.deciding_reason.lower()


def test_rule_based_bearish_weight_sells() -> None:
    analysts = [_analyst("BEARISH", 5), _analyst("BULLISH", 2)]
    verdict = _rule_based_verdict("MSFT", analysts, "2026-01-01T00:00:00+00:00")
    assert verdict.action == "SELL"


def test_rule_based_tie_holds() -> None:
    analysts = [_analyst("BULLISH", 3), _analyst("BEARISH", 3)]
    verdict = _rule_based_verdict("GOOGL", analysts, "2026-01-01T00:00:00+00:00")
    assert verdict.action == "HOLD"
    assert verdict.agreement == "split"
    assert "unavailable" not in verdict.deciding_reason.lower()
