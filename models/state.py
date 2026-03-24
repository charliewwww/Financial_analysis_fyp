"""
Pipeline State — the structured data object that flows through every node.

This is the SINGLE SOURCE OF TRUTH for the entire analysis pipeline.
Every node reads from state, does its work, and writes results back.

DESIGN PRINCIPLES (for smooth LangGraph migration):
1. State is a TypedDict-style dataclass — maps directly to LangGraph's State
2. Every node is a pure function: (state) -> state
3. All intermediate data is captured — articles, links, summaries, LLM I/O
4. Node metadata (timing, token usage, decisions) is recorded per-node
5. The state is fully serializable to JSON for database storage

LANGGRAPH MIGRATION NOTE:
When migrating, this file becomes:
    from langgraph.graph import StateGraph
    from typing import TypedDict
    class PipelineState(TypedDict): ...
And the node functions in nodes.py become graph.add_node("fetch", fetch_node).
The conditional edges (Summarize→Fetch loop, Validate→Analyze loop) become
graph.add_conditional_edges().
"""

from __future__ import annotations

import time
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any


# ── Node Execution Record ──────────────────────────────────────────
# Every time a node runs, we capture EXACTLY what happened.

@dataclass
class NodeExecution:
    """
    Records everything about a single node's execution.

    This is the provenance trail — you can replay exactly what the AI
    saw, what it produced, and how long it took.
    """
    node_name: str                          # e.g. "fetch_news", "summarize", "analyze"
    started_at: str = ""                    # ISO timestamp
    finished_at: str = ""                   # ISO timestamp
    duration_seconds: float = 0.0           # Wall clock time
    status: str = "pending"                 # pending | running | completed | failed | skipped
    error: str | None = None                # Error message if failed

    # What the node consumed and produced
    input_keys: list[str] = field(default_factory=list)    # Which state keys it read
    output_keys: list[str] = field(default_factory=list)   # Which state keys it wrote

    # LLM-specific metadata (only for nodes that call the LLM)
    llm_model: str | None = None
    llm_prompt_tokens: int = 0
    llm_completion_tokens: int = 0
    llm_system_prompt: str | None = None    # The system prompt sent (truncated for storage)
    llm_user_prompt: str | None = None      # The full user prompt sent
    llm_raw_response: str | None = None     # The full LLM output

    # Decision metadata (for conditional edges)
    decision: str | None = None             # e.g. "sufficient", "insufficient", "flaws_found"
    decision_reason: str | None = None      # Why the decision was made

    def to_dict(self) -> dict:
        return asdict(self)


# ── Article (fully structured) ─────────────────────────────────────

@dataclass
class Article:
    """
    A single news article with full provenance.

    Every article the AI sees is stored here — the link, the raw text,
    the summarized version, and why we thought it was relevant.
    """
    title: str
    source: str                             # Feed name (e.g. "CNBC Top News", "Google News (NVDA)")
    link: str                               # Full URL to original article
    published: str                          # ISO date string
    raw_summary: str                        # The raw text/summary from the RSS feed
    condensed_summary: str = ""             # LLM-generated condensed summary (from Summarize node)
    relevance_tag: str = ""                 # Why it matched: "ticker:NVDA" or "keywords:ai+semiconductor"
    relevance_score: float = 0.0            # Numeric relevance (for future ranking)
    used_in_analysis: bool = True           # Whether the Reflect node kept it

    def to_dict(self) -> dict:
        return asdict(self)


# ── The Main Pipeline State ───────────────────────────────────────

