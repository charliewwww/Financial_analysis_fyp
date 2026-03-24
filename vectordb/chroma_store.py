"""
ChromaDB Vector Store — persistent memory for the analysis pipeline.

WHY THIS EXISTS:
Without a vector store, every pipeline run starts from scratch. The LLM
has no memory of what it analyzed last week. This means:
- It can't say "margins have been declining for 3 consecutive quarters"
- It can't compare current news sentiment to last week's
- It can't track evolving narratives over time

ChromaDB gives us a local, embedded vector database. Every time the pipeline
runs, it stores:
1. News articles (title + summary, with source/date metadata)
2. SEC filing sections (MD&A, Risk Factors — the real text)
3. Analysis reports (the LLM's own previous conclusions)

Before the next analysis, we query this store for relevant historical context.
The LLM then sees both CURRENT data AND HISTORICAL context, enabling it
to reason about trends, not just snapshots.

ARCHITECTURE:
- ChromaDB PersistentClient stores data in ./chroma_db/ directory
- Default embedding: ChromaDB's built-in ONNX MiniLM model (no GPU needed)
- Three collections: news, filings, analyses
- Each document tagged with sector_id, run_id, date for filtering
- Graceful degradation: if chromadb isn't installed, pipeline runs fine without RAG
"""

from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timezone
from typing import TYPE_CHECKING

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from models.state import PipelineState, Article

# ── Graceful import ──────────────────────────────────────────────
# ChromaDB is optional. If not installed, all functions return empty
# results and the pipeline continues without RAG context.
try:
    import chromadb
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False

# ── Paths & Constants ────────────────────────────────────────────
CHROMA_DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "chroma_db"
)

# Collection names
COL_NEWS = "news_articles"
COL_FILINGS = "sec_filings"
COL_ANALYSES = "analysis_reports"

# How many results to return from each collection when querying
DEFAULT_N_RESULTS = 5

# Maximum document length (chars) to store per embedding
MAX_DOC_LENGTH = 2000


# ═══════════════════════════════════════════════════════════════════
# CLIENT MANAGEMENT
# ═══════════════════════════════════════════════════════════════════

_client = None


def _get_client():
    """Lazy-init ChromaDB PersistentClient. Cached for the session."""
    global _client
    if _client is None:
        if not CHROMADB_AVAILABLE:
            return None
        _client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
    return _client


def _get_collection(name: str):
    """Get or create a collection. Returns None if ChromaDB unavailable."""
    client = _get_client()
    if client is None:
        return None
    return client.get_or_create_collection(
        name=name,
        metadata={"hnsw:space": "cosine"},  # Cosine similarity for text
    )


def is_available() -> bool:
    """Check if ChromaDB is installed and functional."""
    return CHROMADB_AVAILABLE


# ═══════════════════════════════════════════════════════════════════
# INGEST: Store documents in the vector DB
# ═══════════════════════════════════════════════════════════════════

def ingest_articles(
    articles: list,
    sector_id: str,
    run_id: str,
) -> int:
    """
    Store news articles in the vector DB.

    Each article becomes a document: "TITLE\nSUMMARY"
    Metadata: source, published date, sector, run_id, link

    Returns number of documents ingested.
    """
    collection = _get_collection(COL_NEWS)
    if collection is None:
        return 0

    docs = []
    metadatas = []
    ids = []

    for i, article in enumerate(articles):
        # Build document text — articles may be Article dataclass or plain dict
        if hasattr(article, "__dataclass_fields__"):
            # Dataclass Article object
            title = getattr(article, "title", "")
            summary = getattr(article, "raw_summary", "") or getattr(article, "condensed_summary", "")
            source = getattr(article, "source", "")
            published = getattr(article, "published", "")
            link = getattr(article, "link", "")
        else:
            # Plain dict
            title = article.get("title", "")
            summary = article.get("raw_summary", "") or article.get("summary", "")
            source = article.get("source", "")
            published = article.get("published", "")
            link = article.get("link", "")

        doc = f"{title}\n{summary}"[:MAX_DOC_LENGTH]

        if len(doc.strip()) < 20:
            continue  # Skip empty articles

        meta = {
            "source": source[:100],
            "published": published[:20],
            "sector_id": sector_id,
            "run_id": run_id,
            "link": link[:500],
            "ingested_at": datetime.now(timezone.utc).isoformat()[:19],
            "doc_type": "news",
        }

        doc_id = f"{run_id}_{sector_id}_news_{i}"
        docs.append(doc)
        metadatas.append(meta)
        ids.append(doc_id)

    if docs:
        # ChromaDB upsert handles duplicates gracefully
        collection.upsert(documents=docs, metadatas=metadatas, ids=ids)

    return len(docs)


