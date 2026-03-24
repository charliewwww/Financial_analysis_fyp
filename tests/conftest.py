"""
Shared fixtures for the test suite.

All fixtures here are available to every test module automatically.
"""

import pytest
from models.state import PipelineState, Article, NodeExecution


# ── Factory helpers ──────────────────────────────────────────────

def _make_article(**overrides) -> Article:
    """Create a test Article with sensible defaults."""
    defaults = dict(
        title="NVIDIA beats earnings expectations",
        source="CNBC Top News",
        link="https://example.com/nvda",
        published="2024-01-15",
        raw_summary="NVIDIA reported Q4 revenue of $22B...",
        relevance_tag="ticker:NVDA",
    )
    defaults.update(overrides)
    return Article(**defaults)


def _make_price(ticker: str = "NVDA", price: float = 130.0, **overrides) -> dict:
    """Create a test price snapshot."""
    defaults = dict(
        ticker=ticker,
        price=price,
        market_cap=3.2e12,
        pe_ratio=65.3,
        day_change_pct=1.2,
        week_52_high=140.0,
        week_52_low=40.0,
        volume=45_000_000,
    )
    defaults.update(overrides)
    return defaults


def _make_technical(ticker: str = "NVDA", **overrides) -> dict:
    """Create a test technical indicators dict."""
    defaults = dict(
        ticker=ticker,
        rsi_14=62.5,
        macd=1.23,
        macd_signal=0.98,
        bollinger_upper=135.0,
        bollinger_lower=120.0,
        sma_50=125.0,
        sma_200=110.0,
        volume_zscore=0.5,
    )
    defaults.update(overrides)
    return defaults


# ── Fixtures ─────────────────────────────────────────────────────

@pytest.fixture
def sample_articles():
    """List of 10 diverse articles across sources."""
    sources = ["CNBC Top News", "Reuters", "MarketWatch", "Yahoo Finance",
               "Google News (NVDA)"]
    return [
        _make_article(
            title=f"Article {i} about semiconductors",
            source=sources[i % len(sources)],
        )
        for i in range(10)
    ]


@pytest.fixture
def sample_prices():
    """Price snapshots for 3 tickers."""
    return [
        _make_price("NVDA", 130.0),
        _make_price("TSM", 175.0, market_cap=900e9),
        _make_price("AMD", 165.0, market_cap=265e9),
    ]


@pytest.fixture
def sample_technicals():
    """Technicals for 3 tickers."""
    return [
        _make_technical("NVDA"),
        _make_technical("TSM", rsi_14=55.0),
        _make_technical("AMD", rsi_14=70.0),
    ]


@pytest.fixture
def populated_state(sample_articles, sample_prices, sample_technicals):
    """A PipelineState pre-filled with sample data (as if fetch_node ran)."""
    state = PipelineState.from_sector("ai_semiconductors", {
        "name": "AI & Semiconductors",
        "description": "Test sector",
        "tickers": ["NVDA", "TSM", "AMD"],
        "keywords": ["ai", "semiconductor", "gpu"],
        "supply_chain_map": {"NVDA": {"role": "GPU designer"}},
    })
    state.articles = sample_articles
    state.prices = sample_prices
    state.technicals = sample_technicals
    state.filings = []
    state.macro_data = {
        "_meta": {"api_status": "ok", "indicators_fetched": 6},
        "fed_funds_rate": {"value": 5.25, "name": "Federal Funds Rate"},
    }
    state.news_summary = "NVIDIA beat earnings. TSM raised guidance."
    state.analysis_text = "## AI & Semiconductors Analysis\nNVDA is strong."
    state.validation_status = "PASSED"
    return state
