"""
Reports Database — stores analysis reports and tracks prediction accuracy.

Uses SQLite (built into Python, zero setup, single file).

Two tables:
1. reports: Every analysis report with its metadata
2. predictions: Price snapshots at report time, updated 1 week later with actuals

This is the "accountability loop" — we record what the system said,
then check if it was right. Over time, this builds a track record.
"""

import sqlite3
import json
import threading
from datetime import datetime, timezone
from config.settings import DATABASE_PATH

_db_initialized = False
_db_init_lock = threading.Lock()


def _get_conn() -> sqlite3.Connection:
    """
    Get a database connection, creating tables if needed (once per process).

    ALWAYS use as a context manager:
        with _get_conn() as conn:
            conn.execute(...)
    The connection auto-commits on success and rolls back on exception.
    """
    global _db_initialized
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row  # Access columns by name

    if not _db_initialized:
        with _db_init_lock:
            if not _db_initialized:  # double-check after acquiring lock
                _init_tables(conn)
                _db_initialized = True
    return conn


def _init_tables(conn: sqlite3.Connection):
    """Create tables if they don't exist, and migrate existing tables."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sector_id TEXT NOT NULL,
            sector_name TEXT NOT NULL,
            created_at TEXT NOT NULL,
            analysis TEXT NOT NULL,
            validation TEXT,
            confidence_score REAL,
            status TEXT DEFAULT 'active',
            prices_snapshot TEXT,
            technicals_snapshot TEXT,
            news_snapshot TEXT,
            filings_snapshot TEXT,
            timing_snapshot TEXT,
            news_used INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_id INTEGER NOT NULL,
            ticker TEXT NOT NULL,
            price_at_report REAL,
            change_1w_at_report REAL,
            price_1w_later REAL,
            actual_change_1w REAL,
            checked_at TEXT,
            prediction_correct INTEGER,
            FOREIGN KEY (report_id) REFERENCES reports(id)
        );

        CREATE INDEX IF NOT EXISTS idx_reports_sector ON reports(sector_id);
        CREATE INDEX IF NOT EXISTS idx_reports_date ON reports(created_at);
        CREATE INDEX IF NOT EXISTS idx_predictions_report ON predictions(report_id);
        CREATE INDEX IF NOT EXISTS idx_predictions_unchecked 
            ON predictions(price_1w_later) WHERE price_1w_later IS NULL;
    """)

    # ── Migration: add new columns to existing tables ─────────────
    # SQLite's CREATE TABLE IF NOT EXISTS won't add columns to existing tables,
    # so we need ALTER TABLE for databases created before these columns existed.
    _migrate_add_columns(conn, "reports", [
        ("technicals_snapshot", "TEXT"),
        ("news_snapshot", "TEXT"),
        ("filings_snapshot", "TEXT"),
        ("timing_snapshot", "TEXT"),
        ("pipeline_state", "TEXT"),
        ("news_summary", "TEXT"),
        ("data_sufficiency", "TEXT"),
        ("validation_status", "TEXT"),
    ])

    _migrate_add_columns(conn, "predictions", [
        ("ai_direction", "TEXT"),
        ("ai_predicted_change", "TEXT"),
        ("ai_reasoning", "TEXT"),
        ("ai_risk", "TEXT"),
    ])

    conn.commit()


def _migrate_add_columns(conn: sqlite3.Connection, table: str, columns: list[tuple[str, str]]):
    """Add columns to a table if they don't already exist."""
    cursor = conn.execute(f"PRAGMA table_info({table})")
    existing = {row[1] for row in cursor.fetchall()}
    for col_name, col_type in columns:
        if col_name not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_type}")


