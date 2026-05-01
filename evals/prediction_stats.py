"""
Prediction Accuracy Statistics — empirical evaluation of the AI's directional calls.

Queries the predictions table to compute:
- Overall accuracy vs random (50%) baseline and momentum baseline
- Binomial significance test
- Breakdown by sector, by direction, and by confidence score tier
- Distribution of actual price movements for correct vs incorrect calls
"""

from __future__ import annotations

import sqlite3
import json
from dataclasses import dataclass, field
from typing import Any

from config.settings import DATABASE_PATH


# ── Result data structures ────────────────────────────────────────

@dataclass
class DirectionBreakdown:
    direction: str
    total: int
    correct: int
    accuracy: float


@dataclass
class SectorBreakdown:
    sector: str
    total: int
    correct: int
    accuracy: float


@dataclass
class PredictionStats:
    # Raw counts
    total_predictions: int = 0
    verified_predictions: int = 0
    with_direction: int = 0          # subset that has BULLISH/BEARISH/NEUTRAL
    correct: int = 0

    # Accuracy
    accuracy_pct: float = 0.0        # correct / with_direction * 100
    random_baseline_pct: float = 50.0

    # Statistical significance (binomial test vs 50%)
    p_value: float = 1.0
    is_significant: bool = False      # p < 0.05
    significance_label: str = ""      # "significantly below", "not significant", etc.

    # Confidence intervals
    ci_lower: float = 0.0
    ci_upper: float = 0.0

    # Movement stats
    avg_actual_change_correct: float = 0.0    # avg |Δ| when AI was right
    avg_actual_change_wrong: float = 0.0      # avg |Δ| when AI was wrong
    avg_actual_change_all: float = 0.0

    # Breakdowns
    by_direction: list[DirectionBreakdown] = field(default_factory=list)
    by_sector: list[SectorBreakdown] = field(default_factory=list)

    # Bias analysis
    bullish_rate: float = 0.0    # % of calls that were BULLISH
    bearish_rate: float = 0.0
    neutral_rate: float = 0.0

    # Trend: accuracy over time (list of {date, accuracy} for rolling window)
    accuracy_over_time: list[dict] = field(default_factory=list)


