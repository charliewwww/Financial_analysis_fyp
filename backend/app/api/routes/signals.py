"""
Signals router — the Phase 1+ primary output surface.

Signal cards are the structured, per-ticker verdicts produced by the new
pipeline (signal, conviction, validated numerical claims, supply chain impact).
This router is what the Morning Brief, Board of Analysts, and Track Record
pages in the Next.js frontend consume.

Endpoints:
    GET  /api/v1/signals                        Paginated list with filters
    GET  /api/v1/signals/accuracy               Track Record stats (Phase 2.3)
    GET  /api/v1/signals/latest/{ticker}        Most recent signal for a ticker
    GET  /api/v1/signals/{card_id}              Full signal card
    POST /api/v1/signals/{card_id}/chat         Evidence-scoped chat for a signal card
    GET  /api/v1/signals/{card_id}/predictions  Predictions for a signal card

Path ordering matters: static segments (`/accuracy`, `/latest/{ticker}`)
must be declared BEFORE `/{card_id}` so FastAPI's router doesn't try to
interpret "accuracy" as an integer card ID.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Annotated
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncConnection

from agents.llm_client import call_llm_fast
from app.core.auth import CurrentUser
from app.db.engine import get_db
from app.db.repositories import chief_verdicts as verdict_repo
from app.db.repositories import predictions as pred_repo
from app.db.repositories import signals as signal_repo
from app.schemas.analysis import (
    ChiefVerdictAccuracy,
    ChiefVerdictResponse,
    SignalCardSchema,
    SignalChatCitation,
    SignalChatRequest,
    SignalChatResponse,
)
from app.schemas.common import PaginatedResponse
from app.schemas.reports import AccuracyStats, PredictionSchema
from app.services import chief_strategist as chief_strategist_service

router = APIRouter(prefix="/signals", tags=["signals"])
logger = logging.getLogger(__name__)

DB = Annotated[AsyncConnection, Depends(get_db)]

DEFAULT_CHAT_SUGGESTIONS = [
    "What changed?",
    "What would invalidate this?",
    "Which supplier or customer is affected?",
    "Which claims are verified?",
]


def _compact_text(value: Any, *, limit: int = 1200) -> str:
    if value is None:
        return ""
    text = " ".join(str(value).split())
    if len(text) <= limit:
        return text
    return f"{text[: limit - 3].rstrip()}..."


def _json_text(value: Any, *, limit: int = 1800) -> str:
    try:
        text = json.dumps(value, ensure_ascii=True, default=str)
    except TypeError:
        text = str(value)
    return _compact_text(text, limit=limit)


def _citation(
    label: str,
    source_type: str,
    source: str = "",
    url: str | None = None,
    quote: str = "",
) -> SignalChatCitation:
    return SignalChatCitation(
        label=label,
        source_type=source_type,  # type: ignore[arg-type]
        source=source,
        url=url,
        quote=_compact_text(quote, limit=360),
    )


def _build_signal_evidence_pack(
    card: SignalCardSchema,
    context: str | None,
) -> tuple[str, list[SignalChatCitation]]:
    rows: list[str] = [
        f"Signal card: #{card.id or 'unknown'} for {card.ticker}",
        f"Verdict: {card.signal}; conviction: {card.conviction}/5; confidence: {card.confidence:.2f}",
        f"One-line thesis: {_compact_text(card.one_line, limit=500)}",
    ]
    citations: list[SignalChatCitation] = [
        _citation("analysis: thesis", "analysis", quote=card.one_line),
    ]

    if card.key_catalyst:
        rows.append(f"Key catalyst [analysis: catalyst]: {_compact_text(card.key_catalyst, limit=500)}")
        citations.append(_citation("analysis: catalyst", "analysis", quote=card.key_catalyst))
    if card.key_risk:
        rows.append(f"Key risk [analysis: risk]: {_compact_text(card.key_risk, limit=500)}")
        citations.append(_citation("analysis: risk", "analysis", quote=card.key_risk))
    if card.validation_score:
        rows.append(f"Validation score: {card.validation_score}")
    if card.data_sufficiency or card.sufficiency_reasoning:
        rows.append(
            "Data sufficiency [analysis: data quality]: "
            f"{_compact_text(card.data_sufficiency, limit=120)} - {_compact_text(card.sufficiency_reasoning, limit=700)}"
        )
        citations.append(
            _citation("analysis: data quality", "analysis", quote=f"{card.data_sufficiency}: {card.sufficiency_reasoning}")
        )

    if context:
        rows.append(f"Decision Desk context [decision: board rules]: {_compact_text(context, limit=1800)}")
        citations.append(_citation("decision: board rules", "decision", quote=context))

    if card.numerical_claims:
        rows.append("Numerical claims:")
        for index, claim in enumerate(card.numerical_claims[:8], start=1):
            label = f"claim: {index}"
            status_label = "verified" if claim.verified else "unverified"
            rows.append(f"- [{label}] {claim.claim} ({status_label}; source: {claim.source or 'not provided'})")
            citations.append(_citation(label, "claim", source=claim.source, quote=claim.claim))

    if card.sources:
        rows.append("Sources:")
        for index, source in enumerate(card.sources[:8], start=1):
            domain = source.domain or source.title or source.url or f"source {index}"
            label = f"source: {domain}"
            summary = source.summary or source.title or source.url
            rows.append(f"- [{label}] {source.title or domain}: {_compact_text(summary, limit=500)}")
            citations.append(_citation(label, "source", source=domain, url=source.url, quote=summary))

    if card.supply_chain_impact:
        rows.append("Supply-chain impact:")
        for impact in card.supply_chain_impact[:8]:
            label = f"ripple: {impact.ticker}"
            rows.append(f"- [{label}] {impact.direction} {impact.ticker}: {_compact_text(impact.reason, limit=420)}")
            citations.append(_citation(label, "supply_chain", source=impact.ticker, quote=impact.reason))

    if card.news_summary:
        rows.append(f"News summary [analysis: news summary]: {_compact_text(card.news_summary, limit=1800)}")
        citations.append(_citation("analysis: news summary", "analysis", quote=card.news_summary))

    if card.article_evidence:
        rows.append("Article evidence:")
        for index, article in enumerate(card.article_evidence[:6], start=1):
            title = _compact_text(article.get("title") or article.get("source") or f"Article {index}", limit=180)
            link = article.get("link") or article.get("url")
            source = _compact_text(article.get("source") or article.get("domain") or title, limit=120)
            summary = article.get("condensed_summary") or article.get("raw_summary") or article.get("summary") or ""
            label = f"article: {index}"
            rows.append(f"- [{label}] {title} ({source}): {_compact_text(summary, limit=600)}")
            citations.append(_citation(label, "source", source=source, url=str(link) if link else None, quote=summary or title))

    if card.price_snapshot:
        rows.append(f"Price snapshot [snapshot: prices]: {_json_text(card.price_snapshot[:6], limit=1600)}")
        citations.append(_citation("snapshot: prices", "snapshot", quote=_json_text(card.price_snapshot[:6], limit=360)))
    if card.technical_snapshot:
        rows.append(f"Technical snapshot [snapshot: technicals]: {_json_text(card.technical_snapshot[:6], limit=1600)}")
        citations.append(_citation("snapshot: technicals", "snapshot", quote=_json_text(card.technical_snapshot[:6], limit=360)))
    if card.analysis_text:
        rows.append(f"Full analysis excerpt [analysis: full text]: {_compact_text(card.analysis_text, limit=2600)}")
        citations.append(_citation("analysis: full text", "analysis", quote=card.analysis_text))

    return "\n".join(row for row in rows if row.strip()), citations


def _strip_json_fence(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


def _parse_chat_response(raw: str, citations: list[SignalChatCitation]) -> SignalChatResponse:
    available = {item.label: item for item in citations}
    try:
        parsed = json.loads(_strip_json_fence(raw))
        data = parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        data = {
            "answer": raw,
            "citations": [],
            "limitations": ["The model returned text instead of the expected structured response."],
        }

    answer = _compact_text(data.get("answer") or "The evidence pack is not sufficient to answer that question.", limit=2400)
    requested_labels = data.get("citations") if isinstance(data.get("citations"), list) else []
    response_citations = [available[label] for label in requested_labels if isinstance(label, str) and label in available]
    limitations = [
        _compact_text(item, limit=260)
        for item in (data.get("limitations") if isinstance(data.get("limitations"), list) else [])
        if isinstance(item, str) and item.strip()
    ][:4]

    return SignalChatResponse(
        answer=answer,
        citations=response_citations[:5],
        limitations=limitations,
        grounded=bool(data.get("grounded", bool(response_citations))),
        suggested_questions=DEFAULT_CHAT_SUGGESTIONS,
    )


def _fallback_chat_response(
    card: SignalCardSchema,
    question: str,
    citations: list[SignalChatCitation],
    reason: str | None = None,
) -> SignalChatResponse:
    lower = question.lower()
    selected: list[str] = []
    if any(term in lower for term in ("risk", "invalidate", "wrong")) and card.key_risk:
        selected.append(f"Risk: {card.key_risk}")
    if any(term in lower for term in ("catalyst", "changed", "change", "why")) and card.key_catalyst:
        selected.append(f"Catalyst: {card.key_catalyst}")
    if any(term in lower for term in ("supplier", "customer", "supply", "chain", "ripple")) and card.supply_chain_impact:
        selected.extend([f"{item.direction} {item.ticker}: {item.reason}" for item in card.supply_chain_impact[:3]])
    if any(term in lower for term in ("claim", "verified", "source")) and card.numerical_claims:
        selected.extend([
            f"{claim.claim} ({'verified' if claim.verified else 'unverified'}; {claim.source or 'no source listed'})"
            for claim in card.numerical_claims[:3]
        ])

    if not selected:
        selected = [card.one_line]

    limitations = [
        "This fallback answer uses only structured signal-card fields.",
    ]
    if reason:
        limitations.append(f"LLM evidence chat unavailable: {reason}")

    return SignalChatResponse(
        answer=" ".join(_compact_text(item, limit=500) for item in selected if item).strip()
        or "The signal card does not contain enough evidence to answer that question.",
        citations=citations[:3],
        limitations=limitations[:4],
        grounded=True,
        suggested_questions=DEFAULT_CHAT_SUGGESTIONS,
    )


# ── Accuracy stats  (declared first — static path) ─────────────────

@router.get(
    "/accuracy",
    response_model=AccuracyStats,
    summary="Prediction accuracy stats",
    description=(
        "Aggregated directional accuracy across all checked predictions. "
        "Drives the Track Record page (Phase 2.3). "
        "`direction_accuracy_pct` is null until at least one prediction "
        "has been verified by the weekly accuracy-check job."
    ),
)
async def get_accuracy(db: DB, user: CurrentUser) -> AccuracyStats:
    return await pred_repo.get_accuracy_stats(db, user_email=user)


# ── Latest signal for a ticker  (declared before /{card_id}) ────────

@router.get(
    "/latest/{ticker}",
    response_model=SignalCardSchema,
    summary="Latest signal for a ticker",
    description=(
        "Returns the most recent signal card for the given ticker symbol. "
        "Pass `agent_id` to scope to a specific analyst agent "
        "(e.g. the Supply Chain Analyst)."
    ),
)
async def get_latest_signal(
    ticker: str,
    db: DB,
    user: CurrentUser,
    agent_id: int | None = Query(
        default=None,
        description="Scope to a specific agent. Omit for the system default.",
    ),
) -> SignalCardSchema:
    card = await signal_repo.get_latest_signal(
        db, ticker.upper(), agent_id=agent_id, user_email=user
    )
    if card is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No signal found for ticker '{ticker.upper()}'.",
        )
    return card


# ── Chief Strategist verdict for a ticker  (declared before /{card_id}) ──


@router.get(
    "/verdict/{ticker}",
    response_model=ChiefVerdictResponse,
    summary="Chief Strategist house verdict for a ticker",
    description=(
        "Reads the latest signal card from every analyst for the ticker and asks "
        "the Chief Strategist meta-agent to weigh them into one BUY/SELL/HOLD call "
        "with a conviction and a single deciding reason."
    ),
)
async def get_chief_verdict(ticker: str, db: DB, user: CurrentUser) -> ChiefVerdictResponse:
    symbol = ticker.upper()
    verdict = await chief_strategist_service.generate_verdict(
        db, symbol, user, persist=True
    )
    if verdict is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No analyst signal cards for '{symbol}' yet. Run the board first.",
        )
    return verdict


@router.get(
    "/verdicts/accuracy",
    response_model=ChiefVerdictAccuracy,
    summary="Chief Strategist 'House Call' track record",
    description=(
        "Aggregate accuracy of the Chief Strategist's auto-generated house verdicts, "
        "resolved against the actual 1-week price move. Powers the 'House Call' "
        "section on the prediction/accuracy page."
    ),
)
async def get_chief_verdict_accuracy(
    db: DB,
    user: CurrentUser,
    market: str | None = Query(default=None, description="us | hk"),
) -> ChiefVerdictAccuracy:
    return await verdict_repo.get_accuracy(db, user_email=user, market=market)


@router.post(
    "/verdicts/resolve",
    summary="Resolve due house verdicts and self-refine the strategist",
    description=(
        "Scores the Chief Strategist's verdicts that are at least one week old "
        "against the actual price move, then distils the resulting hits and "
        "misses into calibration notes the strategist applies on its next run. "
        "Normally run by a scheduled weekly job; exposed here for on-demand use."
    ),
)
async def resolve_chief_verdicts(
    db: DB,
    user: CurrentUser,
    min_age_days: float = Query(
        default=7.0,
        ge=0.0,
        description="Only resolve verdicts at least this many days old.",
    ),
) -> dict[str, Any]:
    from app.services import accuracy_resolver

    return await accuracy_resolver.run_resolution(db, min_age_days=min_age_days)


@router.post(
    "/predictions/resolve",
    summary="Resolve due per-ticker predictions against their actual outcome",
    description=(
        "Scores analyst predictions that are at least one week old against the "
        "current price as a proxy for the realised 1-week move (the Track Record "
        "engine). Normally run by the daily scheduler; exposed here for on-demand "
        "use and testing."
    ),
)
async def resolve_predictions_route(
    db: DB,
    user: CurrentUser,
    min_age_days: float = Query(
        default=7.0,
        ge=0.0,
        description="Only resolve predictions at least this many days old.",
    ),
) -> dict[str, int]:
    from app.services import prediction_resolver

    resolved = await prediction_resolver.resolve_predictions(
        db, min_age_days=min_age_days
    )
    return {"resolved": resolved}


# ── Paginated list with filters ────────────────────────────────────

@router.get(
    "/",
    response_model=PaginatedResponse[SignalCardSchema],
    summary="List signal cards",
    description=(
        "Paginated list of signal cards, newest first. "
        "All query parameters are optional and combinable:\n"
        "- `ticker` — filter to a single ticker\n"
        "- `signal` — BULLISH | BEARISH | NEUTRAL\n"
        "- `signal_type` — FUNDAMENTAL_SHIFT | MEDIA_NARRATIVE | TECHNICAL_ONLY\n"
        "- `agent_id` — filter to a specific analyst agent\n"
        "- `market` — us | hk (hk = '*.HK' tickers); keeps the HK view free of US names\n\n"
        "These filters power the Morning Brief filter panel (Phase 2 — User Insight Explorer)."
    ),
)
async def list_signals(
    db: DB,
    user: CurrentUser,
    ticker: str | None = Query(default=None, description="e.g. 'NVDA' or '0700.HK'"),
    signal: str | None = Query(default=None, description="BULLISH | BEARISH | NEUTRAL"),
    signal_type: str | None = Query(
        default=None,
        description="FUNDAMENTAL_SHIFT | MEDIA_NARRATIVE | TECHNICAL_ONLY",
    ),
    agent_id: int | None = Query(default=None),
    market: str | None = Query(default=None, description="us | hk"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> PaginatedResponse[SignalCardSchema]:
    items, total = await signal_repo.list_signal_cards(
        db,
        ticker=ticker,
        signal=signal,
        signal_type=signal_type,
        agent_id=agent_id,
        market=market,
        user_email=user,
        page=page,
        page_size=page_size,
    )
    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        has_next=(page * page_size) < total,
    )


# ── Signal card detail ─────────────────────────────────────────────

@router.get(
    "/{card_id}",
    response_model=SignalCardSchema,
    summary="Get signal card",
    description=(
        "Returns the full signal card including all numerical claims, "
        "sources, and supply chain impact entries."
    ),
)
async def get_signal_card(card_id: int, db: DB, user: CurrentUser) -> SignalCardSchema:
    card = await signal_repo.get_signal_card(db, card_id, user_email=user)
    if card is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Signal card {card_id} not found.",
        )
    return card


# ── Evidence chat for a signal card ───────────────────────────────

@router.post(
    "/{card_id}/chat",
    response_model=SignalChatResponse,
    summary="Ask a signal card evidence question",
    description=(
        "Answers a question using only the selected signal card's evidence pack. "
        "If the evidence does not support an answer, the response says so instead "
        "of inventing a finance-chatbot answer."
    ),
)
async def chat_signal_card(
    card_id: int,
    request: SignalChatRequest,
    db: DB,
    user: CurrentUser,
) -> SignalChatResponse:
    card = await signal_repo.get_signal_card(db, card_id, user_email=user)
    if card is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Signal card {card_id} not found.",
        )

    evidence_pack, citations = _build_signal_evidence_pack(card, request.context)
    history = "\n".join(
        f"{turn.role}: {_compact_text(turn.content, limit=500)}"
        for turn in request.history[-6:]
    )
    citation_labels = [item.label for item in citations]

    system_prompt = (
        "You are MarketPulse Evidence Chat. Answer only from the provided signal-card evidence pack "
        "and optional Decision Desk context. Do not provide personalized financial advice, trade instructions, "
        "or facts outside the evidence. If the evidence is insufficient, say that clearly. "
        "Return valid JSON only with keys: answer (string), citations (array of exact labels from Available citations), "
        "limitations (array of strings), grounded (boolean). Keep the answer concise."
    )
    prompt = (
        f"Question: {request.question}\n\n"
        f"Recent conversation:\n{history or 'None'}\n\n"
        f"Available citations:\n{json.dumps(citation_labels, ensure_ascii=True)}\n\n"
        f"Evidence pack:\n{evidence_pack}"
    )

    try:
        raw = await asyncio.to_thread(
            call_llm_fast,
            prompt,
            system_prompt,
            temperature=0.1,
            max_tokens=900,
            langfuse_name="signal_evidence_chat",
            langfuse_metadata={"signal_card_id": card_id, "ticker": card.ticker},
        )
        return _parse_chat_response(raw, citations)
    except Exception as exc:  # pragma: no cover - the route returns a deterministic fallback
        logger.warning("Signal evidence chat fallback for card %s: %s", card_id, exc)
        return _fallback_chat_response(card, request.question, citations, reason=str(exc))


# ── Predictions for a signal card ─────────────────────────────────

@router.get(
    "/{card_id}/predictions",
    response_model=list[PredictionSchema],
    summary="Predictions for a signal card",
    description=(
        "Returns all price predictions recorded when this signal card was created. "
        "The `prediction_correct` field is null until the weekly accuracy job runs."
    ),
)
async def get_signal_predictions(
    card_id: int, db: DB, user: CurrentUser
) -> list[PredictionSchema]:
    card = await signal_repo.get_signal_card(db, card_id, user_email=user)
    if card is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Signal card {card_id} not found.",
        )
    return await pred_repo.list_for_signal_card(db, card_id)
