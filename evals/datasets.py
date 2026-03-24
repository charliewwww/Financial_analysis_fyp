"""
Evaluation Datasets — golden test cases for regression testing.

Provides curated sector scenarios with known-good expected outputs.
Used by the evaluation runner to test the pipeline against a fixed
benchmark and detect quality regressions.

Dataset structure:
    Each test case = (sector_config, expected_properties)
    - sector_config: Same format as SECTORS dict entries
    - expected_properties: What the output SHOULD look like
      (sections present, predictions exist, confidence range, etc.)

Datasets are stored in-memory (small) but can be extended to Langfuse
datasets via the Langfuse SDK for versioned management.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class EvalExpectation:
    """What we expect from a good pipeline run."""
    min_confidence: float = 3.0             # Minimum acceptable confidence score
    max_confidence: float = 10.0            # Maximum expected
    required_sections: list[str] = field(default_factory=lambda: [
        "THESIS", "KEY DEVELOPMENTS", "RISK", "PRICE PREDICTION",
    ])
    min_predictions: int = 1                # At least N predictions
    must_pass_validation: bool = False      # Validation must PASS (not FAILED)
    must_have_sources: bool = True          # Analysis must cite sources
    max_duration_seconds: float = 300.0     # Timeout threshold
    min_articles: int = 1                   # Minimum fetched articles
    description: str = ""                   # What this test case specifically checks


@dataclass
class EvalCase:
    """A single evaluation test case."""
    case_id: str
    sector_id: str
    sector_config: dict
    expectations: EvalExpectation
    tags: list[str] = field(default_factory=list)


@dataclass
class EvalResult:
    """Result of evaluating one test case."""
    case_id: str
    passed: bool
    checks: dict[str, bool]                 # {check_name: pass/fail}
    details: dict[str, str]                 # {check_name: explanation}
    scores: dict[str, float]                # Scores from scoring.py
    judge_scores: dict[str, float]          # Scores from llm_judge.py
    duration_seconds: float = 0.0


# ── Built-in Evaluation Dataset ──────────────────────────────────

def get_default_dataset() -> list[EvalCase]:
    """
    Default evaluation dataset with representative sector scenarios.

    Covers:
      - High-data sector (lots of news, all data sources)
      - Low-data sector (minimal coverage)
      - Volatile sector (many anomalies expected)
    """
    return [
        EvalCase(
            case_id="eval_high_data_semis",
            sector_id="ai_semiconductors",
            sector_config={
                "name": "AI & Semiconductors",
                "description": "Companies designing GPUs, AI accelerators, and semiconductor equipment",
                "tickers": ["NVDA", "TSM", "AMD"],
                "keywords": ["ai", "semiconductor", "gpu", "nvidia", "chip"],
                "supply_chain_map": {
                    "NVDA": {"role": "GPU designer", "upstream": ["TSM"], "downstream": ["MSFT", "GOOG"]},
                    "TSM": {"role": "Foundry", "upstream": ["ASML"], "downstream": ["NVDA", "AMD"]},
                    "AMD": {"role": "CPU/GPU designer", "upstream": ["TSM"], "downstream": ["MSFT"]},
                },
            },
            expectations=EvalExpectation(
                min_confidence=5.0,
                min_predictions=2,
                must_pass_validation=True,
                min_articles=3,
                description="High-coverage sector — should produce a thorough, well-sourced analysis",
            ),
            tags=["high-data", "flagship"],
        ),
        EvalCase(
            case_id="eval_completeness_check",
            sector_id="ai_semiconductors",
            sector_config={
                "name": "AI & Semiconductors",
                "description": "Companies designing GPUs and AI chips",
                "tickers": ["NVDA"],
                "keywords": ["nvidia", "gpu"],
                "supply_chain_map": {},
            },
            expectations=EvalExpectation(
                min_confidence=2.0,
                required_sections=["THESIS", "PRICE PREDICTION", "RISK"],
                min_predictions=1,
                must_pass_validation=False,
                min_articles=1,
                description="Single-ticker run — checks analysis completeness with minimal data",
            ),
            tags=["minimal", "completeness"],
        ),
    ]


def evaluate_result(
    case: EvalCase,
    state: "Any",  # PipelineState — avoiding circular import
    scores: dict[str, float],
    judge_scores: dict[str, float],
    duration: float,
) -> EvalResult:
    """
    Check a pipeline result against the test case expectations.

    Returns an EvalResult with pass/fail for each check.
    """
    exp = case.expectations
    checks: dict[str, bool] = {}
    details: dict[str, str] = {}

    # 1. Confidence range
    conf = state.confidence_score
    checks["confidence_in_range"] = exp.min_confidence <= conf <= exp.max_confidence
    details["confidence_in_range"] = f"{conf:.1f} (expected {exp.min_confidence}-{exp.max_confidence})"

    # 2. Required sections
    text_upper = (state.analysis_text or "").upper()
    missing = [s for s in exp.required_sections if s.upper() not in text_upper]
    checks["required_sections"] = len(missing) == 0
    details["required_sections"] = f"Missing: {missing}" if missing else "All present"

    # 3. Predictions
    n_preds = len(state.ai_predictions)
    checks["min_predictions"] = n_preds >= exp.min_predictions
    details["min_predictions"] = f"{n_preds} predictions (min={exp.min_predictions})"

    # 4. Validation
    if exp.must_pass_validation:
        checks["validation_passed"] = state.validation_status != "FAILED"
        details["validation_passed"] = f"Status: {state.validation_status}"
    else:
        checks["validation_passed"] = True
        details["validation_passed"] = "Not required"

    # 5. Source citations
    if exp.must_have_sources:
        has_sources = "[SOURCE" in (state.analysis_text or "").upper() or "SOURCE:" in (state.analysis_text or "").upper()
        checks["has_sources"] = has_sources
        details["has_sources"] = "Citations found" if has_sources else "No [SOURCE:] tags"
    else:
        checks["has_sources"] = True
        details["has_sources"] = "Not required"

    # 6. Duration
    checks["within_timeout"] = duration <= exp.max_duration_seconds
    details["within_timeout"] = f"{duration:.1f}s (max={exp.max_duration_seconds}s)"

    # 7. Articles fetched
    n_articles = len(state.articles)
    checks["min_articles"] = n_articles >= exp.min_articles
    details["min_articles"] = f"{n_articles} articles (min={exp.min_articles})"

    # 8. Pipeline completed
    checks["pipeline_completed"] = state.pipeline_status == "completed"
    details["pipeline_completed"] = f"Status: {state.pipeline_status}"

    passed = all(checks.values())

    return EvalResult(
        case_id=case.case_id,
        passed=passed,
        checks=checks,
        details=details,
        scores=scores,
        judge_scores=judge_scores,
        duration_seconds=duration,
    )


# ── Langfuse Dataset Integration ─────────────────────────────────

def sync_dataset_to_langfuse(dataset_name: str = "supply_chain_alpha_eval_v1"):
    """
    Create/update the evaluation dataset in Langfuse for versioned management.

    This allows you to:
      - View test cases in the Langfuse UI
      - Track which cases pass/fail over time
      - Share the dataset with your mentor
    """
    from config.settings import LANGFUSE_ENABLED

    if not LANGFUSE_ENABLED:
        logger.warning("Langfuse disabled — cannot sync dataset")
        return

    try:
        from langfuse import Langfuse
        lf = Langfuse()

        # Create dataset (idempotent)
        dataset = lf.create_dataset(
            name=dataset_name,
            description=(
                "Evaluation dataset for Supply Chain Alpha pipeline. "
                "Tests analysis quality across different sector scenarios."
            ),
        )

        # Add eval cases as dataset items
        for case in get_default_dataset():
            lf.create_dataset_item(
                dataset_name=dataset_name,
                input={
                    "sector_id": case.sector_id,
                    "sector_config": case.sector_config,
                },
                expected_output={
                    "min_confidence": case.expectations.min_confidence,
                    "required_sections": case.expectations.required_sections,
                    "min_predictions": case.expectations.min_predictions,
                    "must_pass_validation": case.expectations.must_pass_validation,
                    "description": case.expectations.description,
                },
                metadata={
                    "case_id": case.case_id,
                    "tags": case.tags,
                },
            )

        lf.flush()
        logger.info("Synced %d eval cases to Langfuse dataset '%s'",
                     len(get_default_dataset()), dataset_name)

    except Exception as e:
        logger.error("Failed to sync dataset to Langfuse: %s", e)