@dataclass
class PipelineState:
    """
    The complete state that flows through the analysis pipeline.

    Maps 1:1 to LangGraph nodes from the user's diagram:
        Fetch Source → Summarize → Reflect on data → Analysis/Reasoning → Validation → Store

    EVERY piece of data the AI touches is here. Nothing is lost.
    """

    # ── Identity ──────────────────────────────────────────────────
    sector_id: str = ""
    sector_name: str = ""
    sector_description: str = ""
    sector_tickers: list[str] = field(default_factory=list)
    sector_keywords: list[str] = field(default_factory=list)
    sector_supply_chain_map: dict = field(default_factory=dict)
    run_id: str = ""                        # Unique identifier for this pipeline run
    created_at: str = ""                    # ISO timestamp when pipeline started

    # ── Node 1: Fetch Source ──────────────────────────────────────
    # Raw data pulled from external sources
    articles: list[Article] = field(default_factory=list)       # News articles (with links!)
    prices: list[dict] = field(default_factory=list)            # Yahoo Finance snapshots
    technicals: list[dict] = field(default_factory=list)        # RSI, MACD, Bollinger, etc.
    filings: list[dict] = field(default_factory=list)           # SEC EDGAR filings
    macro_data: dict = field(default_factory=dict)              # FRED macroeconomic indicators
    fetch_metadata: dict = field(default_factory=dict)          # Feed success/failure counts

    # ── Node 2: Summarize ─────────────────────────────────────────
    # LLM condenses raw articles into key points
    news_summary: str = ""                  # Condensed summary of all articles
    summary_bullet_points: list[str] = field(default_factory=list)  # Key takeaways

    # ── Node 3: Reflect on Data ───────────────────────────────────
    # LLM evaluates: do we have ENOUGH data to analyze?
    data_sufficiency: str = "unknown"       # sufficient | insufficient | marginal
    sufficiency_reasoning: str = ""         # Why the LLM thinks data is sufficient/not
    data_gaps: list[str] = field(default_factory=list)          # What's missing
    fetch_retry_count: int = 0              # How many times we looped back to Fetch
    max_fetch_retries: int = 1              # Max loops before proceeding anyway

    # ── RAG Context ───────────────────────────────────────────────
    # Historical context retrieved from ChromaDB vector store
    rag_context: str = ""                   # Formatted text injected into analysis prompt
    rag_metadata: dict = field(default_factory=dict)  # Query stats (results count, timing)

    # ── Node 4: Analysis / Reasoning ──────────────────────────────
    # The main LLM analysis output
    analysis_text: str = ""                 # Full Markdown analysis report
    analysis_prompt_used: str = ""          # The exact prompt sent (for debugging)
    anomaly_alerts: list[dict] = field(default_factory=list)  # Auto-detected anomalies
    ai_predictions: list[dict] = field(default_factory=list)  # AI price predictions per ticker

    # ── Node 5: Validation ────────────────────────────────────────
    # LLM fact-checks the analysis against real data
    validation_text: str = ""               # Validation report
    validation_status: str = ""             # PASSED | PASSED WITH WARNINGS | FAILED
    validation_issues: list[str] = field(default_factory=list)  # List of discrepancies
    validation_retry_count: int = 0         # How many times analysis was re-run
    max_validation_retries: int = 1         # Max loops before accepting

    # ── Node 6: Scoring ───────────────────────────────────────────
    confidence_score: float = 0.0           # Objective 1-10 score
    confidence_breakdown: dict = field(default_factory=dict)  # Per-dimension breakdown

    # ── Langfuse Observability ─────────────────────────────────────
    langfuse_trace_id: str = ""             # Groups all nodes under one Langfuse trace per sector

    # ── Pipeline Metadata ─────────────────────────────────────────
    node_executions: list[NodeExecution] = field(default_factory=list)  # Full trace
    total_duration_seconds: float = 0.0
    total_llm_prompt_tokens: int = 0
    total_llm_completion_tokens: int = 0
    pipeline_status: str = "pending"        # pending | running | completed | failed

    # ── Database ──────────────────────────────────────────────────
    report_id: int | None = None            # Populated after DB save

    # ── Serialization ─────────────────────────────────────────────
    def to_dict(self) -> dict:
        """Convert entire state to a JSON-serializable dict."""
        d = {}
        for k, v in self.__dict__.items():
            if isinstance(v, list) and v and hasattr(v[0], 'to_dict'):
                d[k] = [item.to_dict() if hasattr(item, 'to_dict') else item for item in v]
            elif hasattr(v, 'to_dict'):
                d[k] = v.to_dict()
            else:
                d[k] = v
        return d

    def to_json(self) -> str:
        """Serialize full state to JSON string."""
        return json.dumps(self.to_dict(), default=str, indent=2)

    @classmethod
    def from_sector(cls, sector_id: str, sector: dict) -> "PipelineState":
        """Create a fresh state from a sector config dict."""
        import uuid
        return cls(
            sector_id=sector_id,
            sector_name=sector["name"],
            sector_description=sector.get("description", ""),
            sector_tickers=list(sector.get("tickers", [])),
            sector_keywords=list(sector.get("keywords", [])),
            sector_supply_chain_map=dict(sector.get("supply_chain_map", {})),
            run_id=str(uuid.uuid4())[:8],
            created_at=datetime.now(timezone.utc).isoformat(),
            pipeline_status="pending",
        )


# ── Helper: timed node execution context manager ──────────────────

class NodeRunner:
    """
    Context manager that creates a NodeExecution record and times it.

    Usage:
        with NodeRunner(state, "fetch_news") as node:
            # do work...
            node.decision = "sufficient"

    When the block exits, the NodeExecution is appended to state.node_executions
    with timing and status automatically filled in.
    """

    def __init__(self, state: PipelineState, node_name: str):
        self.state = state
        self.node = NodeExecution(node_name=node_name)
        self._start_time = 0.0

    def __enter__(self) -> NodeExecution:
        self._start_time = time.time()
        self.node.started_at = datetime.now(timezone.utc).isoformat()
        self.node.status = "running"
        return self.node

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.node.duration_seconds = round(time.time() - self._start_time, 2)
        self.node.finished_at = datetime.now(timezone.utc).isoformat()

        if exc_type:
            self.node.status = "failed"
            self.node.error = str(exc_val)
        else:
            self.node.status = "completed"

        self.state.node_executions.append(self.node)

        # Accumulate LLM token totals
        self.state.total_llm_prompt_tokens += self.node.llm_prompt_tokens
        self.state.total_llm_completion_tokens += self.node.llm_completion_tokens

        return False  # Don't suppress exceptions
