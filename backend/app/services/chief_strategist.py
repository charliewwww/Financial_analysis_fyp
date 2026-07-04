"""
Chief Strategist service — the desk's final-gate verdict, shared by the API
endpoint and the pipeline runner's auto-trigger.

The verdict weighs every analyst's signal card for a ticker into one decisive
BUY/SELL/HOLD call with a probability-weighted risk assessment, optionally
injects the self-refining "lessons" addendum, and persists the result to the
chief_verdicts table so the desk's own accuracy can be tracked.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncConnection

from agents.llm_client import call_llm_fast
from app.core.builtin_agents import CHIEF_STRATEGIST_PROMPT
from app.db.repositories import agents as agent_repo
from app.db.repositories import chief_strategist_memory as memory_repo
from app.db.repositories import chief_verdicts as verdict_repo
from app.db.repositories import signals as signal_repo
from app.schemas.analysis import (
    ChiefVerdictAnalystView,
    ChiefVerdictResponse,
    SignalCardSchema,
)

logger = logging.getLogger(__name__)


# ── Small parsing helpers (kept local to avoid a route ↔ service cycle) ──

def _compact(value: Any, *, limit: int = 1200) -> str:
    if value is None:
        return ""
    text = " ".join(str(value).split())
    if len(text) <= limit:
        return text
    return f"{text[: limit - 3].rstrip()}..."


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


def _normalize_action(value: Any) -> str:
    text = str(value or "").strip().upper()
    if text in {"BUY", "SELL", "HOLD"}:
        return text
    if text in {"LONG", "ADD", "BULLISH"}:
        return "BUY"
    if text in {"SHORT", "TRIM", "AVOID", "BEARISH"}:
        return "SELL"
    return "HOLD"


def _clamp_conviction(value: Any) -> int:
    try:
        n = int(round(float(value)))
    except (TypeError, ValueError):
        return 3
    return max(1, min(5, n))


def _price_for_ticker(card: SignalCardSchema, symbol: str) -> float | None:
    """Best-effort current price snapshot from a signal card."""
    for entry in card.price_snapshot or []:
        if not isinstance(entry, dict):
            continue
        if str(entry.get("ticker", "")).upper() not in {"", symbol}:
            continue
        price = entry.get("price")
        if isinstance(price, (int, float)) and price > 0:
            return float(price)
    return None


async def generate_verdict(
    db: AsyncConnection,
    ticker: str,
    user_email: str | None,
    *,
    run_id: str | None = None,
    persist: bool = True,
    use_lessons: bool = True,
) -> ChiefVerdictResponse | None:
    """
    Build (and optionally persist) the Chief Strategist's house verdict.

    Returns ``None`` when there are no analyst cards to weigh.
    """
    symbol = ticker.upper()
    cards, _ = await signal_repo.list_signal_cards(
        db, ticker=symbol, user_email=user_email, page=1, page_size=50
    )
    if not cards:
        return None

    # Keep the most recent card per agent (cards arrive newest-first).
    latest_by_agent: dict[Any, SignalCardSchema] = {}
    for card in cards:
        key = card.agent_id if card.agent_id is not None else f"_legacy_{card.id}"
        if key not in latest_by_agent:
            latest_by_agent[key] = card

    try:
        agent_rows = await agent_repo.list_agents(db)
        agent_names = {row.id: row.name for row in agent_rows}
    except Exception:  # pragma: no cover - name lookup is best-effort
        agent_names = {}

    analysts: list[ChiefVerdictAnalystView] = []
    for card in latest_by_agent.values():
        name = (
            agent_names.get(card.agent_id, "Analyst")
            if card.agent_id is not None
            else "Analyst"
        )
        analysts.append(
            ChiefVerdictAnalystView(
                agent_id=card.agent_id,
                agent_name=name,
                signal=card.signal,
                conviction=card.conviction,
                one_line=_compact(card.one_line, limit=400),
            )
        )

    lines: list[str] = [
        f"Ticker: {symbol}",
        f"Analysts reporting: {len(analysts)}",
        "",
    ]
    for view in analysts:
        catalyst = next(
            (
                c.key_catalyst
                for c in latest_by_agent.values()
                if c.agent_id == view.agent_id and c.key_catalyst
            ),
            "",
        )
        risk = next(
            (
                c.key_risk
                for c in latest_by_agent.values()
                if c.agent_id == view.agent_id and c.key_risk
            ),
            "",
        )
        lines.append(
            f"- {view.agent_name}: {view.signal} (conviction {view.conviction}/5). "
            f"Thesis: {view.one_line or 'n/a'}."
        )
        if catalyst:
            lines.append(f"    Catalyst: {_compact(catalyst, limit=300)}")
        if risk:
            lines.append(f"    Risk: {_compact(risk, limit=300)}")
    prompt = "\n".join(lines)

    # Self-refining calibration notes prepended to the base prompt.
    system_prompt = CHIEF_STRATEGIST_PROMPT
    if use_lessons:
        try:
            lessons = await memory_repo.get_lessons(db, user_email)
        except Exception:  # pragma: no cover - lessons are best-effort
            lessons = ""
        if lessons.strip():
            system_prompt = (
                f"{CHIEF_STRATEGIST_PROMPT}\n\n"
                "CALIBRATION NOTES FROM YOUR OWN TRACK RECORD "
                "(apply these lessons learned from past hits and misses):\n"
                f"{_compact(lessons, limit=1500)}"
            )

    generated_at = datetime.now(timezone.utc).isoformat()

    try:
        raw = await asyncio.to_thread(
            call_llm_fast,
            prompt,
            system_prompt,
            temperature=0.2,
            max_tokens=800,
            langfuse_name="chief_strategist_verdict",
            langfuse_metadata={"ticker": symbol, "analysts": len(analysts)},
        )
        parsed = json.loads(_strip_json_fence(raw))
        data = parsed if isinstance(parsed, dict) else {}
    except Exception as exc:  # pragma: no cover - deterministic fallback below
        logger.warning("Chief Strategist verdict fallback for %s: %s", symbol, exc)
        data = {}

    if data:
        agreement = str(data.get("agreement", "mixed")).strip().lower()
        if agreement not in {"aligned", "mixed", "split"}:
            agreement = "mixed"
        verdict = ChiefVerdictResponse(
            ticker=symbol,
            action=_normalize_action(data.get("action")),  # type: ignore[arg-type]
            conviction=_clamp_conviction(data.get("conviction")),
            deciding_reason=_compact(data.get("deciding_reason"), limit=400),
            summary=_compact(data.get("summary"), limit=900),
            agreement=agreement,  # type: ignore[arg-type]
            dissent=_compact(data.get("dissent"), limit=400),
            risk_assessment=_compact(data.get("risk_assessment"), limit=700),
            analysts=analysts,
            generated_at=generated_at,
        )
    else:
        # Rule-based fallback so the desk never hard-fails.
        bull = sum(1 for v in analysts if v.signal == "BULLISH")
        bear = sum(1 for v in analysts if v.signal == "BEARISH")
        action = "BUY" if bull > bear else "SELL" if bear > bull else "HOLD"
        agreement = (
            "aligned"
            if (bull == 0 or bear == 0) and len(analysts) > 1
            else "split"
            if bull and bear
            else "mixed"
        )
        verdict = ChiefVerdictResponse(
            ticker=symbol,
            action=action,  # type: ignore[arg-type]
            conviction=3,
            deciding_reason=(
                "Computed from analyst majority (the strategist model was unavailable)."
            ),
            summary=f"{bull} bullish vs {bear} bearish across {len(analysts)} analysts.",
            agreement=agreement,  # type: ignore[arg-type]
            dissent="",
            risk_assessment="",
            analysts=analysts,
            generated_at=generated_at,
        )

    if persist:
        price_at_verdict: float | None = None
        for card in latest_by_agent.values():
            price_at_verdict = _price_for_ticker(card, symbol)
            if price_at_verdict is not None:
                break
        try:
            await verdict_repo.create(
                db,
                {
                    "ticker": symbol,
                    "run_id": run_id,
                    "user_email": user_email,
                    "action": verdict.action,
                    "conviction": verdict.conviction,
                    "deciding_reason": verdict.deciding_reason,
                    "summary": verdict.summary,
                    "agreement": verdict.agreement,
                    "dissent": verdict.dissent,
                    "risk_assessment": verdict.risk_assessment,
                    "analyst_count": len(analysts),
                    "analyst_snapshot": [
                        {
                            "agent_name": v.agent_name,
                            "signal": v.signal,
                            "conviction": v.conviction,
                        }
                        for v in analysts
                    ],
                    "price_at_verdict": price_at_verdict,
                },
            )
        except Exception:  # pragma: no cover - persistence is best-effort
            logger.exception("Failed to persist chief verdict for %s", symbol)

    return verdict