def ingest_filings(
    filings: list[dict],
    sector_id: str,
    run_id: str,
) -> int:
    """
    Store SEC filing text sections in the vector DB.

    Each filing section (MD&A, Risk Factors, etc.) becomes its own
    document for more precise retrieval.

    Returns number of documents ingested.
    """
    collection = _get_collection(COL_FILINGS)
    if collection is None:
        return 0

    docs = []
    metadatas = []
    ids = []

    for fi, filing in enumerate(filings):
        if "error" in filing:
            continue

        ticker = filing.get("ticker", "")
        ftype = filing.get("type", "")
        date = filing.get("date", "")

        for j, section in enumerate(filing.get("text_sections", [])):
            doc = (
                f"{ticker} {ftype} ({date}) — {section['name']}\n\n"
                f"{section['text']}"
            )[:MAX_DOC_LENGTH]

            if len(doc.strip()) < 50:
                continue

            meta = {
                "ticker": ticker,
                "filing_type": ftype,
                "date": date,
                "section_tag": section.get("tag", ""),
                "section_name": section.get("name", ""),
                "sector_id": sector_id,
                "run_id": run_id,
                "ingested_at": datetime.now(timezone.utc).isoformat()[:19],
                "doc_type": "filing",
            }

            # Include filing index (fi) to avoid duplicate IDs when same ticker
            # has multiple filings (e.g. 10-K + 10-Q) with same section tags
            doc_id = f"{run_id}_{sector_id}_filing_{ticker}_{fi}_{section.get('tag', j)}"
            docs.append(doc)
            metadatas.append(meta)
            ids.append(doc_id)

    if docs:
        collection.upsert(documents=docs, metadatas=metadatas, ids=ids)

    return len(docs)


def ingest_analysis(
    analysis_text: str,
    sector_id: str,
    sector_name: str,
    run_id: str,
    confidence_score: float = 0.0,
) -> int:
    """
    Store a completed analysis report in the vector DB.

    This enables the LLM to reference its OWN previous conclusions:
    "Last week I noted that NVDA margins were under pressure..."

    Returns number of documents ingested.
    """
    collection = _get_collection(COL_ANALYSES)
    if collection is None:
        return 0

    if not analysis_text or len(analysis_text.strip()) < 100:
        return 0

    # Split long analysis into chunks for better retrieval
    chunks = _split_into_chunks(analysis_text, chunk_size=MAX_DOC_LENGTH, overlap=200)

    docs = []
    metadatas = []
    ids = []

    for i, chunk in enumerate(chunks):
        meta = {
            "sector_id": sector_id,
            "sector_name": sector_name,
            "run_id": run_id,
            "confidence_score": str(confidence_score),
            "chunk_index": str(i),
            "total_chunks": str(len(chunks)),
            "ingested_at": datetime.now(timezone.utc).isoformat()[:19],
            "doc_type": "analysis",
        }

        doc_id = f"{run_id}_{sector_id}_analysis_{i}"
        docs.append(chunk)
        metadatas.append(meta)
        ids.append(doc_id)

    if docs:
        collection.upsert(documents=docs, metadatas=metadatas, ids=ids)

    return len(docs)


# ═══════════════════════════════════════════════════════════════════
# QUERY: Retrieve relevant historical context
# ═══════════════════════════════════════════════════════════════════

