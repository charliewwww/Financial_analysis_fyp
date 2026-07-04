"""
Pipeline trigger, run tracking, and streaming schemas.

RunRequest      POST /api/pipeline/runs          — start a pipeline run
PipelineRunSchema  GET /api/pipeline/runs/{run_id} — full run record
RunSummary      GET  /api/pipeline/runs           — list view item
SSEEvent        streamed over GET /api/pipeline/runs/{run_id}/stream
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.analysis import NodeExecutionSchema


class _LLMCredentialsMixin(BaseModel):
    """Optional browser-supplied LLM credentials, scoped to a single run.

    These are sent per-request from the user's browser, used only for that
    run, and are NEVER persisted server-side or written to logs. When absent,
    the server's own env credentials are used instead. Supplying an api_key
    also lifts the curated model allow-list (it is the user's own provider).
    """

    api_key: str | None = Field(
        default=None,
        description="User-supplied LLM API key. Used for this run only; never stored or logged.",
    )
    base_url: str | None = Field(
        default=None,
        description="Optional OpenAI-compatible base URL for the user's provider.",
    )


# ── Trigger ────────────────────────────────────────────────────────

class RunRequest(_LLMCredentialsMixin):
    """
    Request body for POST /api/pipeline/runs.

    Phase 1: ticker-based.  sector_id is the context sector the ticker belongs to
    (used for the hybrid context model: sector news as input, per-ticker output).
    """

    ticker: str = Field(..., description="Target ticker, e.g. 'NVDA' or '0700.HK'.")
    sector_id: str = Field(..., description="Sector the ticker belongs to, e.g. 'semiconductors'.")
    agent_id: int | None = Field(
        default=None,
        description="Agent to run. None = system default agent.",
    )
    max_fetch_retries: int = Field(default=1, ge=0, le=3)
    max_validation_retries: int = Field(default=1, ge=0, le=3)
    dry_run: bool = Field(
        default=False,
        description=(
            "When True, no real LangGraph pipeline is executed. "
            "Instead, 5 simulated SSE events are streamed over ~10 seconds "
            "to verify the frontend reacts correctly end-to-end. "
            "Intended for local E2E testing only."
        ),
    )
    model: str | None = Field(
        default=None,
        description="Optional per-run reasoning model override.",
    )


class RunFanoutRequest(_LLMCredentialsMixin):
    """
    Request body for POST /api/pipeline/runs/fanout.

    Starts one pipeline run per selected agent. sector_id is optional because
    the Board of Analysts can infer it for known tickers from config/sectors.py.
    """

    ticker: str = Field(..., description="Target ticker, e.g. 'NVDA' or '0700.HK'.")
    sector_id: str | None = Field(
        default=None,
        description="Optional sector override. Omit to infer from the ticker catalog.",
    )
    agent_ids: list[int] | None = Field(
        default=None,
        min_length=1,
        max_length=16,
        description="Optional agent ids. Omit to run every registered analyst.",
    )
    model: str | None = Field(
        default=None,
        description="Optional per-run reasoning model override (must be in the curated allow-list).",
    )
    max_fetch_retries: int = Field(default=1, ge=0, le=3)
    max_validation_retries: int = Field(default=1, ge=0, le=3)
    dry_run: bool = Field(default=False)


class RunSectorFanoutRequest(_LLMCredentialsMixin):
    """Request body for POST /api/pipeline/runs/sector-fanout."""

    sector_id: str = Field(..., description="Sector to run, e.g. 'ai_semiconductors'.")
    tickers: list[str] | None = Field(
        default=None,
        min_length=1,
        max_length=25,
        description="Optional ticker subset. Omit to run every ticker in the sector.",
    )
    agent_ids: list[int] | None = Field(
        default=None,
        min_length=1,
        max_length=16,
        description="Optional agent ids. Omit to run every registered analyst.",
    )
    model: str | None = Field(
        default=None,
        description="Optional per-run reasoning model override (must be in the curated allow-list).",
    )
    max_fetch_retries: int = Field(default=1, ge=0, le=3)
    max_validation_retries: int = Field(default=1, ge=0, le=3)
    dry_run: bool = Field(default=False)


class RunSectorSynthesisRequest(_LLMCredentialsMixin):
    """Request body for POST /api/pipeline/runs/sector-synthesis.

    Produces ONE board-level sector synthesis run (macro → trend →
    second-order effects across constituents) rather than a per-ticker fanout.
    """

    sector_id: str = Field(..., description="Sector to synthesise, e.g. 'us_technology'.")
    model: str | None = Field(
        default=None,
        description="Optional per-run reasoning model override (must be in the curated allow-list).",
    )
    max_fetch_retries: int = Field(default=1, ge=0, le=3)
    max_validation_retries: int = Field(default=1, ge=0, le=3)


class RunSynthesisResponse(BaseModel):
    """Response body for POST /api/pipeline/runs/sector-synthesis."""

    run_id: str
    sector_id: str
    sector_label: str
    status: Literal["pending"] = "pending"


class RunFanoutItem(BaseModel):
    """One run launched as part of a Board of Analysts fanout."""

    run_id: str
    agent_id: int
    agent_name: str
    status: Literal["pending"] = "pending"


class RunFanoutResponse(BaseModel):
    """Response body for POST /api/pipeline/runs/fanout."""

    ticker: str
    sector_id: str
    dry_run: bool = False
    runs: list[RunFanoutItem]


# ── Full run record ────────────────────────────────────────────────

class PipelineRunSchema(BaseModel):
    """
    Full pipeline_runs row.  Returned by GET /api/pipeline/runs/{run_id}.

    While status == "running", current_node and node_executions update in real time
    via the SSE stream.  Once completed, signal_card_id is populated — the frontend
    can then fetch the signal card for full results.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    run_id: str
    ticker: str
    sector_id: str
    agent_id: int | None = None
    agent_name: str | None = None
    status: Literal["pending", "running", "completed", "failed"]
    current_node: str | None = None
    error: str | None = None
    created_at: str
    started_at: str | None = None
    finished_at: str | None = None
    signal_card_id: int | None = None
    node_executions: list[NodeExecutionSchema] = Field(default_factory=list)


# ── Status / List ──────────────────────────────────────────────────

class RunSummary(BaseModel):
    """
    Lightweight run record used in list responses and the pipeline status page.
    Full details via GET /api/pipeline/runs/{run_id}.
    """

    run_id: str
    ticker: str
    sector_id: str
    agent_id: int | None = None
    agent_name: str | None = None
    status: Literal["pending", "running", "completed", "failed"]
    created_at: str
    started_at: str | None = None
    finished_at: str | None = None
    current_node: str | None = None
    error: str | None = None
    signal_card_id: int | None = None


# ── SSE Streaming ──────────────────────────────────────────────────

class SSENodeUpdate(BaseModel):
    """Payload for node_started / node_completed SSE events."""

    node: NodeExecutionSchema
    progress_pct: float = Field(ge=0.0, le=100.0)


class SSEEvent(BaseModel):
    """
    Every frame sent over the SSE stream is serialised as one of these.

    Frontend discriminates on `event` to update the UI:
        node_started       → mark that node as in-progress in the timeline
        node_completed     → mark it done, advance progress bar
        pipeline_completed → fetch signal card from GET /api/signals/{signal_card_id}
        pipeline_failed    → display error.message from data
        heartbeat          → no-op; keeps the HTTP connection alive every 15 s
    """

    event: Literal[
        "node_started",
        "node_completed",
        "pipeline_completed",
        "pipeline_failed",
        "heartbeat",
    ]
    run_id: str
    data: dict[str, Any] = Field(default_factory=dict)
