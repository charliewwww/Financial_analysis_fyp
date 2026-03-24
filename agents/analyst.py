"""
Analyst Agent — the brain of the system.

Takes sector data (news, prices, filings, technicals, supply chain map) and produces
a structured analysis report using second-order supply-chain reasoning.

ARCHITECTURE NOTE:
    The full analysis pipeline runs via LangGraph nodes (see workflows/nodes.py).
    This module exposes a standalone `analyze_sector()` convenience function
    for direct use outside the pipeline (e.g., CLI one-off analysis, testing).
    The pipeline's analyze_node calls llm_client.call_llm directly for richer
    state management (RAG context, macro injection, token tracking).
"""

import logging
from agents.llm_client import call_llm
from utils.prompts import SYSTEM_PROMPT_ANALYST, build_analysis_prompt

logger = logging.getLogger(__name__)


def analyze_sector(
    sector: dict,
    news: list[dict],
    prices: list[dict],
    filings: list[dict],
    technicals: list[dict] | None = None,
) -> str:
    """
    Run a standalone analysis for a sector (outside the full pipeline).

    For the full LangGraph pipeline with RAG, macro, validation loops, etc.,
    use workflows.weekly_analysis.run_sector_analysis() instead.

    Args:
        sector: Sector definition from config/sectors.py
        news: List of relevant news articles (from RSS fetcher)
        prices: List of stock snapshots (from Yahoo Finance)
        filings: List of SEC filing references
        technicals: List of technical analysis dicts (RSI, MACD, etc.)

    Returns:
        The full analysis report as a Markdown string
    """
    logger.info("Standalone analysis: %s", sector['name'])

    prompt = build_analysis_prompt(sector, news, prices, filings, technicals)

    analysis = call_llm(
        prompt=prompt,
        system_prompt=SYSTEM_PROMPT_ANALYST,
        temperature=0.3,
        max_tokens=4096,
    )

    return analysis
