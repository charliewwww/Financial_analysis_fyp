"""
Weekly Analysis Workflow — LangGraph StateGraph orchestrator.

Pipeline graph (with conditional loops):

    START → Fetch → Summarize → Reflect ──┐
                                          │
              ┌───── (insufficient) ──────┘
              ↓          ↓ (sufficient)
           [Fetch]    Analyze → Validate ──┐
                                           │
                  ┌──── (FAILED) ──────────┘
                  ↓        ↓ (PASSED)
              [Analyze]   Score → Save → END

Every node reads/writes to a shared PipelineState dataclass.
The StateGraph handles routing; node functions stay pure transforms.

Progress callbacks:
    An optional progress_fn(event_type, message) can be passed to
    run_weekly_analysis() and run_sector_analysis(). It is called at
    each pipeline milestone for live UI updates:
        ("step", "🔍 Checking LLM connection...")
        ("sector_start", "AI & Semiconductors")
        ("node", "📡 Fetching data...")
        ("sector_done", "AI & Semiconductors")
        ("error", "something broke")
"""

import os
import signal
import time
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from typing import Callable
from langgraph.graph import StateGraph, START, END
from config.sectors import SECTORS
from config.settings import LANGFUSE_ENABLED, LLM_PROVIDER
from agents.llm_client import (
    request_cancellation as _request_cancel,
    reset_cancellation as _reset_cancel,
    PipelineCancelled,
)
from models.state import PipelineState, Article, NodeExecution
from workflows.nodes import (
    fetch_node,
    summarize_node,
    reflect_node,
    analyze_node,
    validate_node,
    score_node,
    save_node,
    should_refetch,
    should_reanalyze,
)
from vectordb.chroma_store import warm_up as _chroma_warm_up
from agents.llm_client import check_llm_health, LLMHealthCheckError
from database.reports_db import get_unchecked_predictions, update_prediction_actual
from data_sources.yahoo_finance import get_stock_snapshot


# ═══════════════════════════════════════════════════════════════════
# PROGRESS CALLBACK — thread-local so concurrent sessions don't clash
# ═══════════════════════════════════════════════════════════════════

logger = logging.getLogger(__name__)

_thread_local = threading.local()

# Human-friendly labels for each graph node
_NODE_LABELS = {
    "fetch":     "📡 Fetching data (news, prices, SEC filings, macro)…",
    "summarize": "📝 Summarizing articles…",
    "reflect":   "🤔 Evaluating data sufficiency…",
    "analyze":   "🧠 Running deep analysis (RAG + LLM)…",
    "validate":  "✅ Validating analysis (numbers + reasoning)…",
    "score":     "📊 Computing confidence score…",
    "save":      "💾 Saving report…",
}


def _node_wrapper(fn, node_name: str):
    """Wrap a node function to report progress via the module-level callback."""
    label = _NODE_LABELS.get(node_name, node_name)

    def wrapped(state):
        fn_cb = getattr(_thread_local, "progress_fn", None)
        if fn_cb:
            fn_cb("node", label)
        return fn(state)

    # Keep the original function name for debugging
    wrapped.__name__ = fn.__name__
    wrapped.__qualname__ = fn.__qualname__
    return wrapped


# ═══════════════════════════════════════════════════════════════════
# GRAPH BUILDER — compiled once, reused per sector
# ═══════════════════════════════════════════════════════════════════

_compiled_graph = None


