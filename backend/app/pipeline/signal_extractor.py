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
    agent_id: int | None = None
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
    raw_pipeline_state: dict[str, Any] = {}
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: str = "active"


# ── Extractors ─────────────────────────────────────────────────────

_SIGNAL_RE = re.compile(r"\b(BULLISH|BEARISH|NEUTRAL)\b", re.IGNORECASE)
_CONVICTION_RE = re.compile(r"conviction\s*[:=]?\s*(\d)\s*/?\s*5?", re.IGNORECASE)
_METADATA_LINE_RE = re.compile(
    r"^(?:\*\*)?\s*(date|analyst|author|source|report|sector|role|objective)\b",
    re.IGNORECASE,
)

_LABEL_VALUE_RE = re.compile(
    r"^\s*(?:[-*]\s*)?(?:\*\*)?\s*(?P<label>[A-Za-z][A-Za-z\s/&-]{2,40}?)(?:\*\*)?\s*(?::|–|\s+-\s+)\s*(?P<body>.+)$"
)

_DIRECTION_MARKERS: dict[str, str] = {
    "▲": "▲",
    "up": "▲",
    "positive": "▲",
    "benefit": "▲",
    "benefits": "▲",
    "bullish": "▲",
    "▼": "▼",
    "down": "▼",
    "negative": "▼",
    "pressure": "▼",
    "pressured": "▼",
    "bearish": "▼",
    "◆": "◆",
    "mixed": "◆",
    "neutral": "◆",
    "unclear": "◆",
}


def normalize_validation_status(value: Any) -> str:
    """Return the pipeline validation status as a clean display string."""
    return str(value or "").strip()


def is_failed_validation_status(value: Any) -> bool:
    """True when a pipeline result failed validation and should not publish."""
    return "FAILED" in normalize_validation_status(value).upper()


def extract_signal(text: str) -> Signal:
    """Find BULLISH / BEARISH / NEUTRAL near a Signal/Thesis/Verdict heading.

    Falls back to the first occurrence anywhere in the text, then NEUTRAL.
    """
    labeled = _extract_labeled_value(text, ("signal", "verdict", "posture"))
    if labeled:
        m = _SIGNAL_RE.search(labeled)
        if m:
            return m.group(1).upper()  # type: ignore[return-value]

    for heading in ("## Signal Card", "## SIGNAL CARD", "## Signal", "## Thesis", "## Verdict"):
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


def conviction_was_stated(text: str) -> bool:
    """True when the analysis text explicitly states a conviction score.

    Lets the UI distinguish a real "3/5" from the silent default fallback,
    so we never present a fabricated conviction as if the model asserted it.
    """
    return _CONVICTION_RE.search(text or "") is not None


# ── Signal-type classification (rule-based, deterministic) ─────────
# Answers the product's headline question: "is this a real fundamental
# shift, just media narrative, or only a technical setup?"  No LLM call —
# fully transparent and auditable.

_FUNDAMENTAL_KEYWORDS = (
    "earnings", "revenue", "guidance", "margin", "eps", "profit",
    "contract", "order", "backlog", "acquisition", "merger", "acquire",
    "10-k", "10-q", "8-k", "sec filing", "annual report", "quarterly report",
    "product launch", "fda", "approval", "approved", "dividend", "buyback",
    "capex", "capacity", "supply agreement", "partnership", "deal signed",
    "regulatory", "antitrust", "lawsuit", "settlement", "bankruptcy",
    "shipment", "production", "balance sheet", "cash flow", "free cash flow",
    "fundamental", "valuation", "book value", "debt", "outlook raised",
)
_TECHNICAL_KEYWORDS = (
    "rsi", "macd", "moving average", "sma", "ema", "bollinger",
    "overbought", "oversold", "support level", "resistance level",
    "breakout", "breakdown", "momentum", "golden cross", "death cross",
    "trendline", "price action", "volume spike", "consolidation",
    "pullback", "uptrend", "downtrend", "chart pattern",
)
_MEDIA_KEYWORDS = (
    "rumor", "rumour", "speculation", "speculative", "reportedly",
    "sources say", "sentiment", "hype", "buzz", "social media", "reddit",
    "headline", "narrative", "media coverage", "analyst note",
    "price target", "upgrade", "downgrade", "rating", "initiated coverage",
)


