"""Extract a backend-shaped signal card from a legacy PipelineState.

Pure functions only — no DB, no I/O, no async.  This is the typed contract
between the legacy LangGraph pipeline (workflows/weekly_analysis.py) and the
new FastAPI backend, so the pipeline can evolve without breaking the bridge.

Any future agent — quant, momentum, options-flow, etc. — can produce a
`SignalCardDraft` and call `runner._persist_card` to land in the same DB.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Literal
from urllib.parse import urlparse

from pydantic import BaseModel, Field

Signal = Literal["BULLISH", "BEARISH", "NEUTRAL"]


class SignalCardDraft(BaseModel):
    """Typed contract handed to `runner._persist_card`.

    Mirrors `signal_cards` table columns.  Persistable via
    `create_signal_card(**draft.model_dump(exclude={"created_at", "status"}))`.
    """

    ticker: str
    run_id: str
    user_email: str | None = None
    signal: Signal
    conviction: int = Field(ge=1, le=5)
    one_line: str
    key_catalyst: str = ""
    key_risk: str = ""
    confidence: float = 0.0
    signal_type: str = "FUNDAMENTAL_SHIFT"
    validation_score: str = ""
    supply_chain_impact: list[dict[str, Any]] = []
    sources: list[dict[str, Any]] = []
    numerical_claims: list[dict[str, Any]] = []
    sector_context: dict[str, Any] = {}
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: str = "active"


# ── Extractors ─────────────────────────────────────────────────────

_SIGNAL_RE = re.compile(r"\b(BULLISH|BEARISH|NEUTRAL)\b", re.IGNORECASE)
_CONVICTION_RE = re.compile(r"conviction\s*[:=]?\s*(\d)\s*/?\s*5?", re.IGNORECASE)


def extract_signal(text: str) -> Signal:
    """Find BULLISH / BEARISH / NEUTRAL near a Signal/Thesis/Verdict heading.

    Falls back to the first occurrence anywhere in the text, then NEUTRAL.
    """
    for heading in ("## Signal", "## Thesis", "## Verdict"):
        idx = text.find(heading)
        if idx >= 0:
            m = _SIGNAL_RE.search(text[idx:idx + 500])
            if m:
                return m.group(1).upper()  # type: ignore[return-value]
    m = _SIGNAL_RE.search(text)
    return m.group(1).upper() if m else "NEUTRAL"  # type: ignore[return-value]


def extract_conviction(text: str) -> int:
    """Pull a 1–5 conviction score; default 3 if missing."""
    m = _CONVICTION_RE.search(text)
    if m:
        return max(1, min(5, int(m.group(1))))
    return 3


def extract_one_line(text: str) -> str:
    """Single-line thesis (≤280 chars) — first non-blank line under
    ## Thesis / ## Signal / ## Summary, else first non-heading line."""
    for marker in ("## Thesis", "## Signal", "## Summary"):
        idx = text.find(marker)
        if idx >= 0:
            after = text[idx + len(marker):].strip()
            for line in after.splitlines():
                line = line.strip("# ").strip()
                if line and not line.startswith("#"):
                    return line[:280]
    return next(
        (ln.strip() for ln in text.splitlines() if ln.strip() and not ln.strip().startswith("#")),
        "",
    )[:280]


def _extract_section(text: str, markers: tuple[str, ...]) -> str:
    """First section body matching any marker, capped at 280 chars."""
    for marker in markers:
        idx = text.find(marker)
        if idx >= 0:
            block = text[idx + len(marker):].split("\n##")[0].strip()
            return block[:280]
    return ""


def extract_catalyst(text: str) -> str:
    return _extract_section(text, ("## Key Catalyst", "## Catalyst", "**Catalyst**"))


def extract_risk(text: str) -> str:
    return _extract_section(text, ("## Key Risk", "## Risk Assessment", "## Risk", "**Risk**"))


def build_sources(articles: list[Any]) -> list[dict[str, Any]]:
    """Reshape Article dataclasses into the JSONB-friendly source list."""
    out: list[dict[str, Any]] = []
    for a in articles[:10]:
        url = getattr(a, "link", "") or getattr(a, "url", "") or ""
        try:
            domain = urlparse(url).netloc
        except Exception:
            domain = ""
        out.append({
            "url": url,
            "title": getattr(a, "title", "") or "",
            "domain": domain,
        })
    return out


def build_numerical_claims(state: Any) -> list[dict[str, Any]]:
    """Reshape validate-node issues into the canonical claim shape."""
    issues = getattr(state, "validation_issues", None) or []
    out: list[dict[str, Any]] = []
    for issue in issues[:20]:
        if isinstance(issue, dict):
            out.append({
                "claim": issue.get("claim", ""),
                "verified": issue.get("verified", False),
                "source": issue.get("source", ""),
            })
    return out


def from_pipeline_state(
    *,
    state: Any,
    run_id: str,
    ticker: str,
    user_email: str | None,
) -> SignalCardDraft:
    """Build a `SignalCardDraft` from a finished `PipelineState`.

    Pure — safe to call from a worker thread.
    """
    text = getattr(state, "analysis_text", "") or ""
    return SignalCardDraft(
        ticker=ticker,
        run_id=run_id,
        user_email=user_email,
        signal=extract_signal(text),
        conviction=extract_conviction(text),
        one_line=extract_one_line(text),
        key_catalyst=extract_catalyst(text),
        key_risk=extract_risk(text),
        confidence=float(getattr(state, "confidence_score", 0) or 0.0) / 10.0,
        validation_score=str(getattr(state, "validation_status", "")),
        sources=build_sources(getattr(state, "articles", []) or []),
        numerical_claims=build_numerical_claims(state),
        sector_context={
            "sector_id": getattr(state, "sector_id", ""),
            "sector_name": getattr(state, "sector_name", ""),
        },
    )