def _build_sector_graph():
    """
    Build the LangGraph analysis pipeline.

    Graph topology:
        START → fetch → summarize → reflect → [should_refetch]
        should_refetch: "fetch" → fetch (loop), "analyze" → analyze
        analyze → validate → [should_reanalyze]
        should_reanalyze: "analyze" → analyze (loop), "score" → score
        score → save → END

    Every node is wrapped with _node_wrapper so the module-level
    _progress_fn callback is called before each node executes.
    """
    graph = StateGraph(PipelineState)

    # ── Register nodes with progress wrappers ─────────────────────
    graph.add_node("fetch",     _node_wrapper(fetch_node, "fetch"))
    graph.add_node("summarize", _node_wrapper(summarize_node, "summarize"))
    graph.add_node("reflect",   _node_wrapper(reflect_node, "reflect"))
    graph.add_node("analyze",   _node_wrapper(analyze_node, "analyze"))
    graph.add_node("validate",  _node_wrapper(validate_node, "validate"))
    graph.add_node("score",     _node_wrapper(score_node, "score"))
    graph.add_node("save",      _node_wrapper(save_node, "save"))

    # ── Linear edges ──────────────────────────────────────────────
    graph.add_edge(START, "fetch")
    graph.add_edge("fetch", "summarize")
    graph.add_edge("summarize", "reflect")

    # ── Conditional: insufficient data → re-fetch, else analyze ───
    graph.add_conditional_edges(
        "reflect",
        should_refetch,
        {"fetch": "fetch", "analyze": "analyze"},
    )

    # ── Linear: analyze → validate ────────────────────────────────
    graph.add_edge("analyze", "validate")

    # ── Conditional: validation failed → re-analyze, else score ───
    graph.add_conditional_edges(
        "validate",
        should_reanalyze,
        {"analyze": "analyze", "score": "score"},
    )

    # ── Linear: score → save → END ────────────────────────────────
    graph.add_edge("score", "save")
    graph.add_edge("save", END)

    return graph.compile()


def _get_compiled_graph():
    """Lazy-compile the graph (cached for the process lifetime)."""
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = _build_sector_graph()
    return _compiled_graph


# ═══════════════════════════════════════════════════════════════════
# PUBLIC API — called by app.py for granular progress
# ═══════════════════════════════════════════════════════════════════

def run_sector_analysis(
    sector_id: str,
    sector: dict,
    progress_fn: Callable | None = None,
) -> dict:
    """
    Run the full LangGraph pipeline for ONE sector.

    Args:
        sector_id: Key in SECTORS dict
        sector: The sector config dict
        progress_fn: Optional callback(event_type, message) for live UI updates

    Returns:
        Result dict ready for the Streamlit UI.
    """
    logger.info("%s", "─" * 50)
    logger.info("Analyzing: %s", sector['name'])
    logger.info("%s", "─" * 50)

    try:
        state = _run_sector_graph(sector_id, sector, progress_fn=progress_fn)
        result = _state_to_result(state)

        # Log node timing
        logger.info("%s — Report #%s saved", state.sector_name, state.report_id)
        for node_exec in state.node_executions:
            logger.info("  ⏱  %-26s %6.1fs  [%s]",
                        node_exec.node_name, node_exec.duration_seconds, node_exec.status)
        logger.info("  %s", "─" * 46)
        logger.info("  ⏱  %-26s %6.1fs", "SECTOR TOTAL", state.total_duration_seconds)
        if state.total_llm_prompt_tokens > 0:
            logger.info("  Tokens: %d in → %d out",
                        state.total_llm_prompt_tokens, state.total_llm_completion_tokens)

        return result

    except Exception as e:
        logger.error("%s failed: %s", sector['name'], e)
        return {
            "sector_id": sector_id,
            "sector_name": sector["name"],
            "analysis": f"Analysis failed: {e}",
            "validation": "",
            "prices": [],
            "report_id": None,
            "error": str(e),
            "timing": None,
        }


