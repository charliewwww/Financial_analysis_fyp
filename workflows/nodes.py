"""
Pipeline Nodes — each node is a function: (PipelineState) -> PipelineState.

These map 1:1 to the LangGraph StateGraph (see weekly_analysis.py):
    fetch_node      → "fetch"          Fetch news, prices, technicals, filings, macro, ingest vectordb
    summarize_node  → "summarize"      LLM condenses raw articles
    reflect_node    → "reflect"        LLM evaluates data sufficiency
    analyze_node    → "analyze"        RAG query + main LLM analysis
    validate_node   → "validate"       Programmatic + LLM fact-check
    score_node      → "score"          Objective confidence scoring
    save_node       → "save"           Ingest analysis into ChromaDB + save to SQLite

Conditional edges:
    reflect → should_refetch  → fetch (loop) or analyze (proceed)
    validate → should_reanalyze → analyze (loop) or score (proceed)

Node functions are pure (PipelineState) → PipelineState transforms.
The orchestrator in weekly_analysis.py wires them via langgraph.StateGraph.
"""

from models.state import PipelineState, NodeRunner, Article
from data_sources.rss_fetcher import fetch_news_for_sector
from data_sources.yahoo_finance import get_sector_prices
from data_sources.sec_edgar import get_filings_with_text, format_filings_for_prompt
from data_sources.technical_analysis import compute_sector_technicals
from data_sources.fred_macro import get_macro_snapshot, format_macro_for_prompt
from vectordb.chroma_store import (
    ingest_articles as rag_ingest_articles,
    ingest_filings as rag_ingest_filings,
    ingest_analysis as rag_ingest_analysis,
    query_relevant_context as rag_query,
    format_rag_context,
    is_available as rag_is_available,
)
from agents.llm_client import call_llm, call_llm_fast
from utils.prompts import (
    SYSTEM_PROMPT_ANALYST,
    SYSTEM_PROMPT_VALIDATOR,
    build_analysis_prompt,
    build_validation_prompt,
)
from config.settings import REASONING_MODEL, FAST_MODEL, MAX_PROMPT_CHARS
from database.reports_db import save_report_from_state
from utils.numerical_validator import validate_numbers
from utils.anomaly_detection import detect_anomalies
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
import re

logger = logging.getLogger(__name__)


# ── Langfuse trace helper ────────────────────────────────────────

def _lf_kwargs(state: PipelineState, node_name: str) -> dict:
    """
    Build Langfuse keyword args for an LLM call inside a pipeline node.

    When a sector-level trace exists (state.langfuse_trace_id), all LLM
    calls are grouped under that single trace — giving ONE row per sector
    in the Langfuse dashboard instead of one row per LLM call.

    If Langfuse is disabled the dict is empty and call_llm ignores it.
    """
    from config.settings import LANGFUSE_ENABLED
    if not LANGFUSE_ENABLED:
        return {}
    kwargs = {
        "langfuse_name": f"{node_name} — {state.sector_name}",
        "langfuse_metadata": {
            "sector_id": state.sector_id,
            "sector_name": state.sector_name,
            "tickers": state.sector_tickers,
            "node": node_name,
            "session_id": f"run-{state.created_at}" if state.created_at else None,
            "tags": [f"sector:{state.sector_id}", f"node:{node_name}"],
        },
    }
    # Group under the sector-level trace (created in _run_sector_graph)
    if state.langfuse_trace_id:
        kwargs["langfuse_trace_id"] = state.langfuse_trace_id
    return kwargs


# ── Langfuse RAG span helper ─────────────────────────────────────

def _lf_span(state: PipelineState, span_name: str, input_data: dict | None = None):
    """
    Create a Langfuse span under the sector-level trace for non-LLM
    operations (RAG query, RAG ingest, etc.).

    Returns a span object with .update(output=...) and .end() methods,
    or None if Langfuse is disabled. Use as:

        span = _lf_span(state, "rag_query", {"queries": [...]})
        # ... do work ...
        if span:
            span.update(output={"total_results": 8, "top_score": 0.82})
            span.end()
    """
    from config.settings import LANGFUSE_ENABLED
    if not LANGFUSE_ENABLED or not state.langfuse_trace_id:
        return None
    try:
        from langfuse import Langfuse
        lf = Langfuse()
        span = lf.start_span(
            trace_context={"trace_id": state.langfuse_trace_id},
            name=span_name,
            input=input_data or {},
            metadata={
                "sector_id": state.sector_id,
                "node": span_name,
            },
        )
        return span
    except Exception as e:
        logger.debug("Langfuse span '%s' failed: %s", span_name, e)
        return None


# ── Token budget helper ──────────────────────────────────────────