def save_report(
    sector_id: str,
    sector_name: str,
    analysis: str,
    validation: str,
    prices: list[dict],
    news_count: int,
    confidence_score: float | None = None,
    technicals: list[dict] | None = None,
    news_articles: list[dict] | None = None,
    filings: list[dict] | None = None,
    timing: dict | None = None,
) -> int:
    """
    Save a completed analysis report and record price predictions.

    Stores ALL raw data (news, prices, technicals, filings, timing)
    so users can see exactly what the AI was fed, and so we can
    debug bad analyses.

    Returns the report ID.
    """
    now = datetime.now(timezone.utc).isoformat()

    with _get_conn() as conn:
        # Save the report with all raw data
        cursor = conn.execute(
            """INSERT INTO reports (sector_id, sector_name, created_at, analysis, 
               validation, confidence_score, prices_snapshot, technicals_snapshot,
               news_snapshot, filings_snapshot, timing_snapshot, news_used)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                sector_id,
                sector_name,
                now,
                analysis,
                validation,
                confidence_score,
                json.dumps(prices),
                json.dumps(technicals) if technicals else None,
                json.dumps(news_articles) if news_articles else None,
                json.dumps(filings) if filings else None,
                json.dumps(timing) if timing else None,
                news_count,
            ),
        )
        report_id = cursor.lastrowid

        # Record price predictions (for 1-week-later comparison)
        for p in prices:
            if p.get("error") or not p.get("price"):
                continue
            conn.execute(
                """INSERT INTO predictions (report_id, ticker, price_at_report, change_1w_at_report)
                   VALUES (?, ?, ?, ?)""",
                (report_id, p["ticker"], p["price"], p.get("change_1w_pct")),
            )

    return report_id


def save_report_from_state(state) -> int:
    """
    Save a report from a PipelineState object.

    This is the NEW save path — stores the entire serialized pipeline state
    alongside the traditional columns, so old reports keep working and new
    reports have full provenance data.

    Returns the report ID.
    """
    now = datetime.now(timezone.utc).isoformat()

    # Convert Article objects to dicts for news_snapshot
    news_dicts = [
        {
            "title": a.title,
            "source": a.source,
            "link": a.link,
            "published": a.published,
            "summary": a.raw_summary,
            "condensed_summary": a.condensed_summary,
            "relevance": a.relevance_tag,
            "used_in_analysis": a.used_in_analysis,
        }
        for a in state.articles
    ]

    # Build timing from node executions
    timing = {
        "total_seconds": state.total_duration_seconds,
        "steps": [
            {"name": n.node_name, "seconds": n.duration_seconds}
            for n in state.node_executions
        ],
    }

    with _get_conn() as conn:
        cursor = conn.execute(
            """INSERT INTO reports (
                sector_id, sector_name, created_at, analysis, validation,
                confidence_score, prices_snapshot, technicals_snapshot,
                news_snapshot, filings_snapshot, timing_snapshot, news_used,
                pipeline_state, news_summary, data_sufficiency, validation_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                state.sector_id,
                state.sector_name,
                now,
                state.analysis_text,
                state.validation_text,
                state.confidence_score,
                json.dumps(state.prices),
                json.dumps(state.technicals),
                json.dumps(news_dicts),
                json.dumps(state.filings),
                json.dumps(timing),
                len(state.articles),
                state.to_json(),   # ← Full pipeline state, the crown jewel
                state.news_summary,
                state.data_sufficiency,
                state.validation_status,
            ),
        )
        report_id = cursor.lastrowid

        # Build lookup for AI predictions
        ai_pred_map = {p["ticker"]: p for p in (state.ai_predictions if hasattr(state, 'ai_predictions') else [])}

        # Record price predictions with AI directional predictions
        for p in state.prices:
            if p.get("error") or not p.get("price"):
                continue
            ai = ai_pred_map.get(p["ticker"], {})
            conn.execute(
                """INSERT INTO predictions (report_id, ticker, price_at_report, change_1w_at_report,
                   ai_direction, ai_predicted_change, ai_reasoning, ai_risk)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (report_id, p["ticker"], p["price"], p.get("change_1w_pct"),
                 ai.get("direction"), ai.get("predicted_change"),
                 ai.get("reasoning"), ai.get("key_risk")),
            )

    return report_id


# Lightweight columns for list / dashboard views (excludes large JSON blobs)
_LIST_COLS = (
    "id, sector_id, sector_name, created_at, confidence_score,"
    " validation_status, news_used, data_sufficiency, status"
)


def get_reports_list(sector_id: str | None = None, limit: int = 20) -> list[dict]:
    """
    Fast lightweight query for list/dashboard views.
    Excludes heavy columns (pipeline_state, analysis, *_snapshot).
    """
    with _get_conn() as conn:
        if sector_id:
            rows = conn.execute(
                f"SELECT {_LIST_COLS} FROM reports WHERE sector_id = ? ORDER BY created_at DESC LIMIT ?",
                (sector_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                f"SELECT {_LIST_COLS} FROM reports ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
    return [dict(r) for r in rows]


def get_reports(sector_id: str | None = None, limit: int = 20) -> list[dict]:
    """
    Get recent reports, optionally filtered by sector.
    Returns newest first.
    """
    with _get_conn() as conn:
        if sector_id:
            rows = conn.execute(
                "SELECT * FROM reports WHERE sector_id = ? ORDER BY created_at DESC LIMIT ?",
                (sector_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM reports ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
    return [dict(r) for r in rows]


def get_report_by_id(report_id: int) -> dict | None:
    """Get a single report by ID."""
    with _get_conn() as conn:
        row = conn.execute("SELECT * FROM reports WHERE id = ?", (report_id,)).fetchone()
    return dict(row) if row else None


def get_predictions_for_report(report_id: int) -> list[dict]:
    """Get all price predictions associated with a report."""
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM predictions WHERE report_id = ? ORDER BY ticker",
            (report_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_unchecked_predictions() -> list[dict]:
    """Get predictions that haven't been verified against actual prices yet."""
    with _get_conn() as conn:
        rows = conn.execute(
            """SELECT p.*, r.created_at as report_date, r.sector_name
               FROM predictions p 
               JOIN reports r ON p.report_id = r.id
               WHERE p.price_1w_later IS NULL
               ORDER BY r.created_at ASC""",
        ).fetchall()
    return [dict(r) for r in rows]


def update_prediction_actual(prediction_id: int, actual_price: float):
    """
    Update a prediction with the actual price 1 week later.
    Calculates whether the AI directional prediction was correct.
    """
    with _get_conn() as conn:
        pred = conn.execute("SELECT * FROM predictions WHERE id = ?", (prediction_id,)).fetchone()
        if not pred:
            return

        price_at_report = pred["price_at_report"]
        if price_at_report and price_at_report > 0:
            actual_change = ((actual_price - price_at_report) / price_at_report) * 100
        else:
            actual_change = 0

        # Check if AI direction prediction was correct
        prediction_correct = None
        try:
            ai_direction = pred["ai_direction"]
        except (IndexError, KeyError):
            ai_direction = None

        if ai_direction:
            if ai_direction == "BULLISH" and actual_change > 0:
                prediction_correct = 1
            elif ai_direction == "BEARISH" and actual_change < 0:
                prediction_correct = 1
            elif ai_direction == "NEUTRAL" and abs(actual_change) < 2:
                prediction_correct = 1
            elif ai_direction:
                prediction_correct = 0

        conn.execute(
            """UPDATE predictions 
               SET price_1w_later = ?, actual_change_1w = ?, checked_at = ?, prediction_correct = ?
               WHERE id = ?""",
            (actual_price, round(actual_change, 2), datetime.now(timezone.utc).isoformat(),
             prediction_correct, prediction_id),
        )


def get_prediction_accuracy() -> dict:
    """
    Calculate overall prediction tracking stats.
    Returns summary of how many predictions have been checked and accuracy.
    """
    with _get_conn() as conn:
        total = conn.execute("SELECT COUNT(*) FROM predictions").fetchone()[0]
        checked = conn.execute("SELECT COUNT(*) FROM predictions WHERE price_1w_later IS NOT NULL").fetchone()[0]
        unchecked = total - checked

        # Average absolute error for checked predictions
        avg_error = None
        if checked > 0:
            result = conn.execute(
                "SELECT AVG(ABS(actual_change_1w)) FROM predictions WHERE actual_change_1w IS NOT NULL"
            ).fetchone()
            avg_error = round(result[0], 2) if result[0] else None

        # AI direction prediction accuracy
        direction_correct = 0
        direction_total = 0
        if checked > 0:
            result = conn.execute(
                "SELECT COUNT(*) FROM predictions WHERE prediction_correct = 1"
            ).fetchone()
            direction_correct = result[0] if result[0] else 0
            result = conn.execute(
                "SELECT COUNT(*) FROM predictions WHERE prediction_correct IS NOT NULL"
            ).fetchone()
            direction_total = result[0] if result[0] else 0

    return {
        "total_predictions": total,
        "checked": checked,
        "unchecked": unchecked,
        "avg_absolute_weekly_change": avg_error,
        "direction_correct": direction_correct,
        "direction_total": direction_total,
        "direction_accuracy_pct": round(direction_correct / direction_total * 100, 1) if direction_total > 0 else None,
    }


# ── Report purging (keep predictions) ────────────────────────────

# Import cap from central config (default 50)
try:
    from config.settings import MAX_REPORTS
except ImportError:
    MAX_REPORTS = 50


def purge_old_reports(max_reports: int = MAX_REPORTS) -> list[int]:
    """
    Delete the oldest reports when the total exceeds *max_reports*.

    Predictions rows are KEPT (orphaned report_id is fine) so we
    preserve the full prediction-tracking history.

    Returns:
        List of deleted report IDs (empty if nothing was purged).
    """
    with _get_conn() as conn:
        total = conn.execute("SELECT COUNT(*) FROM reports").fetchone()[0]
        if total <= max_reports:
            return []

        # Find IDs to delete (oldest first, skip the newest max_reports)
        rows = conn.execute(
            "SELECT id FROM reports ORDER BY created_at DESC LIMIT -1 OFFSET ?",
            (max_reports,),
        ).fetchall()
        ids_to_delete = [r[0] for r in rows]

        if ids_to_delete:
            placeholders = ",".join("?" for _ in ids_to_delete)
            conn.execute(
                f"DELETE FROM reports WHERE id IN ({placeholders})",
                ids_to_delete,
            )

    return ids_to_delete


def get_report_count() -> int:
    """Return total number of reports stored."""
    with _get_conn() as conn:
        return conn.execute("SELECT COUNT(*) FROM reports").fetchone()[0]


def get_prediction_accuracy_over_time() -> list[dict]:
    """
    Per-report prediction accuracy for charting.

    Returns a list of dicts ordered by report date:
        [{report_id, sector_name, created_at, total, correct, wrong, pending, accuracy_pct}, ...]
    """
    with _get_conn() as conn:
        rows = conn.execute(
            """SELECT
                 r.id AS report_id,
                 r.sector_name,
                 r.created_at,
                 COUNT(p.id) AS total,
                 SUM(CASE WHEN p.prediction_correct = 1 THEN 1 ELSE 0 END) AS correct,
                 SUM(CASE WHEN p.prediction_correct = 0 THEN 1 ELSE 0 END) AS wrong,
                 SUM(CASE WHEN p.prediction_correct IS NULL THEN 1 ELSE 0 END) AS pending
               FROM reports r
               JOIN predictions p ON p.report_id = r.id
               WHERE p.ai_direction IS NOT NULL
               GROUP BY r.id
               ORDER BY r.created_at ASC""",
        ).fetchall()
    results = []
    for r in rows:
        total_checked = (r["correct"] or 0) + (r["wrong"] or 0)
        acc = round((r["correct"] or 0) / total_checked * 100, 1) if total_checked > 0 else None
        results.append({
            "report_id": r["report_id"],
            "sector_name": r["sector_name"],
            "created_at": r["created_at"],
            "total": r["total"],
            "correct": r["correct"] or 0,
            "wrong": r["wrong"] or 0,
            "pending": r["pending"] or 0,
            "accuracy_pct": acc,
        })
    return results
