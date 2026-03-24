"""
Validator Agent — checks the analysis for factual accuracy.

Compares numerical claims in the report against real stock data.
This is the LLM-based layer of the anti-hallucination pipeline.

ARCHITECTURE NOTE:
    The full validation pipeline runs via LangGraph nodes (see workflows/nodes.py),
    which performs BOTH programmatic numerical checks (Layer 3) AND LLM reasoning
    checks (this layer). This module exposes a standalone `validate_analysis()`
    convenience function for direct use outside the pipeline (e.g., testing).
"""

import logging
from agents.llm_client import call_llm
from utils.prompts import SYSTEM_PROMPT_VALIDATOR, build_validation_prompt

logger = logging.getLogger(__name__)


def validate_analysis(analysis_text: str, prices: list[dict]) -> str:
    """
    Validate an analysis report against real data (standalone, outside pipeline).

    For the full LangGraph pipeline with programmatic + LLM validation and
    retry loops, use workflows.weekly_analysis.run_sector_analysis() instead.

    Args:
        analysis_text: The Markdown analysis report from the analyst
        prices: Real stock data from Yahoo Finance (used as ground truth)

    Returns:
        Validation report as a Markdown string
    """
    logger.info("Standalone validation: checking analysis against %d price snapshots", len(prices))

    prompt = build_validation_prompt(analysis_text, prices)

    validation = call_llm(
        prompt=prompt,
        system_prompt=SYSTEM_PROMPT_VALIDATOR,
        temperature=0.1,
        max_tokens=2048,
    )

    return validation