def _truncate_prompt(prompt: str, max_chars: int = MAX_PROMPT_CHARS) -> str:
    """
    Truncate a prompt to fit within the token budget.

    GLM-4.7-Flash has ~128k context but reasoning tokens eat into the
    budget. We cap the *user* prompt to MAX_PROMPT_CHARS (~60k default,
    roughly ~15k tokens) to leave headroom for system prompt + output.

    Truncation strategy (priority-based):
      1. Keep summary, anomaly alerts, technical indicators, prices, supply
         chain map, and closing instructions intact (high-value sections).
      2. Trim the RECENT NEWS section first (already summarized upstream).
      3. Trim SEC filing text second (verbose raw text).
      4. Only as a last resort, fall back to head/tail split.
    """
    if len(prompt) <= max_chars:
        return prompt

    trimmed_chars = len(prompt) - max_chars
    logger.warning("Prompt too long (%d chars, budget %d) — trimming %d chars",
                   len(prompt), max_chars, trimmed_chars)

    # ── Strategy 1: Trim RECENT NEWS section (already summarized) ─
    news_start = prompt.find("## RECENT NEWS")
    news_end = prompt.find("\n---", news_start + 1) if news_start != -1 else -1
    if news_start != -1 and news_end != -1:
        news_section = prompt[news_start:news_end]
        if len(news_section) > 2000:
            # Keep first 2000 chars of news (top articles) + notice
            trimmed_news = news_section[:2000] + (
                f"\n\n[... {len(news_section) - 2000:,} chars of news trimmed — "
                f"see AI-GENERATED NEWS SUMMARY above for full coverage ...]\n"
            )
            prompt = prompt[:news_start] + trimmed_news + prompt[news_end:]
            if len(prompt) <= max_chars:
                logger.info("Trimmed news section → %d chars (within budget)", len(prompt))
                return prompt

    # ── Strategy 2: Trim SEC filings section ──────────────────────
    filings_start = prompt.find("## RECENT SEC FILINGS")
    filings_end = prompt.find("\n---", filings_start + 1) if filings_start != -1 else -1
    if filings_start != -1 and filings_end != -1:
        filings_section = prompt[filings_start:filings_end]
        if len(filings_section) > 3000:
            trimmed_filings = filings_section[:3000] + (
                f"\n\n[... {len(filings_section) - 3000:,} chars of filing text trimmed ...]\n"
            )
            prompt = prompt[:filings_start] + trimmed_filings + prompt[filings_end:]
            if len(prompt) <= max_chars:
                logger.info("Trimmed filings section → %d chars (within budget)", len(prompt))
                return prompt

    # ── Strategy 3: Fallback head/tail split ──────────────────────
    over = len(prompt) - max_chars
    head_budget = int(max_chars * 0.6)
    tail_budget = max_chars - head_budget

    truncation_notice = (
        f"\n\n[... {over:,} characters trimmed to fit context window — "
        f"high-value sections (TA, prices, supply chain) preserved ...]\n\n"
    )

    result = prompt[:head_budget] + truncation_notice + prompt[-tail_budget:]
    logger.info("Prompt truncated (fallback): %d → %d chars (-%d)",
                len(prompt), len(result), over)
    return result


# ═══════════════════════════════════════════════════════════════════
# NODE 1: FETCH SOURCE
# Pulls raw data from all external sources (RSS, Yahoo, SEC, TA)
# ═══════════════════════════════════════════════════════════════════

def _fetch_news(sector_dict: dict) -> list[dict]:
    """Thread target: fetch RSS news articles."""
    return fetch_news_for_sector(sector_dict)


def _fetch_prices(tickers: list[str]) -> list[dict]:
    """Thread target: fetch Yahoo Finance prices."""
    return get_sector_prices(tickers)


def _fetch_technicals(tickers: list[str]) -> list[dict]:
    """Thread target: compute technical indicators."""
    return compute_sector_technicals(tickers)


def _fetch_filings(tickers: list[str]) -> list[dict]:
    """Thread target: fetch SEC EDGAR filings."""
    filings = []
    for ticker in tickers:  # Removed [:3] cap — fetch filings for all sector tickers
        ticker_filings = get_filings_with_text(
            ticker,
            filing_types=["10-K", "10-Q", "8-K"],
            max_filings=2,
            max_text_chars=6000,
        )
        filings.extend(ticker_filings)
    return filings


def _fetch_macro() -> dict:
    """Thread target: fetch FRED macro snapshot."""
    return get_macro_snapshot()


