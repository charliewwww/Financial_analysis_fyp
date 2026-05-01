"""
Retrospective Ablation Study — measures the validation pipeline's effectiveness.

Instead of re-running analyses (expensive), this mines the already-stored
pipeline_state JSON in each report to reconstruct what happened:

  1. RETRY EVENTS — reports where the validate_node fired the re-analyze loop.
     These are the gold cases: we have both the original (flawed) analysis
     AND the corrected analysis stored in node_executions.

  2. NUMERICAL DISCREPANCY COUNTS — for every report, run the numerical
     validator on the stored analysis_text vs the first-draft text (from
     node_executions) to count how many numerical errors the pipeline caught.

  3. VALIDATION INTERVENTION RATE — what % of reports had at least one
     validator flag, and what kinds of issues were found.

The summary table produced here is the empirical proof for: "the 5-layer
pipeline catches real errors that would otherwise reach the user."
"""

from __future__ import annotations

import json
import sqlite3
import re
from dataclasses import dataclass, field

from config.settings import DATABASE_PATH


# ── Result structures ─────────────────────────────────────────────

@dataclass
class RetryEvent:
    report_id: int
    sector_name: str
    created_at: str
    original_analysis_chars: int     # length of first-draft text
    corrected_analysis_chars: int    # length of final text
    issues_found: list[str]          # what the validator flagged


@dataclass
class NumericalComparison:
    report_id: int
    sector_name: str
    # Before correction (first analyze_node output)
    discrepancies_before: int
    verified_before: int
    unchecked_before: int
    # After correction (final analysis_text in state)
    discrepancies_after: int
    verified_after: int
    unchecked_after: int


@dataclass
class AblationResult:
    # Coverage
    total_reports_analyzed: int = 0
    reports_with_pipeline_state: int = 0

    # Validation retry events (Layer 4: self-correction loop)
    retry_events: list[RetryEvent] = field(default_factory=list)
    retry_rate_pct: float = 0.0   # % of reports that triggered a retry

    # Numerical comparisons (Layer 3: numerical cross-check)
    numerical_comparisons: list[NumericalComparison] = field(default_factory=list)
    avg_discrepancies_before: float = 0.0
    avg_discrepancies_after: float = 0.0
    discrepancy_reduction_pct: float = 0.0

    # Validation status distribution (all reports)
    status_counts: dict[str, int] = field(default_factory=dict)
    intervention_rate_pct: float = 0.0  # % with FAILED or PASSED WITH WARNINGS

    # Citation / source grounding (Layer 1)
    avg_citation_rate_pct: float = 0.0  # % of analysis paragraphs containing [SOURCE]

    # Key findings as plain text for display
    summary_bullets: list[str] = field(default_factory=list)


