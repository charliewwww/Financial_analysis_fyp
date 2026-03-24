"""
Tests for data_sources/yahoo_finance.py — with mocked yfinance.

No real API calls — all yfinance interactions are mocked.
"""

import pytest
import pandas as pd
import numpy as np
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta


def _mock_hist(days: int = 60, base_price: float = 150.0) -> pd.DataFrame:
    """Create a realistic mock price history DataFrame."""
    dates = pd.date_range(end=datetime.now(), periods=days, freq="B")
    np.random.seed(42)
    prices = base_price + np.cumsum(np.random.randn(days) * 2)
    volumes = np.random.randint(1_000_000, 10_000_000, size=days).astype(float)
    return pd.DataFrame({
        "Open": prices - 1,
        "High": prices + 2,
        "Low": prices - 2,
        "Close": prices,
        "Volume": volumes,
    }, index=dates)


def _mock_info():
    """Create a mock stock.info dict."""
    return {
        "averageVolume": 5_000_000,
        "marketCap": 2_000_000_000_000,
        "trailingPE": 25.5,
        "forwardPE": 22.0,
        "totalRevenue": 100_000_000_000,
        "profitMargins": 0.35,
        "trailingEps": 6.50,
        "fiftyTwoWeekHigh": 175.0,
        "fiftyTwoWeekLow": 110.0,
        "sector": "Technology",
        "industry": "Semiconductors",
        "longBusinessSummary": "A large chip company.",
        "currency": "USD",
    }


class TestGetStockSnapshot:
    @patch("data_sources.yahoo_finance.yf")
    def test_returns_valid_snapshot(self, mock_yf):
        """Snapshot should return all expected fields."""
        from data_sources.yahoo_finance import get_stock_snapshot

        mock_ticker = MagicMock()
        mock_ticker.info = _mock_info()
        mock_ticker.history.return_value = _mock_hist()
        mock_yf.Ticker.return_value = mock_ticker

        result = get_stock_snapshot("NVDA")
        assert result["ticker"] == "NVDA"
        assert result["error"] is None
        assert isinstance(result["price"], float)
        assert result["price"] > 0
        assert "market_cap" in result
        assert "pe_ratio" in result

    @patch("data_sources.yahoo_finance.yf")
    def test_empty_history_returns_error(self, mock_yf):
        """Snapshot should return error when no price data."""
        from data_sources.yahoo_finance import get_stock_snapshot

        mock_ticker = MagicMock()
        mock_ticker.info = _mock_info()
        mock_ticker.history.return_value = pd.DataFrame()
        mock_yf.Ticker.return_value = mock_ticker

        result = get_stock_snapshot("INVALID")
        assert result["ticker"] == "INVALID"
        assert "error" in result
        assert result["error"] is not None

    @patch("data_sources.yahoo_finance.yf")
    def test_api_exception_returns_error(self, mock_yf):
        """Snapshot should handle API exceptions gracefully."""
        from data_sources.yahoo_finance import get_stock_snapshot

        mock_yf.Ticker.side_effect = Exception("API down")

        result = get_stock_snapshot("FAIL")
        assert result["ticker"] == "FAIL"
        assert "error" in result
        assert "API down" in result["error"]

    @patch("data_sources.yahoo_finance.yf")
    def test_percentage_changes_calculated(self, mock_yf):
        """Should calculate 1w and 1m percentage changes."""
        from data_sources.yahoo_finance import get_stock_snapshot

        mock_ticker = MagicMock()
        mock_ticker.info = _mock_info()
        mock_ticker.history.return_value = _mock_hist(days=60)
        mock_yf.Ticker.return_value = mock_ticker

        result = get_stock_snapshot("AAPL")
        # With 60 days of data, both changes should be calculable
        assert result["change_1w_pct"] is not None
        assert result["change_1m_pct"] is not None


class TestGetSectorPrices:
    @patch("data_sources.yahoo_finance.get_stock_snapshot")
    def test_concurrent_fetch(self, mock_snapshot):
        """Should fetch all tickers and preserve order."""
        from data_sources.yahoo_finance import get_sector_prices

        def fake_snapshot(ticker):
            return {"ticker": ticker, "price": 100.0, "error": None}

        mock_snapshot.side_effect = fake_snapshot

        result = get_sector_prices(["NVDA", "AMD", "AVGO"])
        assert len(result) == 3
        assert result[0]["ticker"] == "NVDA"
        assert result[1]["ticker"] == "AMD"
        assert result[2]["ticker"] == "AVGO"

    @patch("data_sources.yahoo_finance.get_stock_snapshot")
    def test_empty_list(self, mock_snapshot):
        """Should handle empty ticker list."""
        from data_sources.yahoo_finance import get_sector_prices

        result = get_sector_prices([])
        assert result == []
        mock_snapshot.assert_not_called()


class TestGetPriceHistory:
    @patch("data_sources.yahoo_finance.yf")
    def test_returns_dataframe(self, mock_yf):
        """Should return a DataFrame with price data."""
        from data_sources.yahoo_finance import get_price_history

        mock_ticker = MagicMock()
        mock_ticker.history.return_value = _mock_hist(30)
        mock_yf.Ticker.return_value = mock_ticker

        result = get_price_history("NVDA", period="1mo")
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 30
        assert "Close" in result.columns

    @patch("data_sources.yahoo_finance.yf")
    def test_exception_returns_empty_df(self, mock_yf):
        """Should return empty DataFrame on error."""
        from data_sources.yahoo_finance import get_price_history

        mock_yf.Ticker.side_effect = Exception("Timeout")

        result = get_price_history("FAIL")
        assert isinstance(result, pd.DataFrame)
        assert result.empty
