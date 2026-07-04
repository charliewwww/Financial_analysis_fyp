"""System health router — exposes a quick snapshot of the runtime
configuration so the frontend can surface "is everything wired up?" info.
"""

from __future__ import annotations

import os

from fastapi import APIRouter, Depends

from app.core.auth import require_admin
from app.core.config import settings
from app.core.models_catalog import list_model_options
from app.pipeline import runner as _runner  # noqa: F401 — sys.path patch

# Operator/system info is admin-only — enforced server-side, not just in the UI.
router = APIRouter(tags=["system"], dependencies=[Depends(require_admin)])


def _chromadb_doc_count() -> int:
    """Best-effort count of documents in the Chroma store.
    Returns 0 if Chroma is unavailable or empty."""
    try:
        from vectordb.chroma_store import get_store_stats  # type: ignore[import]

        stats = get_store_stats()
        if not stats.get("available"):
            return 0
        return int(stats.get("total_documents", 0) or 0)
    except Exception:
        return 0


def _chromadb_collections() -> list[dict]:
    """Best-effort per-collection document counts for the Chroma store."""
    try:
        from vectordb.chroma_store import get_store_stats  # type: ignore[import]

        stats = get_store_stats()
        if not stats.get("available"):
            return []
        collections: list[dict] = []
        for name, info in (stats.get("collections") or {}).items():
            if isinstance(info, dict) and "count" in info:
                collections.append({"name": name, "count": int(info["count"])})
        return collections
    except Exception:
        return []



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


@router.get(
    "/system/vectordb",
    summary="Vector store statistics",
)
async def system_vectordb() -> dict:
    """Per-collection document counts in the vector store, so the Stocks
    control panel can show how much news/evidence is currently indexed."""
    collections = _chromadb_collections()
    by_name = {c["name"]: c["count"] for c in collections}
    # Friendly aliases for the collections the product cares about most.
    news_count = by_name.get("news_articles", 0)
    return {
        "total_docs": sum(c["count"] for c in collections),
        "news_articles": news_count,
        "collections": collections,
    }


@router.get(
    "/system/models",
    summary="Curated model allow-list",
)
async def system_models() -> dict:
    """The models a user may pick for the next pipeline run."""
    options = list_model_options()
    return {
        "provider": settings.llm_provider,
        "default": settings.reasoning_model,
        "options": options,
    }