def fetch_node(state: PipelineState) -> PipelineState:
    """
    Fetch all raw data for the sector — concurrently.

    Uses ThreadPoolExecutor to run all five I/O-bound data fetches
    (news, prices, technicals, filings, macro) in parallel instead of
    sequentially. Typical wall-time drops from ~30-45s to ~10-15s.

    Reads: sector_id, sector_tickers, sector_keywords
    Writes: articles, prices, technicals, filings, fetch_metadata

    On re-fetch (retry), broadens search by including the sector name
    and description words as extra keywords so we get different results.
    """
    sector_dict = _state_to_sector_dict(state)

    # On re-fetch, broaden the keyword list so we actually get NEW data
    if state.fetch_retry_count > 0:
        extra_keywords = state.sector_name.lower().split()
        extra_keywords += state.sector_description.lower().split()[:10]
        for info in state.sector_supply_chain_map.values():
            role_words = info.get("role", "").lower().split()
            extra_keywords.extend(w for w in role_words if len(w) > 3)
        existing = set(kw.lower() for kw in sector_dict.get("keywords", []))
        broadened = [kw for kw in extra_keywords if kw not in existing and len(kw) > 3]
        sector_dict["keywords"] = list(sector_dict.get("keywords", [])) + broadened[:15]
        logger.info("Re-fetch: broadened keywords (+%d terms)", len(broadened[:15]))

    # ── Launch all fetches concurrently ───────────────────────────
    logger.info("Starting concurrent data fetch (5 sources)...")
    with ThreadPoolExecutor(max_workers=5, thread_name_prefix="fetch") as pool:
        fut_news = pool.submit(_fetch_news, sector_dict)
        fut_prices = pool.submit(_fetch_prices, state.sector_tickers)
        fut_technicals = pool.submit(_fetch_technicals, state.sector_tickers)
        fut_filings = pool.submit(_fetch_filings, state.sector_tickers)
        fut_macro = pool.submit(_fetch_macro)

        # Wait for all and collect results (exceptions propagate on .result())
        futures = {
            "news": fut_news,
            "prices": fut_prices,
            "technicals": fut_technicals,
            "filings": fut_filings,
            "macro": fut_macro,
        }
        results = {}
        for name, fut in futures.items():
            try:
                results[name] = fut.result(timeout=120)
            except Exception as exc:
                logger.error("Concurrent fetch '%s' failed: %s", name, exc)
                results[name] = [] if name != "macro" else {}

    # ── Record results into state with NodeRunner logging ─────────
    with NodeRunner(state, "fetch_news") as node:
        node.input_keys = ["sector_keywords", "sector_tickers"]
        node.output_keys = ["articles", "fetch_metadata"]
        raw_articles = results["news"]
        state.articles = [
            Article(
                title=a.get("title", ""),
                source=a.get("source", ""),
                link=a.get("link", ""),
                published=a.get("published", "unknown"),
                raw_summary=a.get("summary", ""),
                relevance_tag=a.get("relevance", ""),
            )
            for a in raw_articles
        ]
        state.fetch_metadata = {
            "total_articles": len(state.articles),
            "sources": list(set(a.source for a in state.articles)),
            "source_counts": _count_by_source(state.articles),
        }
        node.decision = f"fetched_{len(state.articles)}_articles"

    with NodeRunner(state, "fetch_prices") as node:
        node.input_keys = ["sector_tickers"]
        node.output_keys = ["prices"]
        state.prices = results["prices"]
        valid = [p for p in state.prices if not p.get("error")]
        logger.info("Got price data for %d/%d tickers", len(valid), len(state.sector_tickers))
        node.decision = f"{len(valid)}/{len(state.sector_tickers)}_valid"

    with NodeRunner(state, "fetch_technicals") as node:
        node.input_keys = ["sector_tickers"]
        node.output_keys = ["technicals"]
        state.technicals = results["technicals"]
        valid = [t for t in state.technicals if not t.get("error")]
        logger.info("Computed technicals for %d/%d tickers", len(valid), len(state.sector_tickers))
        node.decision = f"{len(valid)}/{len(state.sector_tickers)}_valid"

    with NodeRunner(state, "fetch_filings") as node:
        node.input_keys = ["sector_tickers"]
        node.output_keys = ["filings"]
        state.filings = results["filings"]
        valid = [f for f in state.filings if "error" not in f]
        with_text = [f for f in valid if f.get("text_total_chars", 0) > 0]
        logger.info("Found %d filings (%d with extracted text)", len(valid), len(with_text))

    with NodeRunner(state, "fetch_macro") as node:
        node.input_keys = []
        node.output_keys = ["macro_data"]
        state.macro_data = results["macro"]
        meta = state.macro_data.get("_meta", {})
        if meta.get("api_status") == "ok":
            count = meta.get("indicators_fetched", 0)
            logger.info("Got %d macro indicators (Fed rate, CPI, GDP, etc.)", count)
        elif meta.get("api_status") == "unavailable":
            logger.info("Skipped — %s", meta.get('reason', 'no API key'))
        else:
            logger.info("Partial — some indicators failed")
        node.decision = meta.get("api_status", "unknown")

    # ── Ingest into vector DB (best-effort, after all data collected) ──
    with NodeRunner(state, "ingest_vectordb") as node:
        node.input_keys = ["articles", "filings"]
        node.output_keys = []
        if rag_is_available():
            logger.info("Ingesting into vector store...")
            span = _lf_span(state, "rag_ingest_fetch", {
                "articles_count": len(state.articles),
                "filings_count": len(state.filings),
            })
            n_news = rag_ingest_articles(state.articles, state.sector_id, state.run_id)
            n_filings = rag_ingest_filings(state.filings, state.sector_id, state.run_id)
            logger.info("Stored %d articles + %d filing sections", n_news, n_filings)
            if span:
                span.update(output={"news_stored": n_news, "filings_stored": n_filings})
                span.end()
            node.decision = f"{n_news}_news_{n_filings}_filings"
        else:
            logger.info("Vector store: skipped (chromadb not installed)")
            node.decision = "unavailable"

    return state


# ═══════════════════════════════════════════════════════════════════
# NODE 2: SUMMARIZE
# LLM condenses raw articles into key bullet points
# ═══════════════════════════════════════════════════════════════════

SYSTEM_PROMPT_SUMMARIZER = """You are a financial news summarizer. Given a list of news articles 
about a specific sector, produce:

1. A BRIEF SUMMARY (2-3 sentences) capturing the overall narrative
2. A list of KEY BULLET POINTS (5-10) — the most important facts, each with 
   [SOURCE: feed name] citation

Focus on: earnings, product launches, supply chain disruptions, regulatory 
changes, M&A activity, and analyst upgrades/downgrades.

Be concise. No filler. Every bullet must contain a concrete fact or number.
"""


def summarize_node(state: PipelineState) -> PipelineState:
    """
    Summarize raw articles into condensed key points.

    Reads: articles
    Writes: news_summary, summary_bullet_points, articles[].condensed_summary
    """
    if not state.articles:
        state.news_summary = "No articles to summarize."
        return state

    with NodeRunner(state, "summarize") as node:
        node.input_keys = ["articles"]
        node.output_keys = ["news_summary", "summary_bullet_points"]
        node.llm_model = FAST_MODEL

        # Build the summarization prompt with article details
        articles_text = ""
        for i, article in enumerate(state.articles[:25], 1):  # Cap at 25
            articles_text += (
                f"{i}. [{article.source}] {article.title}\n"
                f"   Link: {article.link}\n"
                f"   Date: {article.published[:10] if article.published != 'unknown' else 'unknown'}\n"
                f"   Content: {article.raw_summary[:600]}\n\n"
            )

        user_prompt = (
            f"Summarize these {len(state.articles)} articles about the "
            f"**{state.sector_name}** sector:\n\n{articles_text}"
        )

        node.llm_user_prompt = user_prompt
        node.llm_system_prompt = SYSTEM_PROMPT_SUMMARIZER[:200]  # Truncated for storage

        response = call_llm_fast(
            prompt=user_prompt,
            system_prompt=SYSTEM_PROMPT_SUMMARIZER,
            **_lf_kwargs(state, "summarize"),
        )

        node.llm_raw_response = response

        state.news_summary = response

        # Extract bullet points from the response
        bullet_lines = [
            line.strip().lstrip("-•*").strip()
            for line in response.split("\n")
            if line.strip().startswith(("-", "•", "*")) and len(line.strip()) > 10
        ]
        state.summary_bullet_points = bullet_lines

        # Give each article a condensed tag based on whether it appeared in summary
        for article in state.articles:
            for bullet in bullet_lines:
                if article.title[:30].lower() in bullet.lower() or article.source.lower() in bullet.lower():
                    article.condensed_summary = bullet
                    break

        node.decision = f"{len(bullet_lines)}_bullet_points"

    return state