def _has_technical_extreme(technicals: list[Any]) -> bool:
    """True when a technical reading is at an actionable extreme."""
    for t in technicals:
        if not isinstance(t, dict):
            continue
        rsi = t.get("rsi_14")
        try:
            if rsi is not None and (float(rsi) >= 70 or float(rsi) <= 30):
                return True
        except (TypeError, ValueError):
            pass
        # MACD crossover or band extreme is a technical trigger.
        if t.get("macd_bullish") is not None:
            return True
        bb_pos = t.get("bb_position")
        try:
            if bb_pos is not None and (float(bb_pos) >= 0.95 or float(bb_pos) <= 0.05):
                return True
        except (TypeError, ValueError):
            pass
    return False


def classify_signal_type(
    *,
    analysis_text: str,
    key_catalyst: str,
    one_line: str,
    filings: list[Any] | None,
    articles: list[Any] | None,
    technicals: list[Any] | None,
    anomaly_alerts: list[Any] | None,
) -> str:
    """Classify WHAT is driving the signal — transparent, no LLM.

    Returns FUNDAMENTAL_SHIFT | MEDIA_NARRATIVE | TECHNICAL_ONLY.

    The catalyst and one-line thesis explain the *reason* for the call, so
    their keyword hits are weighted 3× the body text.  Real artifacts
    (filings, technical extremes, article volume) add evidence boosts on
    top of the text signal.
    """
    filings = filings or []
    articles = articles or []
    technicals = technicals or []
    anomaly_alerts = anomaly_alerts or []

    weighted_text = " ".join(
        [
            ((key_catalyst or "") + " ") * 3,
            ((one_line or "") + " ") * 3,
            (analysis_text or ""),
        ]
    ).lower()

    def _count(keywords: tuple[str, ...]) -> int:
        return sum(weighted_text.count(k) for k in keywords)

    has_filings = len(filings) > 0
    has_technical_signal = bool(anomaly_alerts) or _has_technical_extreme(technicals)
    article_count = len(articles)

    fundamental_score = _count(_FUNDAMENTAL_KEYWORDS) + (3 if has_filings else 0)
    technical_score = _count(_TECHNICAL_KEYWORDS) + (3 if has_technical_signal else 0)
    media_score = _count(_MEDIA_KEYWORDS) + (1 if article_count >= 5 else 0)

    scores = {
        "FUNDAMENTAL_SHIFT": fundamental_score,
        "MEDIA_NARRATIVE": media_score,
        "TECHNICAL_ONLY": technical_score,
    }

    best = max(scores, key=lambda k: scores[k])
    if scores[best] == 0:
        # No textual signal at all — fall back to whatever raw input exists.
        if has_filings:
            return "FUNDAMENTAL_SHIFT"
        if article_count > 0:
            return "MEDIA_NARRATIVE"
        return "TECHNICAL_ONLY"

    # Fundamental vs media tie: only call it fundamental if filings back it.
    if (
        fundamental_score == media_score
        and fundamental_score >= technical_score
    ):
        return "FUNDAMENTAL_SHIFT" if has_filings else "MEDIA_NARRATIVE"

    return best


def _clean_line(line: str) -> str:
    return re.sub(r"\s+", " ", line.strip("# -*_`>\t ")).strip()


def _clean_domain(hostname: str) -> str:
    hostname = hostname.lower().strip()
    return hostname[4:] if hostname.startswith("www.") else hostname


def _is_investor_line(line: str) -> bool:
    if line.lstrip().startswith("#"):
        return False
    cleaned = _clean_line(line)
    lowered = cleaned.lower()
    if not cleaned:
        return False
    if _METADATA_LINE_RE.match(cleaned):
        return False
    if lowered.startswith(("here is", "below is", "focus:", "corrected weekly analysis")):
        return False
    return bool(re.search(r"[A-Za-z]{3,}", cleaned))


def _first_meaningful_line(block: str) -> str:
    for line in block.splitlines():
        if _is_investor_line(line):
            return _clean_line(line)
    return ""


def extract_one_line(text: str) -> str:
    """Single-line thesis (≤280 chars) — first non-blank line under
    ## Thesis / ## Signal / ## Summary, else first non-heading line."""
    labeled = _extract_labeled_value(text, (
        "one-line thesis",
        "one line thesis",
        "one-line",
        "summary",
        "thesis",
    ))
    if labeled:
        return labeled[:280]

    for marker in ("## Thesis", "## Signal", "## Summary"):
        idx = text.find(marker)
        if idx >= 0:
            after = text[idx + len(marker):].strip()
            for line in after.splitlines():
                if _is_investor_line(line):
                    return _clean_line(line)[:280]
    return next(
        (_clean_line(ln) for ln in text.splitlines() if _is_investor_line(ln)),
        "",
    )[:280]


def _extract_section(text: str, markers: tuple[str, ...]) -> str:
    """First section body matching any marker, capped at 280 chars."""
    for marker in markers:
        idx = text.find(marker)
        if idx >= 0:
            block = text[idx + len(marker):].split("\n##")[0].strip()
            return (_first_meaningful_line(block) or block)[:280]
    return ""


