"""
Evaluation Runner — execute the full eval suite and collect metrics.

Runs the pipeline against the evaluation dataset, computes all scores
(programmatic + LLM-as-Judge), and generates a summary report.

Usage:
    python -m evals.runner                      # run default dataset
    python -m evals.runner --report             # run + print summary
    python -m evals.runner --sync-dataset       # sync dataset to Langfuse
    python -m evals.runner --judge              # include LLM-as-Judge scoring
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from datetime import datetime, timezone

from evals.datasets import (
    EvalCase,
    EvalResult,
    get_default_dataset,
    evaluate_result,
    sync_dataset_to_langfuse,
)
from evals.scoring import push_scores_to_langfuse
from evals.llm_judge import run_llm_judge

logger = logging.getLogger(__name__)


def run_eval_case(
    case: EvalCase,
    include_judge: bool = False,
    progress_fn=None,
) -> EvalResult:
    """
    Run the pipeline for a single eval case and evaluate the result.

    1. Invokes the LangGraph pipeline for the sector
    2. Computes programmatic scores
    3. Optionally runs LLM-as-Judge
    4. Pushes all scores to Langfuse
    5. Returns structured EvalResult
    """
    from workflows.weekly_analysis import _run_sector_graph

    logger.info("Running eval case: %s", case.case_id)
    start = time.time()

    try:
        state = _run_sector_graph(
            case.sector_id,
            case.sector_config,
            progress_fn=progress_fn,
        )
    except Exception as e:
        logger.error("Eval case '%s' pipeline failed: %s", case.case_id, e)
        return EvalResult(
            case_id=case.case_id,
            passed=False,
            checks={"pipeline_completed": False},
            details={"pipeline_completed": f"Error: {e}"},
            scores={},
            judge_scores={},
            duration_seconds=round(time.time() - start, 1),
        )

    duration = round(time.time() - start, 1)

    # Compute programmatic scores and push to Langfuse
    scores = push_scores_to_langfuse(state)

    # Optionally run LLM-as-Judge
    judge_scores = {}
    if include_judge:
        judge_scores = run_llm_judge(state)

    # Evaluate against expectations
    result = evaluate_result(case, state, scores, judge_scores, duration)

    # Log result
    status = "PASS" if result.passed else "FAIL"
    logger.info(
        "Eval %s: %s (overall=%.2f, judge=%.2f, %.1fs)",
        case.case_id, status,
        scores.get("overall", 0),
        judge_scores.get("judge_overall", 0),
        duration,
    )

    return result


def run_eval_suite(
    cases: list[EvalCase] | None = None,
    include_judge: bool = False,
    progress_fn=None,
) -> list[EvalResult]:
    """
    Run all evaluation cases and return results.
    """
    if cases is None:
        cases = get_default_dataset()

    # Pre-flight health check
    from agents.llm_client import check_llm_health, LLMHealthCheckError
    try:
        check_llm_health()
    except LLMHealthCheckError as e:
        logger.error("LLM health check failed — cannot run evals: %s", e)
        return []

    results = []
    for i, case in enumerate(cases, 1):
        logger.info("━" * 50)
        logger.info("Eval case %d/%d: %s", i, len(cases), case.case_id)

        if progress_fn:
            progress_fn("eval_start", f"[{i}/{len(cases)}] {case.case_id}")

        result = run_eval_case(case, include_judge=include_judge, progress_fn=progress_fn)
        results.append(result)

        if progress_fn:
            status = "PASS" if result.passed else "FAIL"
            progress_fn("eval_done", f"{status}: {case.case_id}")

    return results


def format_eval_report(results: list[EvalResult]) -> str:
    """
    Format evaluation results as a readable Markdown report.
    """
    lines = []
    lines.append("# Evaluation Report")
    lines.append(f"**Date:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    lines.append(f"**Cases:** {len(results)}")
    passed = sum(1 for r in results if r.passed)
    lines.append(f"**Passed:** {passed}/{len(results)}")
    lines.append("")

    # Aggregate scores
    all_scores: dict[str, list[float]] = {}
    for r in results:
        for k, v in r.scores.items():
            all_scores.setdefault(k, []).append(v)
        for k, v in r.judge_scores.items():
            all_scores.setdefault(k, []).append(v)

    if all_scores:
        lines.append("## Aggregate Scores")
        lines.append("")
        lines.append("| Metric | Mean | Min | Max |")
        lines.append("|--------|------|-----|-----|")
        for metric in sorted(all_scores.keys()):
            vals = all_scores[metric]
            mean = sum(vals) / len(vals)
            lines.append(f"| {metric} | {mean:.3f} | {min(vals):.3f} | {max(vals):.3f} |")
        lines.append("")

    # Per-case details
    lines.append("## Per-Case Results")
    lines.append("")

    for r in results:
        status = "PASS ✅" if r.passed else "FAIL ❌"
        lines.append(f"### {r.case_id} — {status}")
        lines.append(f"Duration: {r.duration_seconds:.1f}s")
        lines.append("")

        lines.append("| Check | Result | Detail |")
        lines.append("|-------|--------|--------|")
        for check, passed_check in r.checks.items():
            icon = "✅" if passed_check else "❌"
            detail = r.details.get(check, "")
            lines.append(f"| {check} | {icon} | {detail} |")
        lines.append("")

        if r.scores:
            lines.append("**Programmatic Scores:**")
            for k, v in sorted(r.scores.items()):
                bar = "█" * int(v * 20) + "░" * (20 - int(v * 20))
                lines.append(f"  - {k}: {v:.3f} [{bar}]")
            lines.append("")

        if r.judge_scores:
            lines.append("**LLM Judge Scores:**")
            for k, v in sorted(r.judge_scores.items()):
                bar = "█" * int(v * 20) + "░" * (20 - int(v * 20))
                lines.append(f"  - {k}: {v:.3f} [{bar}]")
            lines.append("")

    # Improvement recommendations
    lines.append("## Recommended Improvements")
    lines.append("")

    weak_areas: dict[str, float] = {}
    for metric, vals in all_scores.items():
        mean = sum(vals) / len(vals)
        if mean < 0.6:
            weak_areas[metric] = mean

    if weak_areas:
        lines.append("Areas scoring below 0.6 (priority targets):")
        lines.append("")
        for metric, score in sorted(weak_areas.items(), key=lambda x: x[1]):
            lines.append(f"- **{metric}** ({score:.3f}): Needs improvement")
    else:
        lines.append("All metrics above 0.6 threshold — good baseline quality.")

    lines.append("")
    return "\n".join(lines)


# ── CLI Entry Point ──────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Run evaluation suite")
    parser.add_argument("--report", action="store_true", help="Print summary report")
    parser.add_argument("--judge", action="store_true", help="Include LLM-as-Judge scoring")
    parser.add_argument("--sync-dataset", action="store_true", help="Sync dataset to Langfuse")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")
    args = parser.parse_args()

    # Set up logging
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    if args.sync_dataset:
        sync_dataset_to_langfuse()
        return

    print("=" * 60)
    print("SUPPLY CHAIN ALPHA — Evaluation Suite")
    print("=" * 60)

    results = run_eval_suite(include_judge=args.judge)

    if not results:
        print("\nNo results — check LLM connection and logs.")
        sys.exit(1)

    if args.report:
        report = format_eval_report(results)
        print("\n" + report)

    # Summary
    passed = sum(1 for r in results if r.passed)
    total = len(results)
    print(f"\nResult: {passed}/{total} passed")

    if passed < total:
        sys.exit(1)


if __name__ == "__main__":
    main()
