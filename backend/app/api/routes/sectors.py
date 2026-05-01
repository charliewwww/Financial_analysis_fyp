"""Sectors router — exposes the curated `config/sectors.py` to the frontend.

This is read-only metadata: the dropdown on the pipeline page, the supply
chain page, and any future admin UI all consume `GET /api/v1/sectors`.

The legacy module lives at the repo root (added to sys.path by
app.pipeline.runner at import time).
"""

from __future__ import annotations

from fastapi import APIRouter

from app.pipeline import runner as _runner  # noqa: F401 — ensures sys.path patch

from config.sectors import SECTORS  # type: ignore[import]  # legacy module

router = APIRouter(tags=["sectors"])


@router.get(
    "/sectors",
    summary="List configured sectors",
    description=(
        "Returns the curated sector universe defined in `config/sectors.py`. "
        "Used by the pipeline trigger dropdown and the supply chain page."
    ),
)
async def list_sectors() -> list[dict]:
    return [
        {
            "id": sid,
            "name": s["name"],
            "description": s.get("description", ""),
            "tickers": s["tickers"],
        }
        for sid, s in SECTORS.items()
    ]
