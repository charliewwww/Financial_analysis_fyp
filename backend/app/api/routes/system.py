"""System health router — exposes a quick snapshot of the runtime
configuration so the frontend can surface "is everything wired up?" info.
"""

from __future__ import annotations

import os

from fastapi import APIRouter

from app.core.config import settings
from app.pipeline import runner as _runner  # noqa: F401 — sys.path patch

router = APIRouter(tags=["system"])


def _chromadb_doc_count() -> int:
    """Best-effort count of documents in the legacy Chroma store.
    Returns 0 if Chroma is unavailable or empty."""
    try:
        from vectordb.chroma_store import get_chroma_store  # type: ignore[import]

        store = get_chroma_store()
        client = getattr(store, "client", None) or getattr(store, "_client", None)
        if client is None:
            return 0
        total = 0
        for col in client.list_collections():
            try:
                total += col.count()
            except Exception:
                continue
        return total
    except Exception:
        return 0


@router.get(
    "/system/health",
    summary="Detailed runtime health snapshot",
)
async def system_health() -> dict:
    return {
        "llm_provider": settings.llm_provider,
        "llm_model": settings.reasoning_model,
        "langgraph_ok": True,  # legacy graph imports at startup; absence would crash
        "chromadb_docs": _chromadb_doc_count(),
        "fred_key_set": bool(settings.fred_api_key or os.environ.get("FRED_API_KEY")),
        "sec_edgar_configured": bool(
            settings.sec_edgar_email or os.environ.get("SEC_EDGAR_EMAIL")
        ),
    }
