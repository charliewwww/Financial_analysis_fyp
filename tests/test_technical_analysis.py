"""
Tests for data_sources/technical_analysis.py — with mocked price data.

No real API calls — price history is generated synthetically.
"""

import pytest
import pandas as pd
import numpy as np
from unittest.mock import patch
from datetime import datetime


def _mock_price_history(days: int = 250, base: float = 100.0) -> pd.DataFrame:
    """Generate a realistic mock OHLCV DataFrame."""
    np.random.seed(42)
    dates = pd.date_range(end=datetime.now(), periods=days, freq="B")
    close = base + np.cumsum(np.random.randn(days) * 1.5)
    volume = np.random.randint(500_000, 5_000_000, size=days).astype(float)
    return pd.DataFrame({
        "Open": close - 0.5,
        "High": close + 1.0,
        "Low": close - 1.0,
        "Close": close,
        "Volume": volume,
    }, index=dates)


class TestComputeTechnicals:
    @patch("data_sources.technical_analysis.get_price_history")
    def test_full_indicator_set(self, mock_hist):
        """Should compute all technical indicators with sufficient data."""
        from data_sources.technical_analysis import compute_technicals

        mock_hist.return_value = _mock_price_history(250)

        result = compute_technicals("NVDA")
        assert result["ticker"] == "NVDA"
        assert result["error"] is None

        # All key indicators should be present
        assert isinstance(result["rsi_14"], float)
        assert 0 <= result["rsi_14"] <= 100
        assert result["macd_line"] is not None
        assert result["macd_signal"] is not None
        assert isinstance(result["macd_bullish"], bool)
        assert result["bb_upper"] is not None
        assert result["bb_lower"] is not None
        assert 0 <= result["bb_position"] <= 1.5  # can slightly exceed 1.0
        assert result["sma_20"] is not None
        assert result["sma_50"] is not None
        assert isinstance(result["above_sma_20"], bool)
        assert isinstance(result["above_sma_50"], bool)
        assert result["volume_ratio"] is not None
        assert result["summary"]  # should be non-empty

    @patch("data_sources.technical_analysis.get_price_history")
    def test_insufficient_data(self, mock_hist):
        """Should return error when not enough price history."""
        from data_sources.technical_analysis import compute_technicals

        mock_hist.return_value = _mock_price_history(10)

        result = compute_technicals("SHORT")
        assert result["ticker"] == "SHORT"
        assert result["error"] is not None
        assert "Insufficient" in result["error"]

    @patch("data_sources.technical_analysis.get_price_history")
    def test_empty_dataframe(self, mock_hist):
        """Should handle empty DataFrame gracefully."""
        from data_sources.technical_analysis import compute_technicals

        mock_hist.return_value = pd.DataFrame()

        result = compute_technicals("EMPTY")
        assert result["error"] is not None

    @patch("data_sources.technical_analysis.get_price_history")
    def test_sma_50_none_with_short_data(self, mock_hist):
        """SMA-50 should be None with < 50 data points."""
        from data_sources.technical_analysis import compute_technicals

        mock_hist.return_value = _mock_price_history(40)

        result = compute_technicals("SHORT50")
        assert result["sma_50"] is None
        assert result["above_sma_50"] is None

    @patch("data_sources.technical_analysis.get_price_history")
    def test_momentum_calculations(self, mock_hist):
        """5d/10d/20d momentum should be calculated."""
        from data_sources.technical_analysis import compute_technicals

        mock_hist.return_value = _mock_price_history(60)

        result = compute_technicals("MOM")
        assert result["change_5d_pct"] is not None
        assert result["change_10d_pct"] is not None
        assert result["change_20d_pct"] is not None


class TestComputeSectorTechnicals:
    @patch("data_sources.technical_analysis.compute_technicals")
    def test_returns_ordered_results(self, mock_compute):
        """Should return results in the same order as input tickers."""
        from data_sources.technical_analysis import compute_sector_technicals

        def fake_compute(ticker):
            return {"ticker": ticker, "error": None, "rsi_14": 50.0}

        mock_compute.side_effect = fake_compute

        result = compute_sector_technicals(["NVDA", "AMD", "AVGO"])
        assert len(result) == 3
        assert result[0]["ticker"] == "NVDA"
        assert result[1]["ticker"] == "AMD"
        assert result[2]["ticker"] == "AVGO"

    def test_empty_tickers(self):
        """Should return empty list for empty input."""
        from data_sources.technical_analysis import compute_sector_technicals

        assert compute_sector_technicals([]) == []

    @patch("data_sources.technical_analysis.compute_technicals")
    def test_handles_individual_failures(self, mock_compute):
        """Should not crash if one ticker fails."""
        from data_sources.technical_analysis import compute_sector_technicals

        call_count = [0]

        def alternating_compute(ticker):
            call_count[0] += 1
            if ticker == "FAIL":
                raise Exception("API error")
            return {"ticker": ticker, "error": None}

        mock_compute.side_effect = alternating_compute

        result = compute_sector_technicals(["NVDA", "FAIL", "AMD"])
        assert len(result) == 3
        assert result[1]["ticker"] == "FAIL"
        assert result[1]["error"] is not None


class TestRSI:
    def test_rsi_range(self):
        """RSI should always be between 0 and 100."""
        from data_sources.technical_analysis import _compute_rsi

        np.random.seed(0)
        # Trending up strongly
        up = pd.Series(range(100, 200))
        rsi = _compute_rsi(up, 14)
        assert rsi is not None
        assert 0 <= rsi <= 100

        # Trending down strongly
        down = pd.Series(range(200, 100, -1))
        rsi = _compute_rsi(down, 14)
        assert rsi is not None
        assert 0 <= rsi <= 100

    def test_insufficient_data(self):
        """RSI should return None with too few data points."""
        from data_sources.technical_analysis import _compute_rsi

        short = pd.Series([100, 101, 102])
        assert _compute_rsi(short, 14) is None


class TestMACD:
    def test_returns_all_fields(self):
        """MACD should return line, signal, histogram, and bullish flag."""
        from data_sources.technical_analysis import _compute_macd

        close = pd.Series(np.random.randn(60).cumsum() + 100)
        result = _compute_macd(close)
        assert "macd_line" in result
        assert "macd_signal" in result
        assert "macd_histogram" in result
        assert "macd_bullish" in result
        assert isinstance(result["macd_bullish"], bool)

    def test_insufficient_data(self):
        """Should return None values with < 26 data points."""
        from data_sources.technical_analysis import _compute_macd

        short = pd.Series([100 + i for i in range(10)])
        result = _compute_macd(short)
        assert result["macd_line"] is None


class TestBollinger:
    def test_position_range(self):
        """Bollinger position should be between 0 and ~1."""
        from data_sources.technical_analysis import _compute_bollinger

        close = pd.Series(np.random.randn(50).cumsum() + 100)
        result = _compute_bollinger(close)
        assert result["bb_position"] is not None
        assert result["bb_upper"] > result["bb_lower"]
