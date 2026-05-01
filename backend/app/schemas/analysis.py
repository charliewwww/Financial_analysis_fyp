"""
Pydantic v2 schemas that mirror the internal dataclasses in models/state.py,
plus the new Phase 1 primary output type: SignalCardSchema.

Naming convention:
    Internal dataclass  →  API schema
    NodeExecution       →  NodeExecutionSchema
    Article             →  ArticleSchema
    PipelineState       →  PipelineStateSchema  (legacy sector analysis)
    —                   →  SignalCardSchema      (Phase 1+ primary output)
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


# ── Node Execution ─────────────────────────────────────────────────

class NodeExecutionSchema(BaseModel):
    """
    A single node's execution record.  Maps from NodeExecution in models/state.py.

    Raw LLM prompts and responses are intentionally excluded from the API
    response — they are large and contain internal system instructions.
    Use the /api/pipeline/runs/{run_id}/debug endpoint (future) for full traces.
    """

    model_config = ConfigDict(from_attributes=True)

    node_name: str
    started_at: str = ""
    finished_at: str = ""
    duration_seconds: float = 0.0
    status: Literal["pending", "running", "completed", "failed", "skipped"] = "pending"
    error: str | None = None
    input_keys: list[str] = Field(default_factory=list)
    output_keys: list[str] = Field(default_factory=list)
    llm_model: str | None = None
    llm_prompt_tokens: int = 0
    llm_completion_tokens: int = 0
    decision: str | None = None
    decision_reason: str | None = None


# ── Article ────────────────────────────────────────────────────────

class ArticleSchema(BaseModel):
    """A single news article. Maps from Article in models/state.py."""

    model_config = ConfigDict(from_attributes=True)

    title: str
    source: str
    link: str
    published: str
    raw_summary: str
    condensed_summary: str = ""
    relevance_tag: str = ""
    relevance_score: float = 0.0
    used_in_analysis: bool = True


# ── AI Prediction ──────────────────────────────────────────────────

class AIPredictionSchema(BaseModel):
    """
    Single-ticker price prediction produced by the analyze node.
    Stored in the predictions table and surfaced on the Predictions page.
    """

    ticker: str
    direction: str = ""            # "bullish" | "bearish" | "neutral"
    predicted_change_pct: str = "" # e.g. "+3% to +7%"
    reasoning: str = ""
    risk_level: str = ""           # "low" | "medium" | "high"


# ── Anomaly Alert ──────────────────────────────────────────────────

class AnomalyAlertSchema(BaseModel):
    """Auto-detected statistical anomaly from utils/anomaly_detection.py."""

    ticker: str = ""
    metric: str = ""
    value: Any = None
    threshold: Any = None
    message: str = ""


# ── Full Pipeline State ────────────────────────────────────────────

class PipelineStateSchema(BaseModel):
    """
    Complete snapshot of a pipeline run.

    Returned by:
        GET  /api/pipeline/runs/{run_id}

    This is the "source of truth" response that the frontend parses to
    render the analysis report, predictions, and node execution timeline.
    Raw article text and LLM prompts are intentionally excluded.
    """

    model_config = ConfigDict(from_attributes=True)

    # ── Identity ────────────────────────────────────────────────────
    run_id: str
    sector_id: str
    sector_name: str
    sector_tickers: list[str] = Field(default_factory=list)
    created_at: str = ""
    pipeline_status: Literal["pending", "running", "completed", "failed"] = "pending"

    # ── Timing & Token Usage ─────────────────────────────────────
    total_duration_seconds: float = 0.0
    total_llm_prompt_tokens: int = 0
    total_llm_completion_tokens: int = 0

    # ── Node Outputs ─────────────────────────────────────────────
    news_summary: str = ""
    data_sufficiency: Literal["sufficient", "insufficient", "marginal", "unknown"] = "unknown"
    analysis_text: str = ""
    validation_text: str = ""
    validation_status: str = ""
    confidence_score: float = 0.0
    confidence_breakdown: dict[str, Any] = Field(default_factory=dict)
    reasoning_scores: dict[str, Any] = Field(default_factory=dict)

    # ── Structured Data ───────────────────────────────────────────
    articles: list[ArticleSchema] = Field(default_factory=list)
    ai_predictions: list[AIPredictionSchema] = Field(default_factory=list)
    anomaly_alerts: list[AnomalyAlertSchema] = Field(default_factory=list)

    # ── Provenance ────────────────────────────────────────────────
    node_executions: list[NodeExecutionSchema] = Field(default_factory=list)

    # ── Database ─────────────────────────────────────────────────
    report_id: int | None = None


# ══════════════════════════════════════════════════════════════════
# PHASE 1 PRIMARY OUTPUT — SignalCardSchema
# Replaces the long essay. Every field is independently verifiable.
# Maps 1:1 to the signal_cards table and the roadmap target JSON structure.
# ══════════════════════════════════════════════════════════════════

class NumericalClaimSchema(BaseModel):
    """
    A single verifiable numerical claim extracted from the analysis.

    e.g. {"claim": "CoWoS capacity +40%", "verified": true, "source": "TSMC IR"}

    Every numerical claim the LLM makes must be represented here.
    Unverified claims are NOT hidden — they surface as verified=False.
    This is what makes the Validation Loop work: you cannot hallucinate
    a structured field the same way you can bury a lie in prose.
    """

    claim: str
    verified: bool = False
    source: str = ""


class SupplyChainImpactSchema(BaseModel):
    """One supply-chain ripple effect entry on a signal card."""

    ticker: str
    direction: Literal["▲", "▼", "◆"] = "◆"
    reason: str = ""


class SignalSourceSchema(BaseModel):
    """A cited source backing the signal."""

    url: str
    title: str = ""
    domain: str = ""   # e.g. "reuters.com" — derived from url by the pipeline


class SignalCardSchema(BaseModel):
    """
    Phase 1+ primary output type.

    This is what the Morning Brief, Board of Analysts, and Chat Desk all render.
    Returned by:
        GET  /api/signals/{id}
        GET  /api/signals?ticker=NVDA
        SSE  /api/pipeline/runs/{run_id}/stream  (inside SSEEvent.data on completion)

    Design principle: every field here is a testable assertion.
    The Validation Loop now operates on these fields — not on prose.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int | None = None
    ticker: str
    run_id: str | None = None
    agent_id: int | None = None

    # ── Core verdict ─────────────────────────────────────────────
    signal: Literal["BULLISH", "BEARISH", "NEUTRAL"]
    conviction: int = Field(ge=1, le=5)
    one_line: str                   # single-sentence verdict shown in Morning Brief
    key_catalyst: str = ""          # top bullish driver
    key_risk: str = ""              # top bearish risk
    confidence: float = Field(ge=0.0, le=1.0)

    # ── Signal classification (Phase 2 — field present from Phase 1) ─
    # FUNDAMENTAL_SHIFT | MEDIA_NARRATIVE | TECHNICAL_ONLY
    signal_type: str | None = None
    validation_score: str = ""      # "3/4 claims verified"

    # ── Structured evidence ───────────────────────────────────────
    numerical_claims: list[NumericalClaimSchema] = Field(default_factory=list)
    sources: list[SignalSourceSchema] = Field(default_factory=list)
    supply_chain_impact: list[SupplyChainImpactSchema] = Field(default_factory=list)

    # ── Metadata ──────────────────────────────────────────────────
    created_at: str = ""
    status: str = "active"
