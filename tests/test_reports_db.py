"""
Tests for database/reports_db.py — purge logic and accuracy-over-time query.

Uses a temporary SQLite database for isolation.
"""

import os
import json
import pytest
import tempfile
from unittest.mock import patch
from datetime import datetime, timezone, timedelta


@pytest.fixture(autouse=True)
def _temp_db(tmp_path, monkeypatch):
    """Redirect DATABASE_PATH to a temp file so tests don't touch the real DB."""
    db_path = str(tmp_path / "test_reports.db")
    monkeypatch.setattr("database.reports_db.DATABASE_PATH", db_path)
    # Reset the init flag so tables are re-created
    import database.reports_db as mod
    mod._db_initialized = False
    yield db_path


def _insert_report(conn, sector_id="test", sector_name="Test Sector", offset_days=0):
    """Helper: insert a minimal report row and return its ID."""
    ts = (datetime.now(timezone.utc) - timedelta(days=offset_days)).isoformat()
    cursor = conn.execute(
        """INSERT INTO reports (sector_id, sector_name, created_at, analysis, validation,
           confidence_score, news_used)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (sector_id, sector_name, ts, "test analysis", "test validation", 7.0, 5),
    )
    return cursor.lastrowid


class TestPurgeOldReports:
    """Tests for the purge_old_reports() function."""

    def test_no_purge_when_under_limit(self):
        from database.reports_db import purge_old_reports, _get_conn
        with _get_conn() as conn:
            for i in range(5):
                _insert_report(conn, offset_days=i)
            conn.commit()
        purged = purge_old_reports(max_reports=10)
        assert purged == []

    def test_purge_when_over_limit(self):
        from database.reports_db import purge_old_reports, _get_conn, get_report_count
        with _get_conn() as conn:
            for i in range(12):
                _insert_report(conn, offset_days=i)
            conn.commit()
        assert get_report_count() == 12
        purged = purge_old_reports(max_reports=10)
        assert len(purged) == 2  # Oldest 2 should be deleted
        assert get_report_count() == 10

    def test_purge_preserves_predictions(self):
        from database.reports_db import purge_old_reports, _get_conn
        with _get_conn() as conn:
            # Insert 12 reports with predictions
            for i in range(12):
                rid = _insert_report(conn, offset_days=i)
                conn.execute(
                    "INSERT INTO predictions (report_id, ticker, price_at_report) VALUES (?, ?, ?)",
                    (rid, "NVDA", 130.0),
                )
            conn.commit()
            total_preds_before = conn.execute("SELECT COUNT(*) FROM predictions").fetchone()[0]

        purged = purge_old_reports(max_reports=10)
        assert len(purged) == 2

        with _get_conn() as conn:
            total_preds_after = conn.execute("SELECT COUNT(*) FROM predictions").fetchone()[0]
        # All predictions should still exist (orphaned but preserved)
        assert total_preds_after == total_preds_before

    def test_purge_exactly_at_limit(self):
        from database.reports_db import purge_old_reports, _get_conn
        with _get_conn() as conn:
            for i in range(10):
                _insert_report(conn, offset_days=i)
            conn.commit()
        purged = purge_old_reports(max_reports=10)
        assert purged == []


class TestGetReportCount:
    def test_empty_db(self):
        from database.reports_db import get_report_count
        assert get_report_count() == 0

    def test_with_reports(self):
        from database.reports_db import get_report_count, _get_conn
        with _get_conn() as conn:
            for i in range(3):
                _insert_report(conn)
            conn.commit()
        assert get_report_count() == 3


class TestPredictionAccuracyOverTime:
    def test_empty_db(self):
        from database.reports_db import get_prediction_accuracy_over_time
        result = get_prediction_accuracy_over_time()
        assert result == []

    def test_with_checked_predictions(self):
        from database.reports_db import get_prediction_accuracy_over_time, _get_conn
        with _get_conn() as conn:
            rid = _insert_report(conn, offset_days=0)
            # Insert predictions with AI direction and checked results
            conn.execute(
                """INSERT INTO predictions
                   (report_id, ticker, price_at_report, ai_direction,
                    price_1w_later, actual_change_1w, prediction_correct)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (rid, "NVDA", 130.0, "BULLISH", 135.0, 3.85, 1),
            )
            conn.execute(
                """INSERT INTO predictions
                   (report_id, ticker, price_at_report, ai_direction,
                    price_1w_later, actual_change_1w, prediction_correct)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (rid, "AMD", 165.0, "BEARISH", 170.0, 3.03, 0),
            )
            conn.commit()

        result = get_prediction_accuracy_over_time()
        assert len(result) == 1
        assert result[0]["correct"] == 1
        assert result[0]["wrong"] == 1
        assert result[0]["accuracy_pct"] == 50.0

    def test_pending_predictions_have_null_accuracy(self):
        from database.reports_db import get_prediction_accuracy_over_time, _get_conn
        with _get_conn() as conn:
            rid = _insert_report(conn, offset_days=0)
            conn.execute(
                """INSERT INTO predictions
                   (report_id, ticker, price_at_report, ai_direction)
                   VALUES (?, ?, ?, ?)""",
                (rid, "NVDA", 130.0, "BULLISH"),
            )
            conn.commit()

        result = get_prediction_accuracy_over_time()
        assert len(result) == 1
        assert result[0]["pending"] == 1
        assert result[0]["accuracy_pct"] is None
