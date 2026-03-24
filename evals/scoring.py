"""
Langfuse Score Pushers — attach quantitative evaluation scores to traces.

After each pipeline run, these functions score the trace across multiple
dimensions. Scores appear in the Langfuse dashboard as filterable metrics,
enabling:
  - Tracking quality over time (regression detection)
  - Comparing model/prompt variants (A/B testing)
  - Identifying weak spots for targeted improvement

Score dimensions (all 0-1 normalized):
  1. numerical_accuracy    — % of numerical claims verified correct
  2. validation_quality    — multi-layer validation result (0/0.5/1)
  3. analysis_completeness — does the report contain all required sections?
  4. source_coverage       — data source diversity and volume
  5. confidence_calibration — internal confidence vs data quality alignment
  6. latency_score         — pipeline speed (penalize >120s)
  7. prediction_quality    — directional accuracy when actuals are available

Each score is pushed to the Langfuse trace via the Langfuse SDK's score()
method. Scores are float 0-1 (higher = better) with an optional comment.
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from models.state import PipelineState

logger = logging.getLogger(__name__)


# ── Required analysis sections (from SYSTEM_PROMPT_ANALYST) ───────

_REQUIRED_SECTIONS = [
    "THESIS",
    "KEY DEVELOPMENTS",
    "DEEP CONTEXT",
    "MACRO",
    "SUPPLY CHAIN",
    "RISK",
    "PRICE PREDICTION",
    "CONFIDENCE",
]


def score_numerical_accuracy(state: "PipelineState") -> tuple[float, str]:
    """
    Score 0-1: what fraction of extracted numerical claims were verified?

    Uses the programmatic validation results already computed in validate_node.
    Higher = more claims match real market data within tolerance.
    """
    # Parse validation issues to count verified vs total
    validation_text = state.validation_text or ""

    # Count from the numerical validator output
    verified = 0
    discrepancies = 0
    total_claims = 0

    for line in validation_text.split("\n"):
        line_lower = line.lower()
        if "✅" in line or "verified" in line_lower:
            verified += 1
            total_claims += 1
        elif "❌" in line or "discrepancy" in line_lower:
            discrepancies += 1
            total_claims += 1

    if total_claims == 0:
        # No numerical claims extracted — neutral score
        return 0.5, "No numerical claims found to verify"

    score = verified / total_claims
    comment = f"{verified}/{total_claims} claims verified ({discrepancies} discrepancies)"
    return round(score, 3), comment


def score_validation_quality(state: "PipelineState") -> tuple[float, str]:
    """
    Score 0-1: overall validation result.

    PASSED=1.0, PASSED WITH WARNINGS=0.5, FAILED=0.0
    Also factors in retry count (each retry deducts 0.1).
    """
    status = (state.validation_status or "").upper()

    if "FAILED" in status:
        base = 0.0
    elif "WARNING" in status:
        base = 0.5
    elif "PASSED" in status:
        base = 1.0
    else:
        base = 0.25  # Unknown status

    # Penalty for retries: each retry means the first attempt had issues
    retry_penalty = state.validation_retry_count * 0.1
    score = max(0.0, base - retry_penalty)

    comment = f"Status: {state.validation_status}"
    if state.validation_retry_count > 0:
        comment += f" (after {state.validation_retry_count} retry/retries)"

    return round(score, 3), comment


def score_analysis_completeness(state: "PipelineState") -> tuple[float, str]:
    """
    Score 0-1: does the analysis contain all required sections?

    Checks for the 8 mandatory sections defined in SYSTEM_PROMPT_ANALYST.
    Missing sections indicate the LLM didn't follow instructions.
    """
    text = (state.analysis_text or "").upper()
    found = []
    missing = []

    for section in _REQUIRED_SECTIONS:
        if section.upper() in text:
            found.append(section)
        else:
            missing.append(section)

    score = len(found) / len(_REQUIRED_SECTIONS) if _REQUIRED_SECTIONS else 0.0
    comment = f"{len(found)}/{len(_REQUIRED_SECTIONS)} sections present"
    if missing:
        comment += f" — missing: {', '.join(missing)}"

    return round(score, 3), comment


def score_source_coverage(state: "PipelineState") -> tuple[float, str]:
    """
    Score 0-1: data source diversity and volume.

    Components:
      - Article count (0-0.3): 0 articles=0, 5+=0.3
      - Price data (0-0.2): have valid prices for all tickers
      - Technicals (0-0.15): have technical indicators
      - Filings (0-0.1): have SEC filings
      - Macro (0-0.1): have macro data
      - Source diversity (0-0.15): unique news sources
    """
    components = {}

    # Article count
    n_articles = len(state.articles)
    components["articles"] = min(n_articles / 5, 1.0) * 0.3

    # Price data
    valid_prices = [p for p in state.prices if not p.get("error")]
    expected = len(state.sector_tickers) or 1
    components["prices"] = min(len(valid_prices) / expected, 1.0) * 0.2

    # Technicals
    valid_ta = [t for t in state.technicals if not t.get("error")]
    components["technicals"] = min(len(valid_ta) / max(expected, 1), 1.0) * 0.15

    # Filings
    valid_filings = [f for f in state.filings if "error" not in f]
    components["filings"] = (0.1 if valid_filings else 0.0)

    # Macro
    macro_meta = state.macro_data.get("_meta", {})
    if macro_meta.get("api_status") == "ok":
        fetched = macro_meta.get("indicators_fetched", 0)
        components["macro"] = min(fetched / 6, 1.0) * 0.1
    else:
        components["macro"] = 0.0

    # Source diversity
    if state.articles:
        unique = len(set(a.source for a in state.articles))
        components["diversity"] = min(unique / 4, 1.0) * 0.15
    else:
        components["diversity"] = 0.0

    score = sum(components.values())
    parts = ", ".join(f"{k}={v:.2f}" for k, v in components.items())
    comment = f"Components: {parts}"

    return round(min(score, 1.0), 3), comment


def score_confidence_calibration(state: "PipelineState") -> tuple[float, str]:
    """
    Score 0-1: how well-calibrated is the confidence score?

    A well-calibrated system gives low confidence when data is poor
    and high confidence when data is rich. We compare:
      - confidence_score (0-10) vs source_coverage score (0-1)
    Ideal: they should be correlated. Large gaps = poor calibration.
    """
    if state.confidence_score == 0:
        return 0.5, "No confidence score computed"

    # Normalize confidence to 0-1
    norm_confidence = state.confidence_score / 10.0

    # Get source coverage as a proxy for "should-be" confidence
    source_score, _ = score_source_coverage(state)

    # Calibration = how close are they? Perfect = 0 difference
    gap = abs(norm_confidence - source_score)

    # Score: 1.0 when gap=0, 0.0 when gap=1.0
    score = max(0.0, 1.0 - gap * 2)  # 2x penalty factor

    comment = (
        f"Confidence: {state.confidence_score}/10 ({norm_confidence:.2f}), "
        f"data quality: {source_score:.2f}, gap: {gap:.2f}"
    )

    return round(score, 3), comment


def score_latency(state: "PipelineState") -> tuple[float, str]:
    """
    Score 0-1: pipeline execution speed.

    Target: <60s=1.0, 60-120s=0.5, >120s linearly decreasing to 0.
    """
    duration = state.total_duration_seconds

    if duration <= 60:
        score = 1.0
    elif duration <= 120:
        score = 0.5 + 0.5 * (120 - duration) / 60
    else:
        score = max(0.0, 0.5 * (300 - duration) / 180)

    comment = f"Duration: {duration:.1f}s"
    return round(score, 3), comment


def score_prediction_quality(state: "PipelineState") -> tuple[float, str]:
    """
    Score 0-1: quality of price predictions.

    Checks:
      - Predictions exist for tracked tickers (coverage)
      - Predictions have reasoning and risk factors (completeness)
      - Direction is specified (actionability)

    NOTE: Actual accuracy (predicted vs real) is scored separately
    when predictions are checked 1 week later via score_prediction_accuracy().
    """
    if not state.ai_predictions:
        return 0.0, "No predictions generated"

    n_tickers = len(state.sector_tickers) or 1
    coverage = min(len(state.ai_predictions) / n_tickers, 1.0)

    completeness_scores = []
    for pred in state.ai_predictions:
        parts = 0
        if pred.get("direction"):
            parts += 1
        if pred.get("reasoning"):
            parts += 1
        if pred.get("key_risk"):
            parts += 1
        if pred.get("predicted_change"):
            parts += 1
        completeness_scores.append(parts / 4)

    avg_completeness = sum(completeness_scores) / len(completeness_scores)

    # Weighted: 40% coverage, 60% completeness
    score = 0.4 * coverage + 0.6 * avg_completeness

    comment = (
        f"{len(state.ai_predictions)} predictions, "
        f"coverage={coverage:.0%}, completeness={avg_completeness:.0%}"
    )

    return round(score, 3), comment


# ── Main entry point: push ALL scores to Langfuse ────────────────

def push_scores_to_langfuse(state: "PipelineState") -> dict[str, float]:
    """
    Compute and push all evaluation scores to the Langfuse trace.

    Called automatically after each pipeline run completes.
    Returns a dict of {score_name: score_value} for local use.

    Each score is pushed as a Langfuse score with:
      - name: the dimension name (e.g. "numerical_accuracy")
      - value: float 0-1 (higher = better)
      - comment: human-readable explanation
      - trace_id: links to the sector-level trace
    """
    from config.settings import LANGFUSE_ENABLED

    # Compute all scores regardless of Langfuse status
    scorers = {
        "numerical_accuracy": score_numerical_accuracy,
        "validation_quality": score_validation_quality,
        "analysis_completeness": score_analysis_completeness,
        "source_coverage": score_source_coverage,
        "confidence_calibration": score_confidence_calibration,
        "latency": score_latency,
        "prediction_quality": score_prediction_quality,
    }

    results: dict[str, float] = {}
    score_details: list[tuple[str, float, str]] = []

    for name, scorer in scorers.items():
        try:
            value, comment = scorer(state)
            results[name] = value
            score_details.append((name, value, comment))
        except Exception as e:
            logger.warning("Scorer '%s' failed: %s", name, e)
            results[name] = 0.0
            score_details.append((name, 0.0, f"Error: {e}"))

    # Compute aggregate
    if results:
        aggregate = sum(results.values()) / len(results)
        results["overall"] = round(aggregate, 3)
        score_details.append(("overall", aggregate, "Weighted average of all dimensions"))

    # Push to Langfuse if enabled and trace exists
    if LANGFUSE_ENABLED and state.langfuse_trace_id:
        try:
            from langfuse import Langfuse
            lf = Langfuse()

            for name, value, comment in score_details:
                lf.create_score(
                    trace_id=state.langfuse_trace_id,
                    name=name,
                    value=value,
                    comment=comment,
                    data_type="NUMERIC",
                )

            lf.flush()
            logger.info(
                "Pushed %d eval scores to Langfuse trace %s (overall=%.2f)",
                len(score_details), state.langfuse_trace_id[:8], results.get("overall", 0),
            )
        except Exception as e:
            logger.warning("Failed to push eval scores to Langfuse: %s", e)

    return results


# ── Prediction accuracy scorer (called when actuals come in) ──────

def score_prediction_accuracy(
    trace_id: str,
    predictions: list[dict],
    actuals: dict[str, float],
) -> tuple[float, str]:
    """
    Score prediction directional accuracy. Called when check_old_predictions()
    fetches actual prices and can push the result to the original trace.

    Args:
        trace_id: The Langfuse trace_id of the original pipeline run
        predictions: List of prediction dicts with 'ticker', 'direction', 'price_at_report'
        actuals: Dict of ticker -> actual_price_now

    Returns:
        (score, comment) tuple. Score is fraction of correct directional calls.
    """
    from config.settings import LANGFUSE_ENABLED

    correct = 0
    total = 0

    for pred in predictions:
        ticker = pred.get("ticker")
        direction = pred.get("ai_direction", pred.get("direction", "")).upper()
        price_at_report = pred.get("price_at_report")

        if not ticker or not direction or not price_at_report:
            continue
        if ticker not in actuals:
            continue

        actual_price = actuals[ticker]
        actual_change = ((actual_price - price_at_report) / price_at_report) * 100
        total += 1

        if direction == "BULLISH" and actual_change > 0:
            correct += 1
        elif direction == "BEARISH" and actual_change < 0:
            correct += 1
        elif direction == "NEUTRAL" and abs(actual_change) < 2:
            correct += 1

    if total == 0:
        return 0.5, "No predictions to verify"

    score = correct / total
    comment = f"{correct}/{total} directional predictions correct"

    # Push to Langfuse
    if LANGFUSE_ENABLED and trace_id:
        try:
            from langfuse import Langfuse
            lf = Langfuse()
            lf.create_score(
                trace_id=trace_id,
                name="prediction_accuracy",
                value=score,
                comment=comment,
                data_type="NUMERIC",
            )
            lf.flush()
            logger.info("Pushed prediction_accuracy=%.2f to trace %s", score, trace_id[:8])
        except Exception as e:
            logger.warning("Failed to push prediction_accuracy score: %s", e)

    return round(score, 3), comment
