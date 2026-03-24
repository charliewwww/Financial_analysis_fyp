"""
Evaluation Framework — Langfuse-powered evaluation for the multi-agent pipeline.

This module provides:
  - scoring.py:    Push quantitative scores to Langfuse traces after each run
  - llm_judge.py:  LLM-as-Judge evaluators for analysis quality dimensions
  - datasets.py:   Manage golden evaluation datasets for regression testing
  - runner.py:     Run evaluation suite and collect metrics
  - metrics.py:    Pull aggregated metrics from Langfuse for reporting

Usage (automatic — integrated into pipeline):
    Scores are automatically pushed to every Langfuse trace after pipeline runs.

Usage (manual — evaluation sweep):
    python -m evals.runner                # run all evals
    python -m evals.runner --report       # run + print summary report
"""