# ═══════════════════════════════════════════════════════════════════
# NODE 3: REFLECT ON DATA
# LLM evaluates data sufficiency — should we fetch more?
# ═══════════════════════════════════════════════════════════════════

SYSTEM_PROMPT_REFLECTOR = """You are a data quality assessor for financial analysis. 
Given a summary of available data, determine if there is ENOUGH information 
to produce a reliable sector analysis.

Evaluate these dimensions:
1. NEWS COVERAGE: Are there enough recent articles (ideally 10+)?
2. PRICE DATA: Do we have prices for most tickers in the sector?
3. TECHNICAL DATA: Are technical indicators available?
4. SEC FILINGS: Any recent filings for context?
5. DIVERSITY: Are articles from multiple sources, or just one?

Respond with EXACTLY this format:
VERDICT: SUFFICIENT | INSUFFICIENT | MARGINAL
GAPS: [list any missing data points]
REASONING: [1-2 sentences explaining your verdict]
"""


def reflect_node(state: PipelineState) -> PipelineState:
    """
    Evaluate data sufficiency. If insufficient AND retries remain,
    the orchestrator loops back to Fetch.

    Reads: articles, prices, technicals, filings, news_summary, fetch_retry_count
    Writes: data_sufficiency, sufficiency_reasoning, data_gaps
    """
    with NodeRunner(state, "reflect") as node:
        node.input_keys = ["articles", "prices", "technicals", "filings", "news_summary"]
        node.output_keys = ["data_sufficiency", "sufficiency_reasoning", "data_gaps"]
        node.llm_model = FAST_MODEL

        # Build a data inventory for the reflector
        valid_prices = [p for p in state.prices if not p.get("error")]
        valid_ta = [t for t in state.technicals if not t.get("error")]
        valid_filings = [f for f in state.filings if "error" not in f]

        macro_status = "available" if state.macro_data.get("_meta", {}).get("api_status") == "ok" else "unavailable"
        macro_count = state.macro_data.get("_meta", {}).get("indicators_fetched", 0)

        data_inventory = (
            f"SECTOR: {state.sector_name}\n"
            f"TICKERS: {', '.join(state.sector_tickers)}\n\n"
            f"DATA INVENTORY:\n"
            f"- News articles: {len(state.articles)} "
            f"(from {len(set(a.source for a in state.articles))} sources)\n"
            f"- Price data: {len(valid_prices)}/{len(state.sector_tickers)} tickers\n"
            f"- Technical indicators: {len(valid_ta)}/{len(state.sector_tickers)} tickers\n"
            f"- SEC filings: {len(valid_filings)}\n"
            f"- Macro indicators: {macro_count} ({macro_status})\n"
            f"- Fetch retries so far: {state.fetch_retry_count}/{state.max_fetch_retries}\n\n"
            f"NEWS SUMMARY:\n{state.news_summary[:500]}\n"
        )

        node.llm_user_prompt = data_inventory
        node.llm_system_prompt = SYSTEM_PROMPT_REFLECTOR[:200]

        response = call_llm_fast(
            prompt=data_inventory,
            system_prompt=SYSTEM_PROMPT_REFLECTOR,
            **_lf_kwargs(state, "reflect"),
        )

        node.llm_raw_response = response

        # Parse the verdict
        response_upper = response.upper()
        if "INSUFFICIENT" in response_upper:
            state.data_sufficiency = "insufficient"
        elif "MARGINAL" in response_upper:
            state.data_sufficiency = "marginal"
        else:
            state.data_sufficiency = "sufficient"

        state.sufficiency_reasoning = response

        # Extract gaps
        gaps = []
        for line in response.split("\n"):
            stripped = line.strip().lstrip("-•*").strip()
            if stripped and ("gap" in line.lower() or "missing" in line.lower()
                          or line.strip().startswith("-")):
                if "GAPS:" not in line.upper():
                    gaps.append(stripped)
        state.data_gaps = gaps

        node.decision = state.data_sufficiency
        node.decision_reason = state.sufficiency_reasoning[:200]

        # Increment retry counter HERE (inside the node) so LangGraph
        # persists it. Conditional edge functions must be read-only.
        if state.data_sufficiency == "insufficient":
            state.fetch_retry_count += 1

        # Print the reflection result
        icon = {"sufficient": "✅", "marginal": "⚠️", "insufficient": "❌"}.get(
            state.data_sufficiency, "❓"
        )
        logger.info("Data reflection: %s %s", icon, state.data_sufficiency.upper())
        if state.data_gaps:
            for gap in state.data_gaps[:3]:
                logger.info("  Gap: %s", gap)

    return state


# ═══════════════════════════════════════════════════════════════════
# NODE 4: ANALYSIS / REASONING
# Main LLM analysis with full supply-chain reasoning
# ═══════════════════════════════════════════════════════════════════

