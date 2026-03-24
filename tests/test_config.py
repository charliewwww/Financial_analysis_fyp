"""
Tests for config/settings.py — environment variable loading and defaults.

Uses monkeypatch to simulate different .env configurations.
"""

import pytest


class TestSettingsDefaults:
    """Test that settings have correct defaults when env vars are missing."""

    def test_reasoning_model_exists(self):
        from config.settings import REASONING_MODEL
        assert isinstance(REASONING_MODEL, str)
        assert len(REASONING_MODEL) > 0

    def test_fast_model_exists(self):
        from config.settings import FAST_MODEL
        assert isinstance(FAST_MODEL, str)
        assert len(FAST_MODEL) > 0

    def test_max_prompt_chars(self):
        from config.settings import MAX_PROMPT_CHARS
        assert isinstance(MAX_PROMPT_CHARS, int)
        assert MAX_PROMPT_CHARS > 1000

    def test_numerical_tolerance(self):
        from config.settings import NUMERICAL_TOLERANCE_PCT
        assert isinstance(NUMERICAL_TOLERANCE_PCT, (int, float))
        assert 0 < NUMERICAL_TOLERANCE_PCT < 100

    def test_max_articles_per_feed(self):
        from config.settings import MAX_ARTICLES_PER_FEED
        assert isinstance(MAX_ARTICLES_PER_FEED, int)
        assert MAX_ARTICLES_PER_FEED >= 1

    def test_llm_provider_valid(self):
        from config.settings import LLM_PROVIDER
        assert LLM_PROVIDER in ("openrouter", "ollama")

    def test_llm_base_url_set(self):
        from config.settings import LLM_BASE_URL
        assert isinstance(LLM_BASE_URL, str)
        assert LLM_BASE_URL.startswith("http")


class TestSectorConfig:
    """Test that sector configuration is complete and valid."""

    def test_sectors_not_empty(self):
        from config.sectors import SECTORS
        assert len(SECTORS) >= 1

    def test_sector_required_keys(self):
        from config.sectors import SECTORS
        required = {"name", "description", "tickers", "keywords", "supply_chain_map"}
        for sid, sector in SECTORS.items():
            missing = required - set(sector.keys())
            assert not missing, f"Sector '{sid}' missing keys: {missing}"

    def test_sector_tickers_are_strings(self):
        from config.sectors import SECTORS
        for sid, sector in SECTORS.items():
            for ticker in sector["tickers"]:
                assert isinstance(ticker, str), f"Sector '{sid}' has non-string ticker: {ticker}"
                assert ticker == ticker.upper(), f"Sector '{sid}' has lowercase ticker: {ticker}"

    def test_supply_chain_map_has_roles(self):
        from config.sectors import SECTORS
        for sid, sector in SECTORS.items():
            for company, info in sector["supply_chain_map"].items():
                assert "role" in info, \
                    f"Sector '{sid}', company '{company}' missing 'role' in supply_chain_map"
