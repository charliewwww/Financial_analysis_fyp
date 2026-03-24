"""
Metrics Aggregation — pull evaluation data from Langfuse and local DB.

Provides functions to compute summary statistics across pipeline runs,
enabling your mentor to see quality trends and improvement opportunities.

Key metrics:
  - Score trends over time (per dimension)
  - Prediction accuracy tracking
  - Model comparison baselines
  - Failure mode analysis

These can be printed as a CLI report or fed into the Streamlit dashboard.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


def get_langfuse_score_summary(
    days: int = 30,
    score_names: list[str] | None = None,
) -> dict[str, dict]:
    """
    Pull aggregated scores from Langfuse for the last N days.

    Returns:
        {score_name: {"mean": float, "min": float, "max": float, "count": int, "trend": str}}

    The "trend" field is "improving", "declining", or "stable" based on
    comparing the first half vs second half of the period.
    """
    from config.settings import LANGFUSE_ENABLED

    if not LANGFUSE_ENABLED:
        logger.info("Langfuse disabled — returning empty metrics")
        return {}

    try:
        import os
        import httpx

        # Langfuse v3 SDK has no fetch_traces(); use the REST API directly.
        host = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com").rstrip("/")
        pub_key = os.getenv("LANGFUSE_PUBLIC_KEY", "")
        sec_key = os.getenv("LANGFUSE_SECRET_KEY", "")

        if not pub_key or not sec_key:
            logger.info("Langfuse credentials not set — returning empty metrics")
            return {}

        # GET /api/public/scores — returns paginated score list
        url = f"{host}/api/public/scores"
        params: dict[str, Any] = {"limit": 200, "orderBy": "timestamp.desc"}
        if score_names:
            # The API supports filtering by name (one at a time);
            # we'll fetch all and filter client-side for simplicity.
            pass

        resp = httpx.get(url, auth=(pub_key, sec_key), params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        scores_list = data.get("data", [])
        if not scores_list:
            logger.info("No scores found in Langfuse")
            return {}

        # Collect scores: {name: [(timestamp, value), ...]}
        score_data: dict[str, list[tuple[str, float]]] = {}

        for s in scores_list:
            name = s.get("name", "")
            value = s.get("value")
            ts = s.get("timestamp", "")

            if value is None:
                continue
            if score_names and name not in score_names:
                continue

            try:
                score_data.setdefault(name, []).append((str(ts), float(value)))
            except (TypeError, ValueError):
                continue

        # Compute summary stats
        summary = {}
        for name, pairs in score_data.items():
            values = [v for _, v in pairs]
            if not values:
                continue

            mid = len(values) // 2
            first_half = values[mid:]   # Older (reversed order from API)
            second_half = values[:mid]  # Newer

            first_mean = sum(first_half) / len(first_half) if first_half else 0
            second_mean = sum(second_half) / len(second_half) if second_half else 0

            if second_mean > first_mean + 0.05:
                trend = "improving"
            elif second_mean < first_mean - 0.05:
                trend = "declining"
            else:
                trend = "stable"

            summary[name] = {
                "mean": round(sum(values) / len(values), 3),
                "min": round(min(values), 3),
                "max": round(max(values), 3),
                "count": len(values),
                "trend": trend,
                "first_half_mean": round(first_mean, 3),
                "second_half_mean": round(second_mean, 3),
            }

        return summary

    except Exception as e:
        logger.error("Failed to fetch Langfuse metrics: %s", e)
        return {}


def get_prediction_tracking_summary() -> dict:
    """
    Get prediction accuracy tracking from the local SQLite database.

    Returns a dict with:
      - total_predictions
      - checked / unchecked counts
      - direction_accuracy_pct
      - avg_absolute_weekly_change
      - per_sector_accuracy
    """
    try:
        from database.reports_db import (
            get_prediction_accuracy,
            get_prediction_accuracy_over_time,
        )

        overall = get_prediction_accuracy()
        per_report = get_prediction_accuracy_over_time()

        # Group by sector
        per_sector: dict[str, dict] = {}
        for entry in per_report:
            sector = entry["sector_name"]
            if sector not in per_sector:
                per_sector[sector] = {"correct": 0, "total": 0}
            per_sector[sector]["correct"] += entry["correct"]
            per_sector[sector]["total"] += entry["correct"] + entry["wrong"]

        for sector, data in per_sector.items():
            if data["total"] > 0:
                data["accuracy_pct"] = round(data["correct"] / data["total"] * 100, 1)
            else:
                data["accuracy_pct"] = None

        return {
            **overall,
            "per_sector_accuracy": per_sector,
            "timeline": per_report,
        }

    except Exception as e:
        logger.error("Failed to get prediction tracking: %s", e)
        return {}


def format_metrics_report(langfuse_summary: dict, prediction_summary: dict) -> str:
    """
    Format a readable metrics report for your mentor.

    Shows:
      - Langfuse score trends per dimension
      - Prediction accuracy tracking
      - Weak areas requiring improvement
    """
    lines = []
    lines.append("=" * 60)
    lines.append("SUPPLY CHAIN ALPHA — Quality Metrics Report")
    lines.append(f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    lines.append("=" * 60)

    # ── Langfuse Evaluation Scores ────────────────────────────────
    if langfuse_summary:
        lines.append("")
        lines.append("## EVALUATION SCORES (from Langfuse)")
        lines.append("")
        lines.append(f"{'Metric':<30} {'Mean':>6} {'Min':>6} {'Max':>6} {'N':>4}  {'Trend':<12}")
        lines.append("─" * 75)

        # Sort: overall first, then alphabetical
        sorted_metrics = sorted(
            langfuse_summary.items(),
            key=lambda x: (0 if "overall" in x[0] else 1, x[0]),
        )

        for name, stats in sorted_metrics:
            trend_icon = {
                "improving": "↑ improving",
                "declining": "↓ declining",
                "stable":    "→ stable",
            }.get(stats["trend"], "?")

            lines.append(
                f"  {name:<28} {stats['mean']:>6.3f} {stats['min']:>6.3f} "
                f"{stats['max']:>6.3f} {stats['count']:>4}  {trend_icon}"
            )

        # Identify weak areas
        weak = [(k, v["mean"]) for k, v in langfuse_summary.items() if v["mean"] < 0.5]
        if weak:
            lines.append("")
            lines.append("  ⚠ WEAK AREAS (mean < 0.50):")
            for name, score in sorted(weak, key=lambda x: x[1]):
                lines.append(f"    → {name}: {score:.3f}")
    else:
        lines.append("")
        lines.append("## EVALUATION SCORES")
        lines.append("  No Langfuse data available. Run the pipeline with Langfuse enabled.")

    # ── Prediction Accuracy ───────────────────────────────────────
    lines.append("")
    lines.append("## PREDICTION TRACKING")

    if prediction_summary:
        total = prediction_summary.get("total_predictions", 0)
        checked = prediction_summary.get("checked", 0)
        accuracy = prediction_summary.get("direction_accuracy_pct")

        lines.append(f"  Total predictions:    {total}")
        lines.append(f"  Checked (7+ days):    {checked}")
        lines.append(f"  Unchecked (pending):  {prediction_summary.get('unchecked', 0)}")

        if accuracy is not None:
            lines.append(f"  Direction accuracy:   {accuracy:.1f}%")
            lines.append(f"  Avg weekly |change|:  {prediction_summary.get('avg_absolute_weekly_change', 'N/A')}%")
        else:
            lines.append("  Direction accuracy:   Not enough data yet")

        per_sector = prediction_summary.get("per_sector_accuracy", {})
        if per_sector:
            lines.append("")
            lines.append("  Per-sector accuracy:")
            for sector, data in per_sector.items():
                acc = f"{data['accuracy_pct']:.1f}%" if data.get("accuracy_pct") is not None else "N/A"
                lines.append(f"    {sector}: {acc} ({data['correct']}/{data['total']})")
    else:
        lines.append("  No prediction data available yet.")

    lines.append("")
    lines.append("=" * 60)

    return "\n".join(lines)


def print_metrics_report():
    """Pull all metrics and print a formatted report."""
    langfuse_summary = get_langfuse_score_summary()
    prediction_summary = get_prediction_tracking_summary()
    report = format_metrics_report(langfuse_summary, prediction_summary)
    print(report)
    return report