def analyze_node(state: PipelineState) -> PipelineState:
    """
    Run the main LLM analysis with all available data.

    Reads: articles, prices, technicals, filings, news_summary, sector_*
    Writes: analysis_text, analysis_prompt_used
    """
    sector_dict = _state_to_sector_dict(state)

    # Convert Article objects back to dicts for the prompt builder.
    # Pass condensed_summary separately so build_analysis_prompt can
    # prefer it over the raw summary (avoids feeding raw text the
    # summarizer already processed).
    news_dicts = [
        {
            "title": a.title,
            "summary": a.raw_summary,
            "condensed_summary": a.condensed_summary or "",
            "source": a.source,
            "published": a.published,
            "link": a.link,
            "relevance": a.relevance_tag,
        }
        for a in state.articles
        if a.used_in_analysis
    ]

    # ── Query vector store for historical context ────────────────
    with NodeRunner(state, "rag_query") as node:
        node.input_keys = ["sector_id", "sector_keywords", "sector_tickers"]
        node.output_keys = ["rag_context", "rag_metadata"]
        if rag_is_available():
            logger.info("Querying vector store for historical context...")
            # Build diverse queries: sector name, key tickers, keywords
            queries = [
                f"{state.sector_name} supply chain analysis",
                " ".join(state.sector_tickers[:5]),
            ]
            if state.sector_keywords:
                queries.append(" ".join(state.sector_keywords[:5]))

            span = _lf_span(state, "rag_query", {
                "queries": queries,
                "sector_id": state.sector_id,
                "exclude_run_id": state.run_id,
            })

            rag_result = rag_query(
                sector_id=state.sector_id,
                query_texts=queries,
                exclude_run_id=state.run_id,  # Don't retrieve our own current data
                n_results=5,
            )
            state.rag_context = format_rag_context(rag_result, max_chars=4000)
            state.rag_metadata = {
                "total_results": rag_result.get("total_results", 0),
                "query_time_seconds": rag_result.get("query_time_seconds", 0),
                "news_hits": len(rag_result.get("news", [])),
                "filing_hits": len(rag_result.get("filings", [])),
                "analysis_hits": len(rag_result.get("analyses", [])),
            }

            # Log top similarity scores for Langfuse visibility
            all_scores = (
                [r.get("score", 0) for r in rag_result.get("news", [])]
                + [r.get("score", 0) for r in rag_result.get("filings", [])]
                + [r.get("score", 0) for r in rag_result.get("analyses", [])]
            )
            if span:
                span.update(output={
                    **state.rag_metadata,
                    "top_score": round(max(all_scores), 3) if all_scores else 0,
                    "min_score": round(min(all_scores), 3) if all_scores else 0,
                    "context_chars": len(state.rag_context),
                })
                span.end()
            if state.rag_context:
                logger.info("Found %d relevant docs (%.1fs)",
                            rag_result['total_results'], rag_result['query_time_seconds'])
            else:
                logger.info("No prior-run context yet (historical context builds after each run)")
            node.decision = f"{rag_result.get('total_results', 0)}_results"
        else:
            state.rag_context = ""
            state.rag_metadata = {}
            logger.info("RAG query: skipped (chromadb not installed)")
            node.decision = "unavailable"

    with NodeRunner(state, "analyze") as node:
        node.input_keys = ["articles", "prices", "technicals", "filings", "macro_data", "news_summary", "rag_context"]
        node.output_keys = ["analysis_text", "analysis_prompt_used"]
        node.llm_model = REASONING_MODEL

        # Build the analysis prompt (reuses existing prompt builder)
        prompt = build_analysis_prompt(
            sector_dict, news_dicts, state.prices, state.filings, state.technicals,
        )

        # Inject macroeconomic context if available
        macro_text = format_macro_for_prompt(state.macro_data)
        if macro_text:
            prompt = f"{macro_text}\n\n---\n\n{prompt}"

        # Inject anomaly alerts if any unusual signals detected
        anomaly_report = detect_anomalies(state.technicals)
        anomaly_text = anomaly_report.format_for_prompt()
        if anomaly_text:
            prompt = f"{anomaly_text}\n\n---\n\n{prompt}"
            state.anomaly_alerts = anomaly_report.to_dict_list()

        # Inject RAG historical context if available
        if state.rag_context:
            prompt = f"{state.rag_context}\n\n---\n\n{prompt}"

        # Prepend the LLM summary if available, so the analyst has context
        if state.news_summary and state.news_summary != "No articles to summarize.":
            prompt = (
                f"## AI-GENERATED NEWS SUMMARY\n"
                f"(Condensed from {len(state.articles)} articles — see raw data below)\n\n"
                f"{state.news_summary}\n\n---\n\n{prompt}"
            )

        # ── Self-correction: inject validation feedback on re-analyze ──
        if state.validation_retry_count > 0 and state.validation_issues:
            correction_block = (
                "## ⚠️ SELF-CORRECTION REQUIRED — PREVIOUS ANALYSIS REJECTED\n\n"
                f"Your previous analysis (attempt {state.validation_retry_count}) was "
                f"rejected by the validation layer with status: **{state.validation_status}**.\n\n"
                "**You MUST fix the following issues in this revision:**\n\n"
            )
            for i, issue in enumerate(state.validation_issues, 1):
                correction_block += f"{i}. {issue}\n"
            correction_block += (
                "\n**Instructions:**\n"
                "- Correct every factual error listed above using the source data provided.\n"
                "- Do NOT repeat the same mistakes.\n"
                "- If a number was wrong, use the 'actual' value from the validation.\n"
                "- If reasoning was flawed, strengthen the logical chain.\n"
                "- Keep the same output format (Thesis → Evidence → CoT → Risk → Confidence).\n"
            )
            prompt = f"{correction_block}\n---\n\n{prompt}"
            logger.info("Injected %d validation issues into re-analysis prompt",
                        len(state.validation_issues))

        state.analysis_prompt_used = prompt

        # Apply token budget — truncate if prompt exceeds MAX_PROMPT_CHARS
        prompt = _truncate_prompt(prompt)

        node.llm_user_prompt = prompt
        node.llm_system_prompt = SYSTEM_PROMPT_ANALYST[:200]

        logger.info("Reasoning about %s...", state.sector_name)
        response = call_llm(
            prompt=prompt,
            system_prompt=SYSTEM_PROMPT_ANALYST,
            temperature=0.3,
            max_tokens=4096,
            **_lf_kwargs(state, "analyze"),
        )

        node.llm_raw_response = response
        state.analysis_text = response
        # Parse AI predictions from the analysis text
        state.ai_predictions = _parse_predictions(response, state.sector_tickers)
        if state.ai_predictions:
            logger.info("Parsed %d AI predictions: %s",
                       len(state.ai_predictions),
                       ", ".join(p['ticker'] for p in state.ai_predictions))
    return state


# ═══════════════════════════════════════════════════════════════════
# NODE 5: VALIDATION
# LLM fact-checks the analysis, optionally loops back to Analyze
# ═══════════════════════════════════════════════════════════════════

