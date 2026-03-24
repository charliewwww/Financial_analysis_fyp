"""
Tests for utils/anomaly_detection.py — deterministic anomaly scanner.

All tests use synthetic data, no network calls needed.
"""

import pytest
from utils.anomaly_detection import (
    detect_anomalies,
    AnomalyReport,
    Anomaly,
    VOLUME_ZSCORE_THRESHOLD,
    RSI_OVERBOUGHT,
    RSI_OVERSOLD,
)


class TestDetectAnomalies:
    def test_no_anomalies_normal_data(self):
        """Normal technicals should produce no anomalies."""
        technicals = [{
            "ticker": "NVDA",
            "rsi_14": 55.0,
            "volume_zscore": 0.5,
            "bb_position": 0.5,
            "change_5d_pct": 1.2,
        }]
        report = detect_anomalies(technicals)
        assert not report.has_anomalies

    def test_volume_spike_detected(self):
        """High volume Z-score should trigger alert."""
        technicals = [{
            "ticker": "NVDA",
            "rsi_14": 55.0,
            "volume_zscore": 3.5,
            "volume_ratio": 2.5,
            "bb_position": 0.5,
            "change_5d_pct": 1.0,
        }]
        report = detect_anomalies(technicals)
        assert report.has_anomalies
        vol_alerts = [a for a in report.anomalies if a.signal_type == "volume_spike"]
        assert len(vol_alerts) == 1
        assert vol_alerts[0].severity == "high"  # Z > 3

    def test_rsi_overbought_detected(self):
        """RSI > 70 should trigger overbought alert."""
        technicals = [{
            "ticker": "TSM",
            "rsi_14": 75.0,
            "volume_zscore": 0.5,
            "bb_position": 0.5,
            "change_5d_pct": 1.0,
        }]
        report = detect_anomalies(technicals)
        rsi_alerts = [a for a in report.anomalies if a.signal_type == "rsi_extreme"]
        assert len(rsi_alerts) == 1
        assert "OVERBOUGHT" in rsi_alerts[0].description

    def test_rsi_oversold_detected(self):
        """RSI < 30 should trigger oversold alert."""
        technicals = [{
            "ticker": "AMD",
            "rsi_14": 22.0,
            "volume_zscore": 0.5,
            "bb_position": 0.5,
            "change_5d_pct": -1.0,
        }]
        report = detect_anomalies(technicals)
        rsi_alerts = [a for a in report.anomalies if a.signal_type == "rsi_extreme"]
        assert len(rsi_alerts) == 1
        assert "OVERSOLD" in rsi_alerts[0].description

    def test_large_price_move_detected(self):
        """5-day change > 5% should trigger alert."""
        technicals = [{
            "ticker": "NVDA",
            "rsi_14": 55.0,
            "volume_zscore": 0.5,
            "bb_position": 0.5,
            "change_5d_pct": -8.5,
        }]
        report = detect_anomalies(technicals)
        move_alerts = [a for a in report.anomalies if a.signal_type == "price_move"]
        assert len(move_alerts) == 1
        assert "drop" in move_alerts[0].description

    def test_bollinger_breakout_detected(self):
        """BB position near 1.0 should trigger alert."""
        technicals = [{
            "ticker": "NVDA",
            "rsi_14": 55.0,
            "volume_zscore": 0.5,
            "bb_position": 0.98,
            "change_5d_pct": 2.0,
        }]
        report = detect_anomalies(technicals)
        bb_alerts = [a for a in report.anomalies if a.signal_type == "bollinger_breakout"]
        assert len(bb_alerts) == 1

    def test_multiple_anomalies_multiple_tickers(self):
        """Multiple tickers with multiple anomalies."""
        technicals = [
            {"ticker": "NVDA", "rsi_14": 80.0, "volume_zscore": 4.0,
             "volume_ratio": 3.0, "bb_position": 0.5, "change_5d_pct": 12.0},
            {"ticker": "AMD", "rsi_14": 25.0, "volume_zscore": 0.5,
             "bb_position": 0.02, "change_5d_pct": -7.0},
        ]
        report = detect_anomalies(technicals)
        assert len(report.anomalies) >= 4
        assert report.high_count >= 2

    def test_error_tickers_skipped(self):
        """Tickers with errors should be skipped, not crash."""
        technicals = [
            {"ticker": "BAD", "error": "No data"},
            {"ticker": "NVDA", "rsi_14": 55.0, "volume_zscore": 0.5,
             "bb_position": 0.5, "change_5d_pct": 1.0},
        ]
        report = detect_anomalies(technicals)
        assert not report.has_anomalies

    def test_none_values_handled(self):
        """Technicals with None values should not crash."""
        technicals = [{
            "ticker": "NVDA",
            "rsi_14": None,
            "volume_zscore": None,
            "bb_position": None,
            "change_5d_pct": None,
        }]
        report = detect_anomalies(technicals)
        assert not report.has_anomalies


class TestAnomalyReport:
    def test_format_for_prompt_empty(self):
        report = AnomalyReport()
        assert report.format_for_prompt() == ""

    def test_format_for_prompt_with_alerts(self):
        report = AnomalyReport(anomalies=[
            Anomaly(ticker="NVDA", signal_type="volume_spike",
                    severity="high", description="Volume spike Z=3.5"),
        ])
        text = report.format_for_prompt()
        assert "NVDA" in text
        assert "ANOMALY" in text

    def test_to_dict_list(self):
        report = AnomalyReport(anomalies=[
            Anomaly(ticker="NVDA", signal_type="volume_spike",
                    severity="high", description="Test", value=3.5, threshold=2.0),
        ])
        dicts = report.to_dict_list()
        assert len(dicts) == 1
        assert dicts[0]["ticker"] == "NVDA"
        assert dicts[0]["value"] == 3.5
