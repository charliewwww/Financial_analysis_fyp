"""
CLI Entry Point — run analyses, evaluations, or quality reports.

Usage:
    python main.py                         # Analyze all sectors
    python main.py ai_semiconductors       # Analyze one sector
    python main.py --metrics               # Print quality metrics report
    python main.py --eval                  # Run evaluation suite
    python main.py --eval --judge          # Run evaluation with LLM-as-Judge
    python main.py --eval --report         # Run evaluation + print report
    python main.py --sync-dataset          # Sync eval dataset to Langfuse
"""

import sys
from config.logging_config import setup_logging

setup_logging("INFO")


def _run_analysis(sector_ids: list[str] | None = None):
    """Run the weekly analysis pipeline."""
    from workflows.weekly_analysis import run_weekly_analysis

    if sector_ids:
        print(f"Running analysis for: {', '.join(sector_ids)}")
    else:
        print("Running analysis for ALL sectors")

    reports = run_weekly_analysis(sector_ids=sector_ids)

    for report in reports:
        print(f"\n{'='*60}")
        print(f"  {report['sector_name']}")
        print(f"  Report ID: {report.get('report_id', 'N/A')}")
        print(f"  Confidence: {report.get('confidence', 'N/A')}/10")
        print(f"  News articles used: {report.get('news_count', 0)}")
        print(f"{'='*60}")

        if report.get("error"):
            print(f"  ERROR: {report['error']}")
        else:
            print(report["analysis"][:500] + "...")
            print(f"\n{'─'*40} VALIDATION {'─'*40}")
            print(report["validation"][:300] + "...")


def _run_metrics():
    """Print quality metrics report from Langfuse + local DB."""
    from evals.metrics import print_metrics_report
    print_metrics_report()


def _run_eval(include_judge: bool = False, show_report: bool = False):
    """Run the evaluation suite against the golden dataset."""
    from evals.runner import run_eval_suite, format_eval_report

    print("=" * 60)
    print("SUPPLY CHAIN ALPHA — Evaluation Suite")
    print("=" * 60)

    results = run_eval_suite(include_judge=include_judge)

    if not results:
        print("\nNo results — check LLM connection and logs.")
        sys.exit(1)

    passed = sum(1 for r in results if r.passed)
    total = len(results)
    print(f"\nResult: {passed}/{total} passed")

    if show_report:
        report = format_eval_report(results)
        print("\n" + report)

    if passed < total:
        sys.exit(1)


def _sync_dataset():
    """Sync evaluation dataset to Langfuse."""
    from evals.datasets import sync_dataset_to_langfuse
    sync_dataset_to_langfuse()
    print("Dataset synced to Langfuse.")


def main():
    args = sys.argv[1:]

    # Handle special flags
    if "--metrics" in args:
        _run_metrics()
        return

    if "--eval" in args:
        include_judge = "--judge" in args
        show_report = "--report" in args
        _run_eval(include_judge=include_judge, show_report=show_report)
        return

    if "--sync-dataset" in args:
        _sync_dataset()
        return

    # Default: run analysis
    sector_ids = [a for a in args if not a.startswith("--")] or None
    _run_analysis(sector_ids)


if __name__ == "__main__":
    main()
