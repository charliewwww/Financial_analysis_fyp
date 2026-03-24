"""
Tests for data_sources/fred_macro.py — with mocked FRED API.

No real API calls — all HTTP responses are mocked.
"""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime


class TestGetMacroSnapshot:
    @patch("config.settings.FRED_API_KEY", "")
    def test_no_api_key_returns_unavailable(self):
        """Should return gracefully when FRED_API_KEY is not set."""
        from data_sources.fred_macro import get_macro_snapshot

        result = get_macro_snapshot()
        assert "_meta" in result
        assert result["_meta"]["api_status"] == "unavailable"

    @patch("config.settings.FRED_API_KEY", "test_key_123")
    def test_successful_fetch(self):
        """Should return indicator data when API works."""
        from data_sources.fred_macro import get_macro_snapshot

        # Mock the Fred class from fredapi
        mock_fred = MagicMock()
        # Return a pandas Series with 15 values for each call
        import pandas as pd
        import numpy as np
        dates = pd.date_range(end="2026-02-01", periods=15, freq="ME")
        mock_series = pd.Series(np.linspace(4.0, 5.33, 15), index=dates)
        mock_fred.get_series.return_value = mock_series

        with patch("fredapi.Fred", return_value=mock_fred):
            result = get_macro_snapshot()
            assert "_meta" in result
            indicator_keys = [k for k in result if not k.startswith("_")]
            assert len(indicator_keys) > 0

    @patch("config.settings.FRED_API_KEY", "test_key_123")
    def test_api_failure_degrades_gracefully(self):
        """Should not crash if FRED API returns errors."""
        from data_sources.fred_macro import get_macro_snapshot

        mock_fred = MagicMock()
        mock_fred.get_series.side_effect = Exception("FRED API down")

        with patch("fredapi.Fred", return_value=mock_fred):
            result = get_macro_snapshot()
            assert isinstance(result, dict)
            assert "_meta" in result


class TestFormatMacroForPrompt:
    def test_empty_data(self):
        """Should handle empty macro data."""
        from data_sources.fred_macro import format_macro_for_prompt

        result = format_macro_for_prompt({})
        assert isinstance(result, str)

    def test_unavailable_api(self):
        """Should produce a useful message when API is unavailable."""
        from data_sources.fred_macro import format_macro_for_prompt

        data = {"_meta": {"api_status": "unavailable", "reason": "No key"}}
        result = format_macro_for_prompt(data)
        assert isinstance(result, str)

    def test_formats_indicators(self):
        """Should format indicator data into readable text."""
        from data_sources.fred_macro import format_macro_for_prompt

        data = {
            "fed_funds_rate": {
                "value": 5.33,
                "date": "2026-01-01",
                "name": "Federal Funds Rate",
                "unit": "%",
                "trend": "stable",
                "description": "The Fed's target rate.",
                "interpretation": {},
            },
            "_meta": {"api_status": "ok", "source": "FRED", "indicators_fetched": 1, "fetched_at": "2026-01-01T00:00:00"},
        }
        result = format_macro_for_prompt(data)
        assert "Federal Funds Rate" in result
        assert "5.33" in result
