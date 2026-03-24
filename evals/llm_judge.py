"""
LLM-as-Judge Evaluator — use a second LLM call to grade analysis quality.

This is the "gold standard" evaluation approach in MLOps:
    1. The pipeline LLM generates an analysis
    2. A SEPARATE LLM call evaluates the analysis along specific dimensions
    3. Scores are pushed to Langfuse for tracking

Evaluation dimensions:
    - Reasoning depth:     Does the analysis go beyond surface-level observations?
    - Supply chain insight: Does it identify 2nd/3rd order effects?
    - Evidence grounding:  Are claims backed by cited sources?
    - Risk awareness:      Are risks specific and non-generic?
    - Actionability:       Could a portfolio manager act on this?

Each dimension is scored 1-5 by the judge LLM. Scores are normalized to 0-1
and pushed to Langfuse alongside the programmatic scores from scoring.py.

The judge uses a structured rubric to ensure consistent, reproducible scoring.
"""

from __future__ import annotations

import json
import logging
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from models.state import PipelineState

logger = logging.getLogger(__name__)


# ── Judge System Prompt ───────────────────────────────────────────

JUDGE_SYSTEM_PROMPT = """\
You are an expert financial analysis quality evaluator. Your job is to
objectively grade the quality of an AI-generated equity sector analysis.

You will score the analysis on 5 dimensions, each on a 1-5 scale:

## SCORING RUBRIC

### 1. Reasoning Depth (1-5)
1 = Merely restates news headlines with no interpretation
2 = Basic cause-effect but only surface level
3 = Connects multiple data points with clear logic
4 = Identifies non-obvious implications and trends
5 = Exceptional multi-step reasoning with quantitative support

### 2. Supply Chain Insight (1-5)
1 = No supply chain analysis at all
2 = Mentions suppliers/customers but no depth
3 = Identifies 2nd-order supply chain effects
4 = Maps upstream+downstream impacts with specifics
5 = Reveals non-obvious cross-sector dependencies with evidence

### 3. Evidence Grounding (1-5)
1 = No sources cited, claims are unverifiable
2 = Few sources, many ungrounded claims
3 = Most claims have [SOURCE: ...] tags
4 = All major claims cited, data points reference real numbers
5 = Comprehensive sourcing with cross-referenced data points

### 4. Risk Awareness (1-5)
1 = No risks mentioned
2 = Generic risks ("market volatility", "competition")
3 = Sector-specific risks with some detail
4 = Well-articulated risks with probability/impact assessment
5 = Nuanced risk matrix with catalysts and hedging considerations

### 5. Actionability (1-5)
1 = Vague commentary, no investment implications
2 = General directional view but no specifics
3 = Clear bull/bear thesis with price targets
4 = Specific entry points, catalysts, and timeframes
5 = Portfolio-manager-ready with position sizing considerations

## OUTPUT FORMAT

You MUST respond with ONLY a valid JSON object, no other text:

{
    "reasoning_depth": {"score": <1-5>, "justification": "<1 sentence>"},
    "supply_chain_insight": {"score": <1-5>, "justification": "<1 sentence>"},
    "evidence_grounding": {"score": <1-5>, "justification": "<1 sentence>"},
    "risk_awareness": {"score": <1-5>, "justification": "<1 sentence>"},
    "actionability": {"score": <1-5>, "justification": "<1 sentence>"},
    "overall_comment": "<1 sentence overall assessment>"
}
"""


def _build_judge_prompt(state: "PipelineState") -> str:
    """
    Build the evaluation prompt for the LLM judge.

    Includes the analysis text and key context (sector, tickers, data availability)
    so the judge can assess quality relative to what data was available.
    """
    data_summary = (
        f"Data available to the analyst:\n"
        f"- News articles: {len(state.articles)}\n"
        f"- Price data: {len(state.prices)} tickers\n"
        f"- Technical indicators: {len(state.technicals)} tickers\n"
        f"- SEC filings: {len(state.filings)}\n"
        f"- Macro data: {'available' if state.macro_data.get('_meta', {}).get('api_status') == 'ok' else 'unavailable'}\n"
        f"- Data sufficiency verdict: {state.data_sufficiency}\n"
    )

    return (
        f"## SECTOR: {state.sector_name}\n"
        f"## TICKERS: {', '.join(state.sector_tickers)}\n\n"
        f"{data_summary}\n"
        f"---\n\n"
        f"## ANALYSIS TO EVALUATE:\n\n"
        f"{state.analysis_text}\n"
    )


