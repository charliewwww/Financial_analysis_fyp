"""
Tests for utils/time_utils.py — HKT timestamp conversion.
"""

import pytest
from utils.time_utils import to_hkt, to_hkt_short, HKT


class TestToHkt:
    """Tests for the full HKT timestamp converter."""

    def test_utc_to_hkt_basic(self):
        """UTC midnight → HKT 08:00."""
        result = to_hkt("2025-01-15T00:00:00+00:00")
        assert "2025-01-15" in result
        assert "08:00" in result
        assert "HKT" in result

    def test_utc_afternoon_to_hkt_next_day(self):
        """UTC 20:00 → HKT 04:00 next day."""
        result = to_hkt("2025-01-15T20:00:00+00:00")
        assert "2025-01-16" in result
        assert "04:00" in result
        assert "HKT" in result

    def test_naive_utc_assumed(self):
        """Timestamps without timezone info are assumed UTC."""
        result = to_hkt("2025-06-01T12:30:00")
        assert "20:30" in result
        assert "HKT" in result

    def test_empty_string(self):
        assert to_hkt("") == ""

    def test_malformed_input(self):
        """Malformed timestamp falls back to slicing."""
        result = to_hkt("not-a-date")
        assert isinstance(result, str)

    def test_iso_with_microseconds(self):
        result = to_hkt("2025-01-15T12:00:00.123456+00:00")
        assert "20:00" in result
        assert "HKT" in result


class TestToHktShort:
    """Tests for the short HKT date converter."""

    def test_utc_to_hkt_date(self):
        result = to_hkt_short("2025-01-15T00:00:00+00:00")
        assert result == "2025-01-15"

    def test_utc_late_crosses_midnight(self):
        """UTC 22:00 on Jan 15 → HKT Jan 16."""
        result = to_hkt_short("2025-01-15T22:00:00+00:00")
        assert result == "2025-01-16"

    def test_empty_string(self):
        assert to_hkt_short("") == ""

    def test_malformed_input(self):
        result = to_hkt_short("bad-data")
        assert isinstance(result, str)