def query_relevant_context(
    sector_id: str,
    query_texts: list[str],
    exclude_run_id: str | None = None,
    n_results: int = DEFAULT_N_RESULTS,
) -> dict:
    """
    Query all collections for context relevant to the current analysis.

    Args:
        sector_id: Filter to this sector's data
        query_texts: Search queries (e.g., sector name, ticker names, key themes)
        exclude_run_id: Skip documents from the current run (avoid self-reference)
        n_results: Max results per collection per query

    Returns:
        Dict with:
        - news: list of {text, source, published, score}
        - filings: list of {text, ticker, type, date, section, score}
        - analyses: list of {text, run_id, confidence, score}
        - total_results: int
        - query_time_seconds: float
    """
    if not CHROMADB_AVAILABLE:
        return _empty_context()

    start = time.time()
    result = {
        "news": [],
        "filings": [],
        "analyses": [],
        "total_results": 0,
        "query_time_seconds": 0.0,
    }

    # Build the where filter for sector
    where_filter = {"sector_id": sector_id}

    # Query each collection
    for col_name, result_key, meta_extractor in [
        (COL_NEWS, "news", _extract_news_meta),
        (COL_FILINGS, "filings", _extract_filing_meta),
        (COL_ANALYSES, "analyses", _extract_analysis_meta),
    ]:
        try:
            collection = _get_collection(col_name)
            if collection is None or collection.count() == 0:
                continue

            query_result = collection.query(
                query_texts=query_texts,
                n_results=min(n_results, collection.count()),
                where=where_filter,
            )

            # Flatten results across query texts
            seen_ids = set()
            for batch_idx in range(len(query_result.get("ids", []))):
                batch_ids = query_result["ids"][batch_idx]
                batch_docs = query_result["documents"][batch_idx]
                batch_metas = query_result["metadatas"][batch_idx]
                batch_distances = query_result.get("distances", [[]])[batch_idx]

                for j, doc_id in enumerate(batch_ids):
                    # Skip current run's own documents
                    meta = batch_metas[j] if j < len(batch_metas) else {}
                    if exclude_run_id and meta.get("run_id") == exclude_run_id:
                        continue

                    # Deduplicate across queries
                    if doc_id in seen_ids:
                        continue
                    seen_ids.add(doc_id)

                    doc_text = batch_docs[j] if j < len(batch_docs) else ""
                    distance = batch_distances[j] if j < len(batch_distances) else 1.0
                    # ChromaDB cosine distance: 0 = identical, 2 = opposite
                    # Convert to similarity score: 1 - (distance/2)
                    similarity = round(1.0 - (distance / 2.0), 3)

                    entry = meta_extractor(doc_text, meta, similarity)
                    result[result_key].append(entry)

        except Exception as e:
            # Don't let a ChromaDB error crash the pipeline
            logger.warning("ChromaDB query error on %s: %s", col_name, e)
            continue

    # Sort each result list by similarity (best first)
    for key in ["news", "filings", "analyses"]:
        result[key].sort(key=lambda x: x.get("score", 0), reverse=True)

    result["total_results"] = sum(len(result[k]) for k in ["news", "filings", "analyses"])
    result["query_time_seconds"] = round(time.time() - start, 2)

    return result


def format_rag_context(context: dict, max_chars: int = 4000) -> str:
    """
    Format RAG query results into a text block for the LLM prompt.

    Returns empty string if no relevant context found.
    """
    if not context or context.get("total_results", 0) == 0:
        return ""

    lines = [
        "## HISTORICAL CONTEXT (from previous analyses)\n",
        "The following context was retrieved from your previous analysis runs. ",
        "Use it to identify TRENDS and CHANGES over time — not just this week's snapshot.\n",
    ]
    chars_used = sum(len(l) for l in lines)

    # Previous analyses (most valuable — the LLM's own prior reasoning)
    analyses = context.get("analyses", [])
    if analyses:
        lines.append("\n### Previous Analysis Insights")
        for a in analyses[:3]:  # Top 3
            chunk = a.get("text", "")[:800]
            if chars_used + len(chunk) > max_chars:
                break
            score = a.get("score", 0)
            lines.append(f"\n*[Relevance: {score:.0%} | Run: {a.get('run_id', '?')}]*")
            lines.append(chunk)
            chars_used += len(chunk) + 80

    # Previous filings context
    filings = context.get("filings", [])
    if filings and chars_used < max_chars - 500:
        lines.append("\n### Historical Filing Excerpts")
        for f in filings[:2]:
            chunk = f.get("text", "")[:600]
            if chars_used + len(chunk) > max_chars:
                break
            ticker = f.get("ticker", "?")
            ftype = f.get("type", "?")
            date = f.get("date", "?")
            lines.append(f"\n*[{ticker} {ftype} ({date}) — relevance: {f.get('score', 0):.0%}]*")
            lines.append(chunk)
            chars_used += len(chunk) + 80

    # Previous news (least priority — current news is already in the prompt)
    news = context.get("news", [])
    if news and chars_used < max_chars - 300:
        lines.append("\n### Related Past News")
        for n in news[:3]:
            text = n.get("text", "")[:300]
            if chars_used + len(text) > max_chars:
                break
            source = n.get("source", "?")
            published = n.get("published", "?")[:10]
            lines.append(f"- [{source}, {published}] {text}")
            chars_used += len(text) + 50

    # Only return if we actually got meaningful content
    if chars_used < 200:
        return ""

    lines.append(f"\n*({context['total_results']} total results retrieved in "
                 f"{context['query_time_seconds']:.1f}s)*")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════