def run_llm_judge(state: "PipelineState") -> dict[str, float]:
    """
    Run the LLM-as-Judge evaluation on a completed pipeline state.

    Makes ONE additional LLM call to grade the analysis quality.
    Scores are normalized to 0-1 and pushed to Langfuse.

    Returns:
        Dict of {dimension_name: normalized_score (0-1)}
    """
    from config.settings import LANGFUSE_ENABLED

    if not state.analysis_text:
        logger.warning("No analysis text to evaluate")
        return {}

    prompt = _build_judge_prompt(state)

    # Use the fast model for evaluation (cheaper, faster)
    try:
        from agents.llm_client import call_llm_fast

        # Build Langfuse kwargs for the judge call
        lf_kwargs = {}
        if LANGFUSE_ENABLED and state.langfuse_trace_id:
            lf_kwargs = {
                "langfuse_name": f"llm_judge — {state.sector_name}",
                "langfuse_metadata": {
                    "sector_id": state.sector_id,
                    "node": "llm_judge",
                    "eval_type": "llm_as_judge",
                },
                "langfuse_trace_id": state.langfuse_trace_id,
            }

        response = call_llm_fast(
            prompt=prompt,
            system_prompt=JUDGE_SYSTEM_PROMPT,
            temperature=0.0,  # Deterministic judging
            max_tokens=1024,
            **lf_kwargs,
        )
    except Exception as e:
        logger.error("LLM judge call failed: %s", e)
        return {}

    # Parse the JSON response
    scores = _parse_judge_response(response)
    if not scores:
        logger.warning("Failed to parse LLM judge response")
        return {}

    # Normalize 1-5 scores to 0-1
    normalized: dict[str, float] = {}
    comments: dict[str, str] = {}

    for dim, data in scores.items():
        if dim == "overall_comment":
            continue
        raw_score = data.get("score", 3)
        justification = data.get("justification", "")
        normalized[f"judge_{dim}"] = round((raw_score - 1) / 4, 3)  # Map 1-5 → 0-1
        comments[f"judge_{dim}"] = f"[{raw_score}/5] {justification}"

    # Compute judge aggregate
    if normalized:
        avg = sum(normalized.values()) / len(normalized)
        normalized["judge_overall"] = round(avg, 3)
        overall_comment = scores.get("overall_comment", "")
        comments["judge_overall"] = f"[{avg:.2f}] {overall_comment}"

    # Push to Langfuse
    if LANGFUSE_ENABLED and state.langfuse_trace_id:
        try:
            from langfuse import Langfuse
            lf = Langfuse()

            for name, value in normalized.items():
                lf.create_score(
                    trace_id=state.langfuse_trace_id,
                    name=name,
                    value=value,
                    comment=comments.get(name, ""),
                    data_type="NUMERIC",
                )

            lf.flush()
            logger.info(
                "Pushed %d judge scores to Langfuse (overall=%.2f)",
                len(normalized), normalized.get("judge_overall", 0),
            )
        except Exception as e:
            logger.warning("Failed to push judge scores to Langfuse: %s", e)

    return normalized


def _parse_judge_response(response: str) -> dict | None:
    """
    Parse the LLM judge's JSON response.

    Handles common LLM output issues:
      - Markdown code blocks around JSON
      - Trailing/leading text
      - Minor JSON formatting errors
    """
    if not response:
        return None

    # Strip markdown code fences
    text = response.strip()
    text = re.sub(r'^```(?:json)?\s*', '', text)
    text = re.sub(r'\s*```$', '', text)

    # Try to find JSON object in the response
    # Look for first { and last }
    start = text.find("{")
    end = text.rfind("}")

    if start == -1 or end == -1 or end <= start:
        logger.warning("No JSON object found in judge response")
        return None

    json_str = text[start:end + 1]

    try:
        parsed = json.loads(json_str)
        # Validate expected structure
        expected_dims = [
            "reasoning_depth", "supply_chain_insight",
            "evidence_grounding", "risk_awareness", "actionability",
        ]
        for dim in expected_dims:
            if dim not in parsed:
                logger.warning("Missing dimension '%s' in judge response", dim)
                parsed[dim] = {"score": 3, "justification": "Not evaluated"}
            elif not isinstance(parsed[dim], dict):
                parsed[dim] = {"score": parsed[dim], "justification": ""}

        return parsed

    except json.JSONDecodeError as e:
        logger.warning("Failed to parse judge JSON: %s", e)
        return None