def validate_node(state: PipelineState) -> PipelineState:
    """
    Two-layer validation:
      1. PROGRAMMATIC: Extract numbers from analysis, compare against real data
         (deterministic — no LLM involved, numbers either match or they don't)
      2. LLM: Check reasoning quality, logic, and source citations
         (nuanced — catches bad reasoning even when numbers are correct)

    Reads: analysis_text, prices, technicals
    Writes: validation_text, validation_status, validation_issues
    """
    # ── Layer 1: Programmatic numerical cross-check ──────────────
    with NodeRunner(state, "validate_numbers") as node:
        node.input_keys = ["analysis_text", "prices", "technicals"]
        node.output_keys = ["validation_issues"]

        logger.info("Layer 1: Programmatic number check...")
        num_result = validate_numbers(
            analysis_text=state.analysis_text,
            prices=state.prices,
            technicals=state.technicals,
        )

        programmatic_report = num_result.to_markdown()
        programmatic_status = num_result.status
        programmatic_issues = [
            f"⚠️ {c.ticker}: {c.claim_type} claimed={_fmt(c.claimed_value)} "
            f"actual={_fmt(c.actual_value)} (off by {c.deviation_pct:+.1f}%)"
            for c in num_result.checks if c.is_error
        ]

        logger.info("Checked %d claims: %d verified, %d discrepancies, %d unchecked",
                    len(num_result.checks), num_result.verified_count,
                    num_result.discrepancy_count, num_result.unchecked_count)

        node.decision = f"{num_result.verified_count}ok_{num_result.discrepancy_count}err"

    # ── Layer 2: LLM reasoning quality check ─────────────────────
    with NodeRunner(state, "validate_reasoning") as node:
        node.input_keys = ["analysis_text", "prices"]
        node.output_keys = ["validation_text", "validation_status"]
        node.llm_model = REASONING_MODEL

        # Include programmatic results so the LLM knows what's already checked
        augmented_prompt = (
            f"## PROGRAMMATIC VALIDATION ALREADY DONE\n"
            f"The following numerical claims have been automatically verified "
            f"against real market data:\n\n{programmatic_report}\n\n---\n\n"
            f"Numbers are already checked above — do NOT repeat that work.\n"
            f"Your job is to evaluate REASONING QUALITY across 4 dimensions:\n"
            f"1. Logical consistency (thesis vs evidence)\n"
            f"2. Citation completeness ([SOURCE: ...] tags)\n"
            f"3. Supply chain reasoning depth (2nd/3rd order effects)\n"
            f"4. Prediction-evidence alignment (TA signals vs direction calls)\n\n"
        )
        prompt = augmented_prompt + build_validation_prompt(state.analysis_text, state.prices)

        node.llm_user_prompt = prompt
        node.llm_system_prompt = SYSTEM_PROMPT_VALIDATOR[:200]

        logger.info("Layer 2: LLM reasoning check...")
        response = call_llm(
            prompt=prompt,
            system_prompt=SYSTEM_PROMPT_VALIDATOR,
            temperature=0.1,
            max_tokens=2048,
            **_lf_kwargs(state, "validate"),
        )

        node.llm_raw_response = response

        # Parse LLM validation status — use regex anchored to status
        # lines to avoid false positives (e.g. "the company never failed")
        _status_match = re.search(
            r'(?:^|\n)\s*(?:STATUS|VALIDATION|RESULT|OVERALL)[:\s]*(FAILED|PASSED|WARNING)',
            response,
            re.IGNORECASE,
        )
        if _status_match:
            _matched = _status_match.group(1).upper()
            if _matched == "FAILED":
                llm_status = "FAILED"
            elif _matched == "WARNING":
                llm_status = "PASSED WITH WARNINGS"
            else:
                llm_status = "PASSED"
        else:
            # Fallback: count occurrences to reduce false positives
            response_upper = response.upper()
            fail_count = response_upper.count("FAILED")
            pass_count = response_upper.count("PASSED")
            if fail_count > 0 and fail_count >= pass_count:
                llm_status = "FAILED"
            elif "WARNING" in response_upper or "DISCREPANCY" in response_upper:
                llm_status = "PASSED WITH WARNINGS"
            else:
                llm_status = "PASSED"

        # Extract LLM issues
        llm_issues = []
        for line in response.split("\n"):
            if "⚠️" in line or "DISCREPANCY" in line.upper():
                llm_issues.append(line.strip())

        # ── Merge both layers ────────────────────────────────────
        all_issues = programmatic_issues + llm_issues

        # Overall status: worst of the two layers wins
        if programmatic_status == "FAILED" or llm_status == "FAILED":
            state.validation_status = "FAILED"
        elif "WARNING" in programmatic_status or "WARNING" in llm_status:
            state.validation_status = "PASSED WITH WARNINGS"
        elif programmatic_status == "PASSED" and llm_status == "PASSED":
            state.validation_status = "PASSED"
        else:
            state.validation_status = "PASSED WITH WARNINGS"

        # Increment retry counter HERE (inside the node) so LangGraph
        # persists it. Conditional edge functions must be read-only.
        if state.validation_status == "FAILED":
            state.validation_retry_count += 1

        # Combined validation report
        state.validation_text = (
            f"{programmatic_report}\n\n"
            f"---\n\n"
            f"## LLM REASONING VALIDATION\n\n"
            f"{response}"
        )
        state.validation_issues = all_issues

        node.decision = state.validation_status
        node.decision_reason = f"{len(all_issues)} total issues ({len(programmatic_issues)} numeric, {len(llm_issues)} reasoning)"

        logger.info("Combined: %s (%d numeric + %d reasoning issues)",
                    state.validation_status, len(programmatic_issues), len(llm_issues))

    return state


def _fmt(value) -> str:
    """Quick format helper for validation messages."""
    if value is None:
        return "N/A"
    if isinstance(value, float) and abs(value) >= 1e9:
        return f"${value/1e9:.1f}B"
    if isinstance(value, float) and abs(value) >= 1e6:
        return f"${value/1e6:.0f}M"
    return f"{value}"


# ═══════════════════════════════════════════════════════════════════
# NODE 6: SCORE
# Objective confidence scoring based on data quality
# ═══════════════════════════════════════════════════════════════════