def _extract_labeled_value(text: str, labels: tuple[str, ...]) -> str:
    normalized_labels = {label.lower() for label in labels}
    for line in text.splitlines():
        match = _LABEL_VALUE_RE.match(line.strip())
        if not match:
            continue
        label = re.sub(r"\s+", " ", match.group("label").strip().lower())
        if label not in normalized_labels:
            continue
        body = _clean_line(match.group("body"))
        if _is_investor_line(body):
            return body[:280]
    return ""


def extract_catalyst(text: str) -> str:
    return _extract_labeled_value(text, (
        "key catalyst",
        "primary catalyst",
        "catalyst",
        "bull case",
        "upside driver",
    )) or _extract_section(text, (
        "## Key Catalyst",
        "## Primary Catalyst",
        "## Catalyst",
        "### Key Catalyst",
        "### Primary Catalyst",
        "### Catalyst",
        "## Evidence",
        "## Key Developments",
        "**Key Catalyst**",
        "**Primary Catalyst**",
        "**Catalyst**",
    ))


def extract_risk(text: str) -> str:
    return _extract_labeled_value(text, (
        "key risk",
        "primary risk",
        "invalidation risk",
        "downside risk",
        "risk",
        "bear case",
    )) or _extract_section(text, (
        "## Key Risk",
        "## Primary Risk",
        "## Invalidation Risk",
        "## Downside Risk",
        "## Risk Assessment",
        "## Risk Factors",
        "## Risk",
        "### Key Risk",
        "### Primary Risk",
        "### Invalidation Risk",
        "### Downside Risk",
        "### Risk Assessment",
        "### Risk Factors",
        "### Risk",
        "**Key Risk**",
        "**Primary Risk**",
        "**Invalidation Risk**",
        "**Downside Risk**",
        "**Risk**",
    ))


def extract_supply_chain_impact(text: str, ticker: str | None = None) -> list[dict[str, Any]]:
    raw = _extract_labeled_value(text, (
        "supply-chain ripple",
        "supply chain ripple",
        "supply-chain impact",
        "supply chain impact",
        "ripple",
    ))
    if not raw or raw.strip().lower() in {"none", "none verified", "n/a", "insufficient evidence"}:
        return []

    impacts: list[dict[str, Any]] = []
    chunks = [item.strip() for item in re.split(r"\s*[;|]\s*", raw) if item.strip()]
    for chunk in chunks[:5]:
        ticker_match = re.search(r"\b[A-Z]{1,5}(?:\.[A-Z]{1,3})?\b", chunk)
        if not ticker_match:
            continue
        impacted_ticker = ticker_match.group(0).upper()
        if ticker and impacted_ticker == ticker.upper() and len(chunks) > 1:
            continue

        direction = "◆"
        if "▲" in chunk:
            direction = "▲"
        elif "▼" in chunk:
            direction = "▼"
        elif "◆" in chunk:
            direction = "◆"
        else:
            words = set(re.findall(r"[a-z]+", chunk.lower()))
            for marker, symbol in _DIRECTION_MARKERS.items():
                if len(marker) > 1 and marker in words:
                    direction = symbol
                    break

        reason = _clean_line(chunk.replace(impacted_ticker, "", 1))
        reason = re.sub(r"^[▲▼◆+\-: ]+", "", reason).strip()
        if not reason:
            reason = "Ripple identified in analyst signal card."
        impacts.append({"ticker": impacted_ticker, "direction": direction, "reason": reason[:240]})

    return impacts