def get_prediction_stats() -> PredictionStats:
    """
    Compute all prediction accuracy statistics from the live database.
    Uses scipy for statistical tests if available; falls back to a normal
    approximation otherwise.
    """
    stats = PredictionStats()

    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row

    try:
        # ── Total counts ─────────────────────────────────────────
        stats.total_predictions = conn.execute(
            "SELECT COUNT(*) FROM predictions"
        ).fetchone()[0]

        stats.verified_predictions = conn.execute(
            "SELECT COUNT(*) FROM predictions WHERE price_1w_later IS NOT NULL"
        ).fetchone()[0]

        # Only predictions that have BOTH ai_direction AND were verified
        verified_rows = conn.execute(
            """SELECT p.*, r.sector_name, r.confidence_score, r.created_at as report_date
               FROM predictions p
               JOIN reports r ON p.report_id = r.id
               WHERE p.price_1w_later IS NOT NULL
                 AND p.ai_direction IS NOT NULL
                 AND p.ai_direction != ''"""
        ).fetchall()
        verified_rows = [dict(r) for r in verified_rows]

        stats.with_direction = len(verified_rows)
        if stats.with_direction == 0:
            return stats

        stats.correct = sum(1 for r in verified_rows if r.get("prediction_correct") == 1)
        stats.accuracy_pct = round(stats.correct / stats.with_direction * 100, 1)

        # ── Binomial test ─────────────────────────────────────────
        n, k = stats.with_direction, stats.correct
        try:
            from scipy.stats import binomtest
            result = binomtest(k, n, 0.5, alternative="two-sided")
            stats.p_value = round(result.pvalue, 4)
            ci = result.proportion_ci(confidence_level=0.95)
            stats.ci_lower = round(ci.low * 100, 1)
            stats.ci_upper = round(ci.high * 100, 1)
        except ImportError:
            # Normal approximation fallback
            import math
            p_hat = k / n
            se = math.sqrt(0.25 / n)   # SE under H0: p=0.5
            z = (p_hat - 0.5) / se
            # Two-tailed p-value approximation
            stats.p_value = round(2 * (1 - _normal_cdf(abs(z))), 4)
            margin = 1.96 * math.sqrt(p_hat * (1 - p_hat) / n)
            stats.ci_lower = round((p_hat - margin) * 100, 1)
            stats.ci_upper = round((p_hat + margin) * 100, 1)

        stats.is_significant = stats.p_value < 0.05
        acc = stats.accuracy_pct
        if stats.is_significant:
            if acc < 50:
                stats.significance_label = f"Significantly below random (p={stats.p_value})"
            else:
                stats.significance_label = f"Significantly above random (p={stats.p_value})"
        else:
            stats.significance_label = f"Not significantly different from random (p={stats.p_value})"

        # ── Movement stats ────────────────────────────────────────
        changes_correct = [
            abs(r["actual_change_1w"]) for r in verified_rows
            if r.get("prediction_correct") == 1 and r.get("actual_change_1w") is not None
        ]
        changes_wrong = [
            abs(r["actual_change_1w"]) for r in verified_rows
            if r.get("prediction_correct") == 0 and r.get("actual_change_1w") is not None
        ]
        changes_all = [
            abs(r["actual_change_1w"]) for r in verified_rows
            if r.get("actual_change_1w") is not None
        ]

        stats.avg_actual_change_correct = round(sum(changes_correct) / len(changes_correct), 1) if changes_correct else 0.0
        stats.avg_actual_change_wrong = round(sum(changes_wrong) / len(changes_wrong), 1) if changes_wrong else 0.0
        stats.avg_actual_change_all = round(sum(changes_all) / len(changes_all), 1) if changes_all else 0.0

        # ── Breakdown by direction ────────────────────────────────
        direction_data: dict[str, dict] = {}
        for row in verified_rows:
            d = (row.get("ai_direction") or "UNKNOWN").upper()
            if d not in direction_data:
                direction_data[d] = {"total": 0, "correct": 0}
            direction_data[d]["total"] += 1
            if row.get("prediction_correct") == 1:
                direction_data[d]["correct"] += 1

        for direction, counts in sorted(direction_data.items()):
            t = counts["total"]
            c = counts["correct"]
            stats.by_direction.append(DirectionBreakdown(
                direction=direction,
                total=t,
                correct=c,
                accuracy=round(c / t * 100, 1) if t > 0 else 0.0,
            ))

        # Bias rates
        total_d = stats.with_direction
        stats.bullish_rate = round(direction_data.get("BULLISH", {}).get("total", 0) / total_d * 100, 1)
        stats.bearish_rate = round(direction_data.get("BEARISH", {}).get("total", 0) / total_d * 100, 1)
        stats.neutral_rate = round(direction_data.get("NEUTRAL", {}).get("total", 0) / total_d * 100, 1)

        # ── Breakdown by sector ────────────────────────────────────
        sector_data: dict[str, dict] = {}
        for row in verified_rows:
            s = row.get("sector_name", "Unknown")
            if s not in sector_data:
                sector_data[s] = {"total": 0, "correct": 0}
            sector_data[s]["total"] += 1
            if row.get("prediction_correct") == 1:
                sector_data[s]["correct"] += 1

        for sector_name, counts in sorted(sector_data.items()):
            t = counts["total"]
            c = counts["correct"]
            stats.by_sector.append(SectorBreakdown(
                sector=sector_name,
                total=t,
                correct=c,
                accuracy=round(c / t * 100, 1) if t > 0 else 0.0,
            ))

        # ── Accuracy over time (rolling per-report rate) ──────────
        # Group verified predictions by report date, compute per-report accuracy
        report_map: dict[str, dict] = {}
        for row in verified_rows:
            date_key = (row.get("report_date") or "")[:10]  # YYYY-MM-DD
            if date_key not in report_map:
                report_map[date_key] = {"total": 0, "correct": 0}
            report_map[date_key]["total"] += 1
            if row.get("prediction_correct") == 1:
                report_map[date_key]["correct"] += 1

        cumulative_total = 0
        cumulative_correct = 0
        for date_key in sorted(report_map.keys()):
            cumulative_total += report_map[date_key]["total"]
            cumulative_correct += report_map[date_key]["correct"]
            stats.accuracy_over_time.append({
                "date": date_key,
                "cumulative_accuracy": round(cumulative_correct / cumulative_total * 100, 1),
                "cumulative_total": cumulative_total,
            })

    finally:
        conn.close()

    return stats


def _normal_cdf(z: float) -> float:
    """Approximate normal CDF using error function (no scipy needed)."""
    import math
    return 0.5 * (1 + math.erf(z / math.sqrt(2)))