# ── Main Pipeline (still usable for CLI / testing) ────────────────
def run_weekly_analysis(
    sector_ids: list[str] | None = None,
    progress_fn: Callable | None = None,
) -> list[dict]:
    """
    Run the full weekly analysis pipeline for all sectors.

    Args:
        sector_ids: Which sectors to analyze (default: all)
        progress_fn: Optional callback(event_type, message) for live UI

    Returns list of result dicts (one per sector) for the Streamlit UI.
    """
    if sector_ids is None:
        sector_ids = list(SECTORS.keys())

    results = []
    pipeline_start = time.time()

    # Reset cancellation from any previous run, then install Ctrl+C handler
    _reset_cancel()
    _prev_handler = signal.getsignal(signal.SIGINT)

    def _on_sigint(sig, frame):
        logger.warning("Ctrl+C received — requesting graceful shutdown…")
        _request_cancel()

    # Only install on main thread (signal module requirement)
    try:
        signal.signal(signal.SIGINT, _on_sigint)
    except ValueError:
        pass  # not main thread (e.g. Streamlit) — that's fine

    logger.info("%s", "=" * 60)
    logger.info("WEEKLY ANALYSIS — %s", datetime.now().strftime('%Y-%m-%d %H:%M'))
    logger.info("Sectors: %d", len(sector_ids))
    logger.info("%s", "=" * 60)

    # ── Pre-flight check: can we reach the LLM? ──────────────────
    if progress_fn:
        progress_fn("step", "🔍 Checking LLM connection…")

    try:
        check_llm_health()
        if progress_fn:
            progress_fn("step", "✅ LLM connected")
    except LLMHealthCheckError as e:
        logger.error("LLM HEALTH CHECK FAILED: %s", e)
        if progress_fn:
            progress_fn("error", f"❌ LLM health check failed: {e}")
        return [{
            "sector_id": sid,
            "sector_name": SECTORS.get(sid, {}).get("name", sid),
            "analysis": f"Pipeline aborted: {e}",
            "validation": "",
            "prices": [],
            "report_id": None,
            "error": str(e),
            "timing": None,
        } for sid in sector_ids]

    # ── Filter valid sectors ─────────────────────────────────────
    valid_sectors = []
    for sid in sector_ids:
        sector = SECTORS.get(sid)
        if not sector:
            logger.warning("Unknown sector: %s, skipping", sid)
            continue
        valid_sectors.append((sid, sector))

    total = len(valid_sectors)

    # ── Pre-warm ChromaDB before threading to avoid ONNX race condition ──
    # On first run (especially on cloud), ChromaDB downloads the ONNX embedding
    # model. If multiple threads race to do this simultaneously the protobuf
    # file gets corrupted. Warm up once here in the main thread first.
    _chroma_warm_up()

    # ── Cloud provider → run sectors in parallel; local → sequential ──
    # Local LLM (Ollama) uses your GPU — concurrent requests would OOM
    # or serialize at the GPU anyway.  Cloud APIs handle concurrency fine.
    use_parallel = LLM_PROVIDER != "ollama" and total > 1

    if use_parallel:
        logger.info("Cloud LLM detected (%s) — running %d sectors in parallel",
                     LLM_PROVIDER, total)
        if progress_fn:
            progress_fn("step", f"🚀 Running {total} sectors in parallel (cloud LLM)")

        futures = {}
        with ThreadPoolExecutor(max_workers=total) as pool:
            for i, (sid, sector) in enumerate(valid_sectors, 1):
                if progress_fn:
                    progress_fn("sector_start", f"[{i}/{total}] {sector['name']}")
                fut = pool.submit(run_sector_analysis, sid, sector, progress_fn=progress_fn)
                futures[fut] = sector

            for fut in as_completed(futures):
                sector = futures[fut]
                try:
                    result = fut.result()
                except PipelineCancelled:
                    logger.info("Sector %s cancelled", sector['name'])
                    if progress_fn:
                        progress_fn("sector_done", f"⚠️ {sector['name']}: cancelled")
                    continue
                results.append(result)
                if progress_fn:
                    if result.get("error"):
                        progress_fn("sector_done", f"❌ {sector['name']}: {result['error']}")
                    else:
                        conf = result.get("confidence", 0)
                        progress_fn("sector_done", f"✅ {sector['name']} — {conf}/10")
    else:
        mode = "local LLM (GPU)" if LLM_PROVIDER == "ollama" else "single sector"
        logger.info("Sequential mode (%s) — running %d sector(s) one by one", mode, total)
        for i, (sid, sector) in enumerate(valid_sectors, 1):
            if progress_fn:
                progress_fn("sector_start", f"[{i}/{total}] {sector['name']}")

            result = run_sector_analysis(sid, sector, progress_fn=progress_fn)
            results.append(result)

            if progress_fn:
                if result.get("error"):
                    progress_fn("sector_done", f"❌ {sector['name']}: {result['error']}")
                else:
                    conf = result.get("confidence", 0)
                    progress_fn("sector_done", f"✅ {sector['name']} — {conf}/10")

    # After all analyses, check old predictions
    check_old_predictions()

    total_time = time.time() - pipeline_start
    logger.info("%s", "=" * 60)
    logger.info("Weekly analysis complete — %d reports in %.0fs", len(results), total_time)
    logger.info("%s", "=" * 60)

    # Restore original Ctrl+C handler
    try:
        signal.signal(signal.SIGINT, _prev_handler)
    except ValueError:
        pass

    return results