def build_sources(articles: list[Any]) -> list[dict[str, Any]]:
    """Reshape Article dataclasses into the JSONB-friendly source list."""
    out: list[dict[str, Any]] = []
    for a in articles[:10]:
        url = getattr(a, "link", "") or getattr(a, "url", "") or ""
        publisher_url = getattr(a, "publisher_url", "") or getattr(a, "source_url", "") or ""
        source_label = getattr(a, "source", "") or ""
        try:
            domain = urlparse(url).netloc
        except Exception:
            domain = ""
        if _clean_domain(domain) in {"news.google.com", "google.com"}:
            try:
                publisher_domain = urlparse(publisher_url).netloc
            except Exception:
                publisher_domain = ""
            domain = publisher_domain or source_label or domain
        out.append({
            "url": url,
            "title": getattr(a, "title", "") or "",
            "domain": _clean_domain(domain),
            "summary": (
                getattr(a, "condensed_summary", "")
                or getattr(a, "raw_summary", "")
                or ""
            ),
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
        # Non-dict items (e.g. plain strings) are intentionally ignored here.
        # They lack the structured metadata needed for claim tracking.
    return out


def build_raw_pipeline_state(state: Any) -> dict[str, Any]:
    """Keep the investor-facing evidence needed by the signal detail page."""
    if hasattr(state, "to_dict"):
        data = state.to_dict()
    else:
        data = dict(getattr(state, "__dict__", {}) or {})

    return {
        "analysis_text": data.get("analysis_text") or "",
        "news_summary": data.get("news_summary") or "",
        "summary_bullet_points": data.get("summary_bullet_points") or [],
        "data_sufficiency": data.get("data_sufficiency") or "",
        "sufficiency_reasoning": data.get("sufficiency_reasoning") or "",
        "data_gaps": data.get("data_gaps") or [],
        "anomaly_alerts": data.get("anomaly_alerts") or [],
        "ai_predictions": data.get("ai_predictions") or [],
        "prices": data.get("prices") or [],
        "technicals": data.get("technicals") or [],
        "filings": data.get("filings") or [],
        "articles": data.get("articles") or [],
        "validation_text": data.get("validation_text") or "",
        "validation_status": data.get("validation_status") or "",
        "validation_issues": data.get("validation_issues") or [],
        "reasoning_scores": data.get("reasoning_scores") or {},
        "confidence_breakdown": data.get("confidence_breakdown") or {},
        "confidence_score": data.get("confidence_score") or 0,
        "rag_metadata": data.get("rag_metadata") or {},
        "sector_id": data.get("sector_id") or "",
        "sector_name": data.get("sector_name") or "",
        "agent_id": data.get("agent_id"),
        "agent_name": data.get("agent_name") or "",
    }


def cap_confidence_for_missing_evidence(
    confidence: float,
    *,
    one_line: str,
    key_catalyst: str,
    key_risk: str,
    sources: list[dict[str, Any]],
) -> float:
    """Prevent weakly structured cards from carrying strong confidence."""
    has_sources = any(source.get("url") or source.get("title") for source in sources)
    if not one_line or not has_sources:
        return min(confidence, 0.4)
    if not key_catalyst.strip() or not key_risk.strip():
        return min(confidence, 0.65)
    return confidence


def from_pipeline_state(
    *,
    state: Any,
    run_id: str,
    ticker: str,
    user_email: str | None,
    agent_id: int | None = None,
) -> SignalCardDraft:
    """Build a `SignalCardDraft` from a finished `PipelineState`.

    Pure — safe to call from a worker thread.
    """
    text = getattr(state, "analysis_text", "") or ""
    one_line = extract_one_line(text)
    key_catalyst = extract_catalyst(text)
    key_risk = extract_risk(text)
    sources = build_sources(getattr(state, "articles", []) or [])
    raw_confidence = float(getattr(state, "confidence_score", 0) or 0.0) / 10.0

    filings = getattr(state, "filings", []) or []
    articles = getattr(state, "articles", []) or []
    technicals = getattr(state, "technicals", []) or []
    anomaly_alerts = getattr(state, "anomaly_alerts", []) or []

    signal_type = classify_signal_type(
        analysis_text=text,
        key_catalyst=key_catalyst,
        one_line=one_line,
        filings=filings,
        articles=articles,
        technicals=technicals,
        anomaly_alerts=anomaly_alerts,
    )

    # Carry the "was conviction explicitly stated?" flag through the JSONB
    # blob so the UI never presents the default-3 fallback as a real score.
    raw_pipeline_state = build_raw_pipeline_state(state)
    raw_pipeline_state["conviction_stated"] = conviction_was_stated(text)

    return SignalCardDraft(
        ticker=ticker,
        run_id=run_id,
        agent_id=agent_id,
        user_email=user_email,
        signal=extract_signal(text),
        conviction=extract_conviction(text),
        one_line=one_line,
        key_catalyst=key_catalyst,
        key_risk=key_risk,
        confidence=cap_confidence_for_missing_evidence(
            raw_confidence,
            one_line=one_line,
            key_catalyst=key_catalyst,
            key_risk=key_risk,
            sources=sources,
        ),
        signal_type=signal_type,
        validation_score=normalize_validation_status(
            getattr(state, "validation_status", "")
        ),
        supply_chain_impact=extract_supply_chain_impact(text, ticker=ticker),
        sources=sources,
        numerical_claims=build_numerical_claims(state),
        sector_context={
            "sector_id": getattr(state, "sector_id", ""),
            "sector_name": getattr(state, "sector_name", ""),
        },
        raw_pipeline_state=raw_pipeline_state,
    )