# STATS & MANAGEMENT
# ═══════════════════════════════════════════════════════════════════

def get_store_stats() -> dict:
    """Get statistics about what's stored in the vector DB."""
    if not CHROMADB_AVAILABLE:
        return {"available": False, "reason": "chromadb not installed"}

    client = _get_client()
    if client is None:
        return {"available": False, "reason": "client init failed"}

    stats = {"available": True, "collections": {}}
    for col_name in [COL_NEWS, COL_FILINGS, COL_ANALYSES]:
        try:
            col = client.get_or_create_collection(name=col_name)
            stats["collections"][col_name] = {
                "count": col.count(),
            }
        except Exception as e:
            stats["collections"][col_name] = {"error": str(e)}

    stats["total_documents"] = sum(
        c.get("count", 0) for c in stats["collections"].values()
        if isinstance(c, dict) and "count" in c
    )
    stats["db_path"] = CHROMA_DB_PATH

    return stats


def clear_collection(collection_name: str) -> bool:
    """Delete all documents in a collection. Use carefully!"""
    client = _get_client()
    if client is None:
        return False
    try:
        collection = client.get_or_create_collection(name=collection_name)
        if collection.count() > 0:
            all_ids = collection.get()["ids"]
            if all_ids:
                collection.delete(ids=all_ids)
        return True
    except Exception:
        return False


# ═══════════════════════════════════════════════════════════════════
# INTERNAL HELPERS
# ═══════════════════════════════════════════════════════════════════

def _empty_context() -> dict:
    return {
        "news": [],
        "filings": [],
        "analyses": [],
        "total_results": 0,
        "query_time_seconds": 0.0,
    }


def _extract_news_meta(text: str, meta: dict, score: float) -> dict:
    return {
        "text": text,
        "source": meta.get("source", ""),
        "published": meta.get("published", ""),
        "score": score,
    }


def _extract_filing_meta(text: str, meta: dict, score: float) -> dict:
    return {
        "text": text,
        "ticker": meta.get("ticker", ""),
        "type": meta.get("filing_type", ""),
        "date": meta.get("date", ""),
        "section": meta.get("section_name", ""),
        "score": score,
    }


def _extract_analysis_meta(text: str, meta: dict, score: float) -> dict:
    return {
        "text": text,
        "run_id": meta.get("run_id", ""),
        "confidence": meta.get("confidence_score", ""),
        "score": score,
    }


def _split_into_chunks(
    text: str,
    chunk_size: int = 2000,
    overlap: int = 200,
) -> list[str]:
    """
    Split text into overlapping chunks for embedding.

    Uses sentence-boundary splitting where possible.
    """
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0

    while start < len(text):
        end = start + chunk_size

        # Try to end at a sentence boundary
        if end < len(text):
            # Look for ". " within the last 200 chars of the chunk
            boundary = text.rfind(". ", max(start, end - 200), end)
            if boundary > start:
                end = boundary + 1  # Include the period

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        # Move start forward, with overlap for context continuity
        start = end - overlap if end < len(text) else len(text)

    return chunks