def _run_sector_graph(
    sector_id: str,
    sector: dict,
    progress_fn: Callable | None = None,
) -> PipelineState:
    """
    Execute the LangGraph pipeline for a single sector.

    Sets the thread-local _thread_local.progress_fn so node wrappers can
    report per-node progress to the UI callback.
    """
    start = time.time()

    # ── Initialize state ──────────────────────────────────────────
    state = PipelineState.from_sector(sector_id, sector)
    state.pipeline_status = "running"

    # ── Create a single Langfuse trace for the entire sector run ──
    # All LLM calls and RAG spans will be grouped under this trace,
    # giving you ONE row in Langfuse per sector instead of many.
    lf_client = None
    lf_root_span = None
    if LANGFUSE_ENABLED:
        try:
            from langfuse import Langfuse
            lf_client = Langfuse()
            trace_id = lf_client.create_trace_id(
                seed=f"{sector_id}-{state.created_at}"
            )
            state.langfuse_trace_id = trace_id

            # Open a root span that covers the entire pipeline run.
            # This also sets the OTel context so update_current_trace works.
            lf_root_span = lf_client.start_as_current_span(
                trace_context={"trace_id": trace_id},
                name=f"pipeline — {sector['name']}",
                input={"sector_id": sector_id, "tickers": sector.get("tickers", [])},
                metadata={"sector_id": sector_id},
                end_on_exit=False,  # we'll end it manually after state update
            )
            lf_root_span.__enter__()

            # Set trace-level metadata (name, session, user, tags) so the
            # trace shows up with useful labels in the Langfuse dashboard.
            lf_client.update_current_trace(
                name=f"weekly_analysis — {sector['name']}",
                session_id=f"run-{state.created_at}",
                user_id="supply-chain-alpha",
                tags=["weekly", sector_id],
                metadata={
                    "sector_name": sector["name"],
                    "tickers": sector.get("tickers", []),
                },
            )
            logger.info("Langfuse trace created: %s", trace_id)
        except Exception as e:
            logger.warning("Failed to create Langfuse trace: %s", e)
            lf_root_span = None

    # ── Run the graph with progress callback active ───────────────
    graph = _get_compiled_graph()
    _thread_local.progress_fn = progress_fn  # Node wrappers will pick this up

    try:
        # LangGraph copies the state internally, so the original `state`
        # object is NOT mutated. Reconstruct from the result dict.
        result_dict = graph.invoke(state)
    finally:
        _thread_local.progress_fn = None  # Always clean up

    # Update state from result dict (LangGraph returns all fields)
    # LangGraph may serialize dataclass objects to plain dicts, so
    # we reconstruct Article / NodeExecution objects where needed.
    for key, value in result_dict.items():
        if not hasattr(state, key):
            continue
        if key == "articles" and isinstance(value, list):
            state.articles = [
                Article(**item) if isinstance(item, dict) else item
                for item in value
            ]
        elif key == "node_executions" and isinstance(value, list):
            state.node_executions = [
                NodeExecution(**item) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            setattr(state, key, value)

    # ── Finalize ──────────────────────────────────────────────────
    state.total_duration_seconds = round(time.time() - start, 1)
    state.pipeline_status = "completed"

    # ── Update Langfuse trace with final results ──────────────────
    if LANGFUSE_ENABLED and state.langfuse_trace_id:
        try:
            if lf_client is None:
                from langfuse import Langfuse
                lf_client = Langfuse()

            # Update trace output with pipeline results
            lf_client.update_current_trace(
                output={
                    "confidence_score": state.confidence_score,
                    "validation_status": state.validation_status,
                    "data_sufficiency": state.data_sufficiency,
                    "news_count": len(state.articles),
                    "predictions_count": len(state.ai_predictions),
                    "total_duration_seconds": state.total_duration_seconds,
                    "report_id": state.report_id,
                },
            )

            # Also log a categorical score for pipeline completion
            lf_client.create_score(
                trace_id=state.langfuse_trace_id,
                name="pipeline_completed",
                value="completed",
                data_type="CATEGORICAL",
                comment=(
                    f"confidence={state.confidence_score}, "
                    f"validation={state.validation_status}, "
                    f"data_sufficiency={state.data_sufficiency}, "
                    f"news={len(state.articles)}, "
                    f"predictions={len(state.ai_predictions)}, "
                    f"duration={state.total_duration_seconds}s, "
                    f"report_id={state.report_id}"
                ),
                metadata={
                    "confidence_score": state.confidence_score,
                    "validation_status": state.validation_status,
                    "data_sufficiency": state.data_sufficiency,
                    "news_count": len(state.articles),
                    "predictions_count": len(state.ai_predictions),
                    "total_duration_seconds": state.total_duration_seconds,
                    "report_id": state.report_id,
                },
            )

            # Close the root span that wraps the entire pipeline
            if lf_root_span is not None:
                try:
                    lf_root_span.__exit__(None, None, None)
                except Exception:
                    pass

            lf_client.flush()
        except Exception as e:
            logger.warning("Failed to finalize Langfuse trace: %s", e)

    # ── Push evaluation scores to Langfuse ────────────────────────
    # Scores are computed regardless of Langfuse status (for local use)
    # and pushed to Langfuse when enabled. This enables quality tracking
    # over time and regression detection.
    try:
        from evals.scoring import push_scores_to_langfuse
        eval_scores = push_scores_to_langfuse(state)
        logger.info("Eval scores: overall=%.2f", eval_scores.get("overall", 0))
    except Exception as e:
        logger.debug("Eval scoring skipped: %s", e)

    return state


def _state_to_result(state: PipelineState) -> dict:
    """Convert PipelineState to the result dict the UI expects."""
    timing_steps = [
        {"name": n.node_name, "seconds": n.duration_seconds}
        for n in state.node_executions
    ]
    return {
        "sector_id": state.sector_id,
        "sector_name": state.sector_name,
        "analysis": state.analysis_text,
        "validation": state.validation_text,
        "prices": state.prices,
        "report_id": state.report_id,
        "news_count": len(state.articles),
        "confidence": state.confidence_score,
        "timing": {
            "total_seconds": state.total_duration_seconds,
            "steps": timing_steps,
        },
        # New fields the UI can use
        "data_sufficiency": state.data_sufficiency,
        "news_summary": state.news_summary,
        "validation_status": state.validation_status,
    }


def check_old_predictions():
    """Check predictions from previous reports against current actual prices."""
    unchecked = get_unchecked_predictions()
    if not unchecked:
        return

    now = datetime.now(timezone.utc)
    old_enough = []
    for pred in unchecked:
        try:
            report_dt = datetime.fromisoformat(pred["report_date"])
            # Ensure timezone-aware (old records may lack tz info)
            if report_dt.tzinfo is None:
                report_dt = report_dt.replace(tzinfo=timezone.utc)
            if (now - report_dt).days >= 7:
                old_enough.append(pred)
        except (ValueError, TypeError):
            continue

    if not old_enough:
        return

    logger.info("Checking %d past predictions...", len(old_enough))

    tickers_to_check = set(p["ticker"] for p in old_enough)
    current_prices = {}

    # Fetch current prices concurrently instead of one-by-one
    from concurrent.futures import ThreadPoolExecutor, as_completed
    with ThreadPoolExecutor(max_workers=min(len(tickers_to_check), 6)) as pool:
        future_to_ticker = {
            pool.submit(get_stock_snapshot, t): t for t in tickers_to_check
        }
        for future in as_completed(future_to_ticker):
            ticker = future_to_ticker[future]
            try:
                snapshot = future.result(timeout=30)
                if not snapshot.get("error") and snapshot.get("price"):
                    current_prices[ticker] = snapshot["price"]
            except Exception as e:
                logger.warning("Failed to fetch %s for prediction check: %s", ticker, e)

    updated = 0
    for pred in old_enough:
        if pred["ticker"] in current_prices:
            update_prediction_actual(pred["id"], current_prices[pred["ticker"]])
            updated += 1

    logger.info("Updated %d predictions with actual prices", updated)
