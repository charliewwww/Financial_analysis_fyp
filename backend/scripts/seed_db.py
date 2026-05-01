"""
Seed the PostgreSQL database with realistic mock data for local E2E testing.

Usage (venv activated, run from backend/):

    python scripts/seed_db.py

The script is idempotent — it deletes any existing rows for SEED_USER before
inserting fresh ones, so it is safe to run repeatedly.

Requires DATABASE_URL to be set in ../.env (relative to the repo root).
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

# ── Make backend/ importable and load .env from repo root ─────────
_BACKEND = Path(__file__).resolve().parents[1]
_REPO_ROOT = _BACKEND.parent
sys.path.insert(0, str(_BACKEND))

# Explicitly load .env so DATABASE_URL is in os.environ before Settings()
# is instantiated (pydantic-settings also reads env vars, so this bridges
# the case where the script is run from a non-backend CWD).
try:
    from dotenv import load_dotenv

    _env_path = _REPO_ROOT / ".env"
    if _env_path.exists():
        load_dotenv(_env_path, override=False)
except ImportError:
    pass  # python-dotenv not installed — rely on actual env vars

from sqlalchemy import delete, insert, select, update  # noqa: E402
from sqlalchemy.ext.asyncio import create_async_engine  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.db.tables import pipeline_runs, reports, signal_cards  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("seed")

SEED_USER = "test@example.com"
_NOW = datetime.now(timezone.utc)


def _dt(days: int = 0, hours: int = 0) -> datetime:
    return _NOW - timedelta(days=days, hours=hours)


# ── Seed definitions ───────────────────────────────────────────────

_RUN_IDS = [str(uuid4()) for _ in range(5)]

_SIGNAL_CARDS_DATA = [
    {
        "ticker": "NVDA",
        "run_id": _RUN_IDS[0],
        "signal": "BULLISH",
        "conviction": 4,
        "one_line": "H200 backorder confirmation + institutional accumulation = near-term upside.",
        "key_catalyst": "Jensen confirmed H200 backorders through Q3 2026 on the earnings call.",
        "key_risk": "US export-control escalation could restrict ~20% of addressable datacenter market.",
        "confidence": 0.82,
        "signal_type": "FUNDAMENTAL_SHIFT",
        "validation_score": "3/4 claims verified",
        "supply_chain_impact": [
            {"ticker": "TSM", "direction": "▲", "reason": "CoWoS packaging orders rise with H200 ramp"},
            {"ticker": "CEG", "direction": "▲", "reason": "Datacenter power demand +40% confirmed"},
            {"ticker": "ANET", "direction": "▲", "reason": "InfiniBand replacement with Arista in new clusters"},
        ],
        "sources": [
            {"url": "https://www.reuters.com/technology/nvidia-earnings-2026", "title": "NVDA Q1 2026 Earnings", "domain": "reuters.com"},
            {"url": "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=NVDA", "title": "NVDA 10-K 2025", "domain": "sec.gov"},
        ],
        "numerical_claims": [
            {"claim": "H200 ASP $35,000", "verified": True, "source": "earnings call Q1 2026"},
            {"claim": "CoWoS capacity +40%", "verified": True, "source": "TSMC IR Q1 2026"},
            {"claim": "Volume +2.1σ above 30-day average", "verified": True, "source": "Yahoo Finance"},
            {"claim": "AI capex $200B combined", "verified": False, "source": "unverified estimate"},
        ],
        "sector_context": {"sector": "semiconductors", "peers": ["TSMC", "ASML", "AMD"]},
        "raw_pipeline_state": None,
        "created_at": _dt(days=4),
        "status": "active",
        "user_email": SEED_USER,
    },
    {
        "ticker": "TSM",
        "run_id": _RUN_IDS[1],
        "signal": "BULLISH",
        "conviction": 3,
        "one_line": "CoWoS expansion removes NVDA packaging bottleneck — upstream demand confirmed.",
        "key_catalyst": "TSMC CoWoS capacity expansion +40% removes H200 production constraint.",
        "key_risk": "Geopolitical risk — Taiwan Strait tension adds tail risk to any long position.",
        "confidence": 0.71,
        "signal_type": "FUNDAMENTAL_SHIFT",
        "validation_score": "3/3 claims verified",
        "supply_chain_impact": [
            {"ticker": "NVDA", "direction": "▲", "reason": "H200 packaging bottleneck resolves Q3 2026"},
            {"ticker": "ASML", "direction": "▲", "reason": "EUV tool orders from TSMC expected to rise"},
        ],
        "sources": [
            {"url": "https://investor.tsmc.com/english/quarterly-results/2026/q1", "title": "TSMC Q1 2026 Analyst Day", "domain": "tsmc.com"},
        ],
        "numerical_claims": [
            {"claim": "CoWoS capacity +40% by Q3 2026", "verified": True, "source": "TSMC IR"},
            {"claim": "Revenue guidance NT$850B Q2 2026", "verified": True, "source": "earnings call"},
            {"claim": "Advanced packaging now 35% of revenue", "verified": True, "source": "TSMC 20-F"},
        ],
        "sector_context": {"sector": "semiconductors", "peers": ["NVDA", "ASML", "INTC"]},
        "raw_pipeline_state": None,
        "created_at": _dt(days=3),
        "status": "active",
        "user_email": SEED_USER,
    },
    {
        "ticker": "AAPL",
        "run_id": _RUN_IDS[2],
        "signal": "NEUTRAL",
        "conviction": 2,
        "one_line": "RSI reset with no fundamental catalyst — wait for June WWDC guidance.",
        "key_catalyst": "Services revenue +18% YoY provides defensive floor.",
        "key_risk": "iPhone 17 cycle underwhelm — early channel checks suggest modest upgrade intent.",
        "confidence": 0.55,
        "signal_type": "TECHNICAL_ONLY",
        "validation_score": "1/2 claims verified",
        "supply_chain_impact": [
            {"ticker": "QCOM", "direction": "◆", "reason": "Modem supply unchanged — no design change signal"},
        ],
        "sources": [
            {"url": "https://investor.apple.com/sec-filings/annual-reports/default.aspx", "title": "AAPL 10-K 2025", "domain": "apple.com"},
        ],
        "numerical_claims": [
            {"claim": "Services revenue $26B Q1 FY2026", "verified": True, "source": "earnings release"},
            {"claim": "iPhone 17 pre-orders +12% vs iPhone 16", "verified": False, "source": "unconfirmed channel check"},
        ],
        "sector_context": {"sector": "consumer_tech", "peers": ["MSFT", "GOOG", "META"]},
        "raw_pipeline_state": None,
        "created_at": _dt(days=2),
        "status": "active",
        "user_email": SEED_USER,
    },
    {
        "ticker": "MSFT",
        "run_id": _RUN_IDS[3],
        "signal": "BULLISH",
        "conviction": 4,
        "one_line": "Azure AI revenue +65% YoY with Copilot monetisation accelerating.",
        "key_catalyst": "Azure AI services segment confirmed inflection — Copilot M365 attach rate at 22%.",
        "key_risk": "OpenAI partnership concentration risk — any GPT quality degradation affects Copilot retention.",
        "confidence": 0.79,
        "signal_type": "FUNDAMENTAL_SHIFT",
        "validation_score": "4/4 claims verified",
        "supply_chain_impact": [
            {"ticker": "NVDA", "direction": "▲", "reason": "Azure GPU cluster expansion drives H100/H200 demand"},
            {"ticker": "ANET", "direction": "▲", "reason": "Azure datacenter networking expansion confirmed in capex"},
        ],
        "sources": [
            {"url": "https://www.microsoft.com/en-us/investor/earnings/FY-2026-Q3/", "title": "MSFT Q3 FY2026 Earnings", "domain": "microsoft.com"},
        ],
        "numerical_claims": [
            {"claim": "Azure AI revenue +65% YoY", "verified": True, "source": "earnings call Q3 FY2026"},
            {"claim": "M365 Copilot attach rate 22%", "verified": True, "source": "earnings call Q3 FY2026"},
            {"claim": "Capex $18B guided Q4 FY2026", "verified": True, "source": "CFO commentary"},
            {"claim": "Azure market share now 23%", "verified": True, "source": "Synergy Research Q1 2026"},
        ],
        "sector_context": {"sector": "cloud_infrastructure", "peers": ["AMZN", "GOOG", "ORCL"]},
        "raw_pipeline_state": None,
        "created_at": _dt(days=1),
        "status": "active",
        "user_email": SEED_USER,
    },
    {
        "ticker": "0700.HK",
        "run_id": _RUN_IDS[4],
        "signal": "BEARISH",
        "conviction": 3,
        "one_line": "Q1 revenue miss + gaming licence delay = near-term headwind.",
        "key_catalyst": "Tencent Q1 2026 revenue -8% vs consensus on gaming licensing delay.",
        "key_risk": "Regulatory normalisation — MIIT gaming approvals resuming could reverse this signal quickly.",
        "confidence": 0.68,
        "signal_type": "FUNDAMENTAL_SHIFT",
        "validation_score": "2/3 claims verified",
        "supply_chain_impact": [
            {"ticker": "9988.HK", "direction": "▼", "reason": "Alibaba ad revenue correlated with Tencent consumer sentiment"},
        ],
        "sources": [
            {"url": "https://www.tencent.com/en-us/investors.html", "title": "Tencent Q1 2026 Results", "domain": "tencent.com"},
        ],
        "numerical_claims": [
            {"claim": "Q1 2026 revenue CNY155B (-8% vs CNY168B consensus)", "verified": True, "source": "earnings release"},
            {"claim": "Gaming MAU declined 3% QoQ", "verified": True, "source": "earnings release"},
            {"claim": "WeChat MAU 1.42B", "verified": False, "source": "analyst estimate — official figure not yet released"},
        ],
        "sector_context": {"sector": "consumer_tech", "peers": ["9988.HK", "9618.HK", "BIDU"]},
        "raw_pipeline_state": None,
        "created_at": _dt(hours=6),
        "status": "active",
        "user_email": SEED_USER,
    },
]

_REPORTS_DATA = [
    {
        "sector_id": "semiconductors",
        "sector_name": "AI Semiconductors & Compute",
        "created_at": _dt(days=4, hours=2),
        "status": "active",
        "analysis": (
            "## Semiconductor Sector — Week of 26 April 2026\n\n"
            "The semiconductor sector is experiencing a bifurcation. "
            "NVDA remains the primary beneficiary of the AI capex cycle, "
            "with H200 backorders confirmed through Q3 2026. The key upstream "
            "read-through is TSMC's CoWoS capacity expansion — packaging has "
            "been the binding constraint, and its removal is structurally "
            "bullish for the entire compute supply chain.\n\n"
            "ASML continues to book record EUV orders. The leading-edge "
            "duopoly (TSMC + Samsung) is expanding at a rate that justifies "
            "current ASML valuation multiples. AMD's MI300X server GPU ramp "
            "is proceeding but remains a secondary narrative to H200 demand.\n\n"
            "**Key risk:** US export control escalation remains the sector's "
            "single largest binary risk event. Any new restriction targeting "
            "HBM or CoWoS supply chains would reprice the sector within hours."
        ),
        "validation": "3/4 numerical claims verified against SEC and IR sources.",
        "news_summary": "NVDA earnings beat; TSMC CoWoS expansion; ASML record bookings.",
        "confidence_score": 0.78,
        "validation_status": "partial",
        "data_sufficiency": "sufficient",
        "news_used": 12,
        "prices_snapshot": {"NVDA": 892.40, "TSM": 178.25, "ASML": 841.60},
        "technicals_snapshot": {"NVDA": {"rsi": 62, "macd_signal": "bullish"}, "TSM": {"rsi": 55, "macd_signal": "neutral"}},
        "news_snapshot": None,
        "filings_snapshot": None,
        "timing_snapshot": {"fetch_s": 18.2, "analyze_s": 94.1, "validate_s": 41.3, "total_s": 183.4},
        "pipeline_state": None,
        "user_email": SEED_USER,
    },
    {
        "sector_id": "cloud_infrastructure",
        "sector_name": "Cloud Infrastructure & DevOps",
        "created_at": _dt(days=3, hours=1),
        "status": "active",
        "analysis": (
            "## Cloud Infrastructure — Week of 27 April 2026\n\n"
            "Microsoft Azure AI services are inflecting. The Copilot M365 "
            "attach rate of 22% represents genuine monetisation rather than "
            "trial usage — this is the metric the market has been waiting for.\n\n"
            "AWS re:Invent product cadence remains strong but margin compression "
            "from GPU infrastructure costs is becoming visible. Google Cloud "
            "continues to narrow the gap on AI workloads, driven by TPU v6 "
            "availability and Gemini integration.\n\n"
            "**Watchlist:** Oracle's OCI is the dark horse — Elon Musk's Grok "
            "infrastructure deal represents a meaningful data point about "
            "enterprise willingness to consider OCI as a credible hyperscaler alternative."
        ),
        "validation": "4/4 numerical claims verified.",
        "news_summary": "MSFT Copilot monetisation; AWS margin watch; GOOG TPU v6 launch.",
        "confidence_score": 0.81,
        "validation_status": "verified",
        "data_sufficiency": "sufficient",
        "news_used": 9,
        "prices_snapshot": {"MSFT": 423.15, "AMZN": 198.70, "GOOG": 174.40},
        "technicals_snapshot": {"MSFT": {"rsi": 64, "macd_signal": "bullish"}},
        "news_snapshot": None,
        "filings_snapshot": None,
        "timing_snapshot": {"fetch_s": 14.8, "analyze_s": 88.5, "validate_s": 36.1, "total_s": 162.2},
        "pipeline_state": None,
        "user_email": SEED_USER,
    },
    {
        "sector_id": "ev_battery",
        "sector_name": "EV & Battery Technology",
        "created_at": _dt(days=2, hours=3),
        "status": "active",
        "analysis": (
            "## EV & Battery — Week of 28 April 2026\n\n"
            "BYD's March delivery figures confirmed it as the world's largest "
            "EV manufacturer by volume for the third consecutive quarter. "
            "The LFP chemistry advantage — lower cost, longer cycle life — "
            "is structurally favourable in the price-sensitive mass market.\n\n"
            "Tesla's Q1 2026 delivery miss (386k vs 420k consensus) is partly "
            "explained by Model Y transition timing, but the market is pricing "
            "in a more serious demand concern. Cybertruck returns to positive "
            "territory in owner satisfaction surveys — a lagging indicator "
            "that may support resale value stabilisation.\n\n"
            "CATL's solid-state battery timeline (2027 pilot, 2029 mass "
            "production) remains the most significant long-term variable in "
            "the sector. Any acceleration of this timeline would reprice "
            "the entire EV supply chain."
        ),
        "validation": "2/3 claims verified. One delivery figure disputed across sources.",
        "news_summary": "BYD volume record; Tesla delivery miss; CATL solid-state update.",
        "confidence_score": 0.64,
        "validation_status": "partial",
        "data_sufficiency": "sufficient",
        "news_used": 11,
        "prices_snapshot": {"TSLA": 248.30, "NIO": 4.82, "RIVN": 11.40},
        "technicals_snapshot": {"TSLA": {"rsi": 44, "macd_signal": "bearish"}},
        "news_snapshot": None,
        "filings_snapshot": None,
        "timing_snapshot": {"fetch_s": 16.1, "analyze_s": 91.3, "validate_s": 44.7, "total_s": 176.8},
        "pipeline_state": None,
        "user_email": SEED_USER,
    },
    {
        "sector_id": "fintech",
        "sector_name": "Fintech & Digital Payments",
        "created_at": _dt(days=1, hours=4),
        "status": "active",
        "analysis": (
            "## Fintech — Week of 29 April 2026\n\n"
            "Stripe's rumoured IPO filing (H2 2026) is the sector's dominant "
            "near-term catalyst. The embedded finance buildout — Stripe Treasury, "
            "Stripe Capital, Issuing — is mature enough to command a payments "
            "terminal multiple rather than a pure SaaS multiple.\n\n"
            "Visa and Mastercard continue to benefit from travel normalisation "
            "and cross-border volume recovery. The macro tailwind is durable "
            "as long as consumer spending holds. Block (SQ) is the most "
            "interesting re-rating candidate — Cash App MAUs are growing "
            "faster than consensus modelled, and BNPL integration is driving "
            "spend per active user.\n\n"
            "**Risk:** Central bank digital currency (CBDC) development in "
            "the EU and China creates a long-dated headwind for the incumbent "
            "payments rails. The timeline is 3–5 years, not immediate."
        ),
        "validation": "3/3 claims verified.",
        "news_summary": "Stripe IPO signals; Visa cross-border recovery; Block MAU growth.",
        "confidence_score": 0.73,
        "validation_status": "verified",
        "data_sufficiency": "sufficient",
        "news_used": 8,
        "prices_snapshot": {"V": 314.20, "MA": 488.50, "SQ": 68.15},
        "technicals_snapshot": {"V": {"rsi": 58, "macd_signal": "neutral"}},
        "news_snapshot": None,
        "filings_snapshot": None,
        "timing_snapshot": {"fetch_s": 12.4, "analyze_s": 79.8, "validate_s": 31.2, "total_s": 145.1},
        "pipeline_state": None,
        "user_email": SEED_USER,
    },
    {
        "sector_id": "biotech",
        "sector_name": "Biotech & Drug Discovery",
        "created_at": _dt(hours=8),
        "status": "active",
        "analysis": (
            "## Biotech — Week of 30 April 2026\n\n"
            "GLP-1 agonist expansion continues to be the dominant investment "
            "theme. Novo Nordisk and Eli Lilly are both guiding to cardiovascular "
            "indication approvals that expand the addressable market well beyond "
            "obesity. The supply chain constraint (API manufacturing capacity) "
            "is easing as new facilities come online in 2026.\n\n"
            "CRISPR Therapeutics' Casgevy commercial launch data is showing "
            "strong durability at 24 months — if the 36-month data (due Q3 2026) "
            "confirms this, it represents a significant catalyst for the "
            "gene-editing sector.\n\n"
            "AI drug discovery companies (Recursion, Insilico) are delivering "
            "first clinical candidates. The sector is 18–24 months from knowing "
            "whether AI-designed molecules perform better than traditional "
            "small-molecule discovery."
        ),
        "validation": "2/4 claims verified. GLP-1 market size figures vary widely across analyst reports.",
        "news_summary": "GLP-1 cardiovascular approvals; CRISPR durability data; AI drug discovery milestones.",
        "confidence_score": 0.61,
        "validation_status": "partial",
        "data_sufficiency": "sufficient",
        "news_used": 14,
        "prices_snapshot": {"NVO": 112.40, "LLY": 862.30, "CRSP": 43.80},
        "technicals_snapshot": {"NVO": {"rsi": 48, "macd_signal": "neutral"}},
        "news_snapshot": None,
        "filings_snapshot": None,
        "timing_snapshot": {"fetch_s": 19.3, "analyze_s": 102.4, "validate_s": 48.9, "total_s": 198.7},
        "pipeline_state": None,
        "user_email": SEED_USER,
    },
]


# ── Main seeding function ──────────────────────────────────────────

async def seed() -> None:
    engine = create_async_engine(settings.database_url, echo=False)

    async with engine.begin() as conn:
        # ── Wipe existing seed data ────────────────────────────────
        log.info("Clearing existing seed data for %s …", SEED_USER)
        await conn.execute(
            delete(signal_cards).where(signal_cards.c.user_email == SEED_USER)
        )
        await conn.execute(
            delete(pipeline_runs).where(pipeline_runs.c.user_email == SEED_USER)
        )
        await conn.execute(
            delete(reports).where(reports.c.user_email == SEED_USER)
        )

        # ── Insert signal_cards, collect returned IDs ──────────────
        log.info("Inserting %d signal cards …", len(_SIGNAL_CARDS_DATA))
        sc_result = await conn.execute(
            insert(signal_cards).returning(signal_cards.c.id, signal_cards.c.run_id),
            _SIGNAL_CARDS_DATA,
        )
        sc_id_map: dict[str, int] = {row.run_id: row.id for row in sc_result}

        # ── Insert pipeline_runs linked to signal_cards ────────────
        log.info("Inserting %d pipeline runs …", len(_RUN_IDS))
        _run_rows = [
            {
                "run_id": _RUN_IDS[i],
                "ticker": _SIGNAL_CARDS_DATA[i]["ticker"],
                "sector_id": _SIGNAL_CARDS_DATA[i]["sector_context"]["sector"],  # type: ignore[index]
                "status": "completed",
                "created_at": _SIGNAL_CARDS_DATA[i]["created_at"],
                "started_at": _SIGNAL_CARDS_DATA[i]["created_at"],
                "finished_at": _SIGNAL_CARDS_DATA[i]["created_at"],
                "signal_card_id": sc_id_map.get(_RUN_IDS[i]),
                "node_executions": [
                    {"node_name": "fetch",     "status": "completed"},
                    {"node_name": "summarize", "status": "completed"},
                    {"node_name": "analyze",   "status": "completed"},
                    {"node_name": "validate",  "status": "completed"},
                    {"node_name": "save",      "status": "completed"},
                ],
                "user_email": SEED_USER,
            }
            for i in range(5)
        ]
        await conn.execute(insert(pipeline_runs), _run_rows)

        # ── Insert reports ─────────────────────────────────────────
        log.info("Inserting %d reports …", len(_REPORTS_DATA))
        await conn.execute(insert(reports), _REPORTS_DATA)

    await engine.dispose()
    log.info("✓ Seed complete — %d signal cards, %d runs, %d reports for %s",
             len(_SIGNAL_CARDS_DATA), len(_RUN_IDS), len(_REPORTS_DATA), SEED_USER)


if __name__ == "__main__":
    asyncio.run(seed())