def score_node(state: PipelineState) -> PipelineState:
    """
    Compute honest confidence score (1-10) based on data quality
    AND analysis quality — not just "did we get data?".

    Dimensions (max 10):
        News coverage     max 2.5  (volume, source diversity, recency)
        Price data        max 2.0  (valid ratio)
        Technicals        max 1.0  (valid ratio)
        SEC filings       max 0.5  (presence of filing text)
        Macro data        max 1.0  (indicator count)
        Source diversity   max 1.0  (penalise single-source reliance)
        Validation result max 2.0  (PASSED / WARNING / FAILED)

    Reads: articles, prices, technicals, filings, macro_data, validation_status
    Writes: confidence_score, confidence_breakdown
    """
    with NodeRunner(state, "score") as node:
        node.input_keys = ["articles", "prices", "technicals", "filings", "macro_data", "validation_text"]
        node.output_keys = ["confidence_score", "confidence_breakdown"]

        breakdown: dict[str, float] = {}

        # ── 1. News coverage (max 2.5) ───────────────────────────
        n = len(state.articles)
        if n >= 9:
            news_pts = 2.5
        elif n >= 4:
            news_pts = 1.5
        elif n >= 1:
            news_pts = 0.5
        else:
            news_pts = 0.0
        breakdown["news_coverage"] = news_pts

        # ── 2. Price data quality (max 2.0) ──────────────────────
        valid_prices = [p for p in state.prices if not p.get("error")]
        price_pts = 0.0
        if state.prices:
            price_pts = round(len(valid_prices) / len(state.prices) * 2.0, 2)
        breakdown["price_data"] = price_pts

        # ── 3. Technical analysis quality (max 1.0) ──────────────
        valid_ta = [t for t in state.technicals if not t.get("error")]
        ta_pts = 0.0
        if state.technicals:
            ta_pts = round(len(valid_ta) / len(state.technicals) * 1.0, 2)
        breakdown["technicals"] = ta_pts

        # ── 4. SEC filings (max 0.5) ─────────────────────────────
        valid_filings = [f for f in state.filings if "error" not in f]
        filing_pts = 0.5 if valid_filings else 0.0
        breakdown["filings"] = filing_pts

        # ── 5. Macro data (max 1.0) ──────────────────────────────
        macro_meta = state.macro_data.get("_meta", {})
        macro_pts = 0.0
        if macro_meta.get("api_status") == "ok":
            fetched = macro_meta.get("indicators_fetched", 0)
            macro_pts = min(round(fetched / 6 * 1.0, 2), 1.0)
        elif macro_meta.get("api_status") == "partial":
            macro_pts = 0.3
        breakdown["macro_data"] = macro_pts

        # ── 6. Source diversity (max 1.0) ─────────────────────────
        #   Penalise single-source reliance. If 80%+ of articles
        #   come from one feed, cap this component at 0.25.
        diversity_pts = 0.0
        if state.articles:
            sources = [a.source for a in state.articles]
            unique_sources = len(set(sources))
            if unique_sources >= 4:
                diversity_pts = 1.0
            elif unique_sources == 3:
                diversity_pts = 0.75
            elif unique_sources == 2:
                diversity_pts = 0.5
            else:
                diversity_pts = 0.25
            # Extra penalty: if any single source dominates (>80%)
            most_common_count = max(sources.count(s) for s in set(sources))
            if most_common_count / len(sources) > 0.8:
                diversity_pts = min(diversity_pts, 0.25)
        breakdown["source_diversity"] = diversity_pts

        # ── 7. Validation result (max 2.0) ───────────────────────
        if state.validation_status == "FAILED":
            val_pts = 0.0
        elif "WARNING" in state.validation_status:
            val_pts = 1.0
        elif "PASSED" in state.validation_status:
            val_pts = 2.0
        else:
            val_pts = 1.0
        breakdown["validation"] = val_pts

        # ── Total ────────────────────────────────────────────────
        raw = sum(breakdown.values())
        state.confidence_score = min(round(raw, 1), 10.0)
        state.confidence_breakdown = breakdown

        node.decision = f"score={state.confidence_score}"
        logger.info(
            "Confidence: %.1f/10 — news=%.1f price=%.1f ta=%.1f "
            "filings=%.1f macro=%.1f diversity=%.1f validation=%.1f",
            state.confidence_score,
            breakdown["news_coverage"], breakdown["price_data"],
            breakdown["technicals"], breakdown["filings"],
            breakdown["macro_data"], breakdown["source_diversity"],
            breakdown["validation"],
        )

    return state


# ═══════════════════════════════════════════════════════════════════
# NODE 7: SAVE
# Ingest analysis into ChromaDB + persist report to SQLite
# ═══════════════════════════════════════════════════════════════════

def save_node(state: PipelineState) -> PipelineState:
    """
    Store the completed analysis in ChromaDB and save report to SQLite.

    Reads: analysis_text, sector_id, sector_name, run_id, confidence_score
    Writes: report_id
    """
    # ── Ingest completed analysis into vector store (best-effort) ─
    with NodeRunner(state, "ingest_analysis") as node:
        node.input_keys = ["analysis_text", "sector_id", "confidence_score"]
        node.output_keys = []
        try:
            if rag_is_available() and state.analysis_text:
                span = _lf_span(state, "rag_ingest_analysis", {
                    "sector_id": state.sector_id,
                    "confidence_score": state.confidence_score,
                    "analysis_length": len(state.analysis_text),
                })
                n = rag_ingest_analysis(
                    analysis_text=state.analysis_text,
                    sector_id=state.sector_id,
                    sector_name=state.sector_name,
                    run_id=state.run_id,
                    confidence_score=state.confidence_score,
                )
                logger.info("Stored analysis in vector DB (%d chunks)", n)
                if span:
                    span.update(output={"chunks_stored": n})
                    span.end()
                node.decision = f"{n}_chunks"
            else:
                node.decision = "skipped"
        except Exception as e:
            logger.warning("Vector DB analysis ingest: %s", e)
            node.decision = f"error"

    # ── Save to SQLite ────────────────────────────────────────────
    with NodeRunner(state, "save_to_db") as node:
        node.input_keys = ["analysis_text", "validation_text", "confidence_score", "prices"]
        node.output_keys = ["report_id"]
        state.report_id = save_report_from_state(state)
        node.decision = f"report_id={state.report_id}"
        logger.info("Report #%s saved to database", state.report_id)

    # ── Purge old reports (keep predictions) ──────────────────────
    try:
        from database.reports_db import purge_old_reports
        purged = purge_old_reports()
        if purged:
            logger.info("Purged %d old report(s): %s (predictions preserved)", len(purged), purged)
    except Exception as e:
        logger.warning("Report purge failed: %s", e)

    return state


