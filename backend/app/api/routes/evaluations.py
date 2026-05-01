"""Evaluations router — exposes ablation study + detailed accuracy stats.

These are heavy operations, so each endpoint is read-only and deliberately
simple. The frontend calls them lazily from the Accuracy → "Ablation" tab.
"""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any

from fastapi import APIRouter, HTTPException

from app.pipeline import runner as _runner  # noqa: F401 — sys.path patch

router = APIRouter(tags=["evaluations"])


def _to_dict(obj: Any) -> Any:
    if is_dataclass(obj):
        return asdict(obj)
    if isinstance(obj, list):
        return [_to_dict(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _to_dict(v) for k, v in obj.items()}
    return obj


@router.get(
    "/evaluations/ablation",
    summary="Run the validation-layer ablation study",
)
async def get_ablation(max_reports: int = 100) -> dict:
    try:
        from evals.ablation_study import run_ablation_study  # type: ignore[import]
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"ablation module unavailable: {exc}",
        ) from exc
    result = run_ablation_study(max_reports=max_reports)
    return _to_dict(result)


@router.get(
    "/evaluations/accuracy-detailed",
    summary="Detailed prediction accuracy breakdown (direction, sector, time)",
)
async def get_detailed_accuracy() -> dict:
    try:
        from evals.prediction_stats import get_prediction_stats  # type: ignore[import]
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"prediction_stats module unavailable: {exc}",
        ) from exc
    stats = get_prediction_stats()
    return _to_dict(stats)
