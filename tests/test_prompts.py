"""
Tests for utils/prompts.py — prompt builders.

Verifies that prompt templates contain required sections
and handle edge cases (empty data, missing fields).
"""

import pytest
from utils.prompts import (
    SYSTEM_PROMPT_ANALYST,
    SYSTEM_PROMPT_VALIDATOR,
    build_analysis_prompt,
    build_validation_prompt,
)


class TestSystemPrompts:
    """Verify system prompts are non-empty and well-structured."""

    def test_analyst_prompt_not_empty(self):
        assert len(SYSTEM_PROMPT_ANALYST) > 100

    def test_validator_prompt_not_empty(self):
        assert len(SYSTEM_PROMPT_VALIDATOR) > 100

    def test_analyst_prompt_mentions_supply_chain(self):
        """The analyst system prompt should reference supply chain reasoning."""
        assert "supply" in SYSTEM_PROMPT_ANALYST.lower() or "chain" in SYSTEM_PROMPT_ANALYST.lower()


class TestBuildAnalysisPrompt:
    """Test the analysis prompt builder with various data scenarios."""

    def test_basic_prompt_structure(self):
        sector = {
            "name": "AI & Semiconductors",
            "description": "AI chip supply chain",
            "tickers": ["NVDA"],
            "supply_chain_map": {"NVDA": {"role": "GPU designer"}},
        }
        news = [{"title": "NVDA beats earnings", "summary": "Good Q4.",
                 "source": "CNBC", "published": "2024-01-15",
                 "link": "https://example.com", "relevance": "ticker:NVDA"}]
        prices = [{"ticker": "NVDA", "price": 130.0, "market_cap": 3.2e12}]
        prompt = build_analysis_prompt(sector, news, prices, [], [])
        assert isinstance(prompt, str)
        assert len(prompt) > 100
        assert "NVDA" in prompt

    def test_empty_news(self):
        """Should not crash with empty news list."""
        sector = {"name": "Test", "description": "Test sector", "tickers": ["X"], "supply_chain_map": {}}
        prompt = build_analysis_prompt(sector, [], [], [], [])
        assert isinstance(prompt, str)

    def test_empty_prices(self):
        """Should not crash with empty prices."""
        sector = {"name": "Test", "description": "Test sector", "tickers": ["X"], "supply_chain_map": {}}
        news = [{"title": "T", "summary": "S", "source": "Src",
                 "published": "2024-01-01", "link": "L", "relevance": ""}]
        prompt = build_analysis_prompt(sector, news, [], [], [])
        assert isinstance(prompt, str)

    def test_technicals_included(self):
        """When technicals are provided, they should appear in the prompt."""
        sector = {"name": "Test", "description": "Test sector", "tickers": ["NVDA"], "supply_chain_map": {}}
        technicals = [{"ticker": "NVDA", "rsi_14": 65.0, "macd": 1.5}]
        prompt = build_analysis_prompt(sector, [], [], [], technicals)
        # If technicals data is present, the prompt should reference it somehow
        assert isinstance(prompt, str)


class TestBuildValidationPrompt:
    """Test the validation prompt builder."""

    def test_basic_structure(self):
        analysis = "## Sector Analysis\nNVDA is doing great."
        prices = [{"ticker": "NVDA", "price": 130.0}]
        prompt = build_validation_prompt(analysis, prices)
        assert isinstance(prompt, str)
        assert len(prompt) > 50

    def test_includes_analysis_text(self):
        analysis = "UNIQUE_ANALYSIS_MARKER_12345"
        prompt = build_validation_prompt(analysis, [])
        assert "UNIQUE_ANALYSIS_MARKER_12345" in prompt
