"""
Tests for utils/markdown_export.py — report-to-markdown converter.
"""

import json
import pytest
from utils.markdown_export import export_report_markdown, _fmt, _fmt_large, _parse_json


class TestExportReportMarkdown:
    @pytest.fixture
    def minimal_report(self):
        return {
            "id": 42,
            "sector_id": "semiconductors",
            "sector_name": "Semiconductors",
            "created_at": "2025-01-15T10:30:00",
            "analysis": "NVDA is bullish due to AI demand.",
            "confidence_score": 7.5,
            "validation_status": "passed",
            "data_sufficiency": "sufficient",
        }

    def test_contains_title(self, minimal_report):
        md = export_report_markdown(minimal_report)
        assert "# Semiconductors" in md

    def test_contains_analysis(self, minimal_report):
        md = export_report_markdown(minimal_report)
        assert "NVDA is bullish" in md

    def test_contains_confidence(self, minimal_report):
        md = export_report_markdown(minimal_report)
        assert "7.5" in md

    def test_contains_metadata(self, minimal_report):
        md = export_report_markdown(minimal_report)
        assert "Report ID" in md
        assert "42" in md
        assert "2025-01-15" in md

    def test_news_summary_included(self, minimal_report):
        minimal_report["news_summary"] = "AI chips dominate headlines."
        md = export_report_markdown(minimal_report)
        assert "AI chips dominate" in md

    def test_validation_section(self, minimal_report):
        minimal_report["validation"] = "All numbers verified."
        md = export_report_markdown(minimal_report)
        assert "Validation Report" in md
        assert "All numbers verified" in md

    def test_technicals_table(self, minimal_report):
        minimal_report["technicals_snapshot"] = json.dumps([
            {"ticker": "NVDA", "current_price": 130.5, "rsi_14": 65.0,
             "volume_zscore": 0.8, "bb_position": 0.6, "change_5d_pct": 3.2},
        ])
        md = export_report_markdown(minimal_report)
        assert "Technical Indicators" in md
        assert "NVDA" in md
        assert "130.50" in md

    def test_prices_table(self, minimal_report):
        minimal_report["prices_snapshot"] = json.dumps([
            {"ticker": "NVDA", "price": 130.5, "change_1w_pct": 2.1,
             "change_1m_pct": 8.3, "market_cap": 3200000000000},
        ])
        md = export_report_markdown(minimal_report)
        assert "Price Snapshot" in md
        assert "130.50" in md
        assert "3.2T" in md

    def test_timing_table(self, minimal_report):
        minimal_report["timing_snapshot"] = json.dumps({
            "total_seconds": 42.5,
            "steps": [{"name": "fetch_news", "seconds": 10.2}],
        })
        md = export_report_markdown(minimal_report)
        assert "Pipeline Timing" in md
        assert "42.5s" in md
        assert "fetch_news" in md

    def test_anomaly_alerts_from_state(self, minimal_report):
        state = {
            "anomaly_alerts": [
                {"ticker": "NVDA", "signal_type": "volume_spike",
                 "severity": "high", "description": "Volume Z=3.5"},
            ]
        }
        md = export_report_markdown(minimal_report, state)
        assert "Anomaly Alerts" in md
        assert "🔴" in md
        assert "Volume Z=3.5" in md

    def test_empty_state_no_crash(self, minimal_report):
        md = export_report_markdown(minimal_report, state={})
        assert "# Semiconductors" in md

    def test_news_sources_listed(self, minimal_report):
        minimal_report["news_snapshot"] = json.dumps([
            {"title": "AI Boom", "source": "Reuters", "link": "https://example.com",
             "published": "2025-01-15"},
        ])
        md = export_report_markdown(minimal_report)
        assert "News Sources" in md
        assert "[AI Boom](https://example.com)" in md


class TestHelpers:
    def test_fmt_none(self):
        assert _fmt(None) == "—"

    def test_fmt_number(self):
        assert _fmt(3.14159, 2) == "3.14"

    def test_fmt_large_billions(self):
        assert _fmt_large(3.2e9) == "3.2B"

    def test_fmt_large_trillions(self):
        assert _fmt_large(1.5e12) == "1.5T"

    def test_fmt_large_millions(self):
        assert _fmt_large(450e6) == "450.0M"

    def test_fmt_large_none(self):
        assert _fmt_large(None) == "—"

    def test_parse_json_string(self):
        assert _parse_json('[1,2,3]') == [1, 2, 3]

    def test_parse_json_already_parsed(self):
        assert _parse_json([1, 2]) == [1, 2]

    def test_parse_json_none(self):
        assert _parse_json(None) is None

    def test_parse_json_invalid(self):
        assert _parse_json("not-json{{{") is None