# ═══════════════════════════════════════════════════════════════════
# CONDITIONAL EDGE FUNCTIONS (used by LangGraph StateGraph)
# ═══════════════════════════════════════════════════════════════════

def should_refetch(state: PipelineState) -> str:
    """
    Conditional edge after Reflect node.
    Returns "fetch" if data is insufficient and retries remain,
    otherwise "analyze".

    IMPORTANT: This function must be READ-ONLY. LangGraph discards
    mutations made in conditional edge functions. The retry counter
    is incremented inside reflect_node instead.
    """
    if (state.data_sufficiency == "insufficient"
        and state.fetch_retry_count <= state.max_fetch_retries):
        logger.info("Data insufficient — re-fetching (attempt %d/%d)...",
                    state.fetch_retry_count, state.max_fetch_retries)
        return "fetch"
    if state.data_sufficiency == "insufficient":
        logger.warning("Data still insufficient after %d retries — proceeding anyway",
                       state.max_fetch_retries)
    return "analyze"


def should_reanalyze(state: PipelineState) -> str:
    """
    Conditional edge after Validate node.
    Returns "analyze" if validation found critical flaws and retries remain,
    otherwise "score".

    IMPORTANT: This function must be READ-ONLY. LangGraph discards
    mutations made in conditional edge functions. The retry counter
    is incremented inside validate_node instead.
    """
    if (state.validation_status == "FAILED"
        and state.validation_retry_count <= state.max_validation_retries):
        logger.info("Validation FAILED — re-analyzing (attempt %d/%d)...",
                    state.validation_retry_count, state.max_validation_retries)
        return "analyze"
    if state.validation_status == "FAILED":
        logger.warning("Validation still FAILED after %d retries — scoring anyway",
                       state.max_validation_retries)
    return "score"


# ═══════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════

def _state_to_sector_dict(state: PipelineState) -> dict:
    """Reconstruct a sector dict from state (for backward-compatible functions)."""
    return {
        "name": state.sector_name,
        "description": state.sector_description,
        "tickers": state.sector_tickers,
        "keywords": state.sector_keywords,
        "supply_chain_map": state.sector_supply_chain_map,
    }


def _count_by_source(articles: list[Article]) -> dict[str, int]:
    """Count articles per source."""
    counts: dict[str, int] = {}
    for a in articles:
        counts[a.source] = counts.get(a.source, 0) + 1
    return counts


def _parse_predictions(analysis_text: str, tickers: list[str]) -> list[dict]:
    """
    Parse AI price predictions from the analysis text.

    Looks for the PRICE PREDICTIONS section and extracts per-ticker predictions
    with direction, expected move range, reasoning, and key risk.
    """
    predictions = []

    # Find the predictions section
    lines = analysis_text.split("\n")
    in_section = False
    section_lines = []
    for line in lines:
        if "PRICE PREDICTION" in line.upper() and "#" in line:
            in_section = True
            continue
        if in_section:
            # Stop at the next ## section header
            if line.strip().startswith("## ") and "PREDICTION" not in line.upper():
                break
            section_lines.append(line)

    if not section_lines:
        return predictions

    current = None
    for line in section_lines:
        stripped = line.strip()
        if not stripped:
            continue

        # Match ticker line — handles many LLM formatting variants:
        #   **NVDA**: BULLISH | Expected move: +3%
        #   *   **[LITE]**: **BEARISH** | Expected move: -3% to -6%
        #   - **NVDA** : BULLISH | Expected move: +5%
        ticker_match = re.match(
            r'^[-*\s]*\*{0,2}\[?([A-Z]{1,5})\]?\*{0,2}\s*:\s*\*{0,2}(BULLISH|BEARISH|NEUTRAL)\*{0,2}',
            stripped, re.IGNORECASE
        )
        if ticker_match:
            if current:
                predictions.append(current)
            ticker = ticker_match.group(1).upper()
            direction = ticker_match.group(2).upper()
            # Extract predicted change range
            change_match = re.search(r'[Ee]xpected\s+move:\s*(.+?)(?:\n|$)', stripped)
            if not change_match:
                change_match = re.search(r'[Pp]redicted\s+move:\s*(.+?)(?:\n|$)', stripped)
            change_range = change_match.group(1).strip() if change_match else ""
            current = {
                "ticker": ticker,
                "direction": direction,
                "predicted_change": change_range,
                "reasoning": "",
                "key_risk": "",
            }
        elif current:
            lower = stripped.lower()
            # Handle many LLM reasoning formats:
            #   - Reasoning: ...
            #   *   **Reasoning:** ...
            #   Reasoning: ...
            clean = re.sub(r'^[-*\s]*\*{0,2}', '', stripped)
            clean_lower = clean.lower()
            if clean_lower.startswith("reasoning:"):
                current["reasoning"] = re.sub(r'\*{1,2}', '', clean.split(":", 1)[-1]).strip()
            elif clean_lower.startswith("key risk:"):
                current["key_risk"] = re.sub(r'\*{1,2}', '', clean.split(":", 1)[-1]).strip()
            elif current["reasoning"] and not current["key_risk"] and not stripped.startswith(("-", "*")):
                # Continuation of reasoning line
                current["reasoning"] += " " + stripped

    if current:
        predictions.append(current)

    return predictions