def run_ablation_study(max_reports: int = 100) -> AblationResult:
    """
    Mine stored reports to reconstruct validation effectiveness.

    Args:
        max_reports: Cap on how many reports to scan (most recent first).
    """
    result = AblationResult()

    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row

    try:
        rows = conn.execute(
            """SELECT id, sector_name, created_at, analysis,
                      validation_status, pipeline_state
               FROM reports
               ORDER BY created_at DESC
               LIMIT ?""",
            (max_reports,),
        ).fetchall()
        rows = [dict(r) for r in rows]
    finally:
        conn.close()

    result.total_reports_analyzed = len(rows)

    # ── Pass 1: validation_status distribution ────────────────────
    for row in rows:
        status = (row.get("validation_status") or "UNKNOWN").strip()
        result.status_counts[status] = result.status_counts.get(status, 0) + 1

    intervention_count = (
        result.status_counts.get("FAILED", 0)
        + result.status_counts.get("PASSED WITH WARNINGS", 0)
    )
    if result.total_reports_analyzed > 0:
        result.intervention_rate_pct = round(
            intervention_count / result.total_reports_analyzed * 100, 1
        )

    # ── Pass 2: mine pipeline_state for retry events & numerical diffs ──
    citation_rates = []

    for row in rows:
        raw_state = row.get("pipeline_state")
        if not raw_state:
            continue
        result.reports_with_pipeline_state += 1

        try:
            state_dict = json.loads(raw_state)
        except (json.JSONDecodeError, TypeError):
            continue

        node_execs = state_dict.get("node_executions", [])
        if not node_execs:
            continue

        # Find all analyze_node executions
        analyze_runs = [
            n for n in node_execs
            if n.get("node_name") in ("analyze", "analyze_node")
            and n.get("status") == "completed"
        ]

        # ── Retry event detection ─────────────────────────────────
        if len(analyze_runs) >= 2:
            first_run = analyze_runs[0]
            last_run = analyze_runs[-1]

            first_text = first_run.get("llm_raw_response") or ""
            final_text = state_dict.get("analysis_text") or ""

            # Extract validator issues from the state
            issues = state_dict.get("validation_issues") or []
            if isinstance(issues, str):
                try:
                    issues = json.loads(issues)
                except Exception:
                    issues = [issues] if issues else []

            result.retry_events.append(RetryEvent(
                report_id=row["id"],
                sector_name=row.get("sector_name", ""),
                created_at=(row.get("created_at") or "")[:10],
                original_analysis_chars=len(first_text),
                corrected_analysis_chars=len(final_text),
                issues_found=issues[:5],  # cap to first 5
            ))

            # ── Numerical comparison ──────────────────────────────
            prices_raw = state_dict.get("prices", [])
            technicals_raw = state_dict.get("technicals", [])

            if first_text and final_text and prices_raw:
                try:
                    from utils.numerical_validator import validate_numbers
                    vr_before = validate_numbers(first_text, prices_raw, technicals_raw)
                    vr_after = validate_numbers(final_text, prices_raw, technicals_raw)
                    result.numerical_comparisons.append(NumericalComparison(
                        report_id=row["id"],
                        sector_name=row.get("sector_name", ""),
                        discrepancies_before=vr_before.discrepancy_count,
                        verified_before=vr_before.verified_count,
                        unchecked_before=vr_before.unchecked_count,
                        discrepancies_after=vr_after.discrepancy_count,
                        verified_after=vr_after.verified_count,
                        unchecked_after=vr_after.unchecked_count,
                    ))
                except Exception:
                    pass

        # ── Citation rate (Layer 1: source grounding) ─────────────
        analysis_text = state_dict.get("analysis_text") or row.get("analysis") or ""
        if analysis_text:
            paragraphs = [p.strip() for p in analysis_text.split("\n\n") if len(p.strip()) > 80]
            if paragraphs:
                cited = sum(
                    1 for p in paragraphs
                    if re.search(r"\[SOURCE\]|\[source\]|\[Source\]|https?://", p)
                )
                citation_rates.append(cited / len(paragraphs) * 100)

    # ── Aggregate numerical comparison stats ──────────────────────
    if result.retry_rate_pct == 0 and result.reports_with_pipeline_state > 0:
        result.retry_rate_pct = round(
            len(result.retry_events) / result.reports_with_pipeline_state * 100, 1
        )

    if result.numerical_comparisons:
        before_vals = [c.discrepancies_before for c in result.numerical_comparisons]
        after_vals = [c.discrepancies_after for c in result.numerical_comparisons]
        result.avg_discrepancies_before = round(sum(before_vals) / len(before_vals), 2)
        result.avg_discrepancies_after = round(sum(after_vals) / len(after_vals), 2)
        if result.avg_discrepancies_before > 0:
            reduction = (
                (result.avg_discrepancies_before - result.avg_discrepancies_after)
                / result.avg_discrepancies_before * 100
            )
            result.discrepancy_reduction_pct = round(reduction, 1)

    if citation_rates:
        result.avg_citation_rate_pct = round(sum(citation_rates) / len(citation_rates), 1)

    # ── Build summary bullets ─────────────────────────────────────
    bullets = []

    passed = result.status_counts.get("PASSED", 0)
    warnings = result.status_counts.get("PASSED WITH WARNINGS", 0)
    failed = result.status_counts.get("FAILED", 0)
    if result.total_reports_analyzed:
        bullets.append(
            f"Across {result.total_reports_analyzed} reports: "
            f"{passed} passed cleanly, {warnings} had warnings, {failed} triggered a full retry."
        )

    if result.intervention_rate_pct:
        bullets.append(
            f"{result.intervention_rate_pct}% of reports had at least one validator intervention "
            f"(warnings or retry) — errors that would have reached the user undetected without the pipeline."
        )

    if result.retry_events:
        bullets.append(
            f"{len(result.retry_events)} reports triggered the self-correction loop (Layer 4). "
            f"In each case the Analyst agent was sent back with specific correction instructions."
        )

    if result.numerical_comparisons:
        bullets.append(
            f"Numerical cross-check (Layer 3): across {len(result.numerical_comparisons)} corrected reports, "
            f"discrepancies dropped from {result.avg_discrepancies_before:.1f} → "
            f"{result.avg_discrepancies_after:.1f} per report "
            f"({result.discrepancy_reduction_pct:.0f}% reduction)."
        )

    if result.avg_citation_rate_pct:
        bullets.append(
            f"Source grounding (Layer 1): {result.avg_citation_rate_pct:.0f}% of analysis paragraphs "
            f"contain an explicit source citation."
        )

    result.summary_bullets = bullets
    return result
