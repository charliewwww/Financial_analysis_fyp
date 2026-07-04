# MarketPulse — Master Plan

> **Status:** Living document · **Last updated:** 2026-05-31
> **Owner:** Wong Tsz Hei Charlie (57141182)
> **One-liner:** A fast, real-data market-intelligence platform that tells a retail investor *"is this news real or noise — and what should I do?"*, backed by transparent, validated reasoning and second-order supply-chain insight.

> ℹ️ **Naming note:** The official product name is **MarketPulse**. The app UI, FastAPI backend, agents, and frontend branding now say *MarketPulse*. A few residual *"Alpha Lens"* / *"Supply Chain Alpha"* strings remain in code comments, CLI banners, and the legacy Streamlit stack — see [Action Items](#7-action-items) item 3.

> This master doc replaces the following legacy files (their useful content is merged here):
> `IMPROVEMENT_PLAN.md`, `PRODUCT_ROADMAP.md`, `MIGRATION_STATUS.md`, `PLATFORM_AUDIT_SUMMARY_2026-05-06.md`, `ACTION_ITEMS.md`.
> Companion docs that remain: `README.md` (quick start), `ARCHITECTURE_DIAGRAM.md` (deployment diagrams), `UX_FINDINGS.md` (UX backlog), `FYP_IMPLEMENTATION_PLAN.md` (academic record), `frontend/FRONTEND_OVERVIEW.md`, `backend/BACKEND_OVERVIEW.md`.

---

## Table of Contents
1. [What MarketPulse Is](#1-what-marketpulse-is)
2. [The Real Problem We Solve](#2-the-real-problem-we-solve)
3. [Why This (vs ChatGPT / FinGPT / FinRobot)](#3-why-this-vs-chatgpt--fingpt--finrobot)
4. [The Product Experience (Four Modes)](#4-the-product-experience-four-modes)
5. [Current State — The Honest Version](#5-current-state--the-honest-version)
6. [Roadmap](#6-roadmap)
7. [Action Items](#7-action-items)
8. [Feature Backlog — the "Rich Toolbox"](#8-feature-backlog--the-rich-toolbox)
9. [Tech Stack & Layout](#9-tech-stack--layout)

---

## 1. What MarketPulse Is

A market-intelligence platform for the modern retail/solo investor. It is **not** a report generator and **not** a portfolio tracker. Its central question is: *"What is the market telling me, and is it real?"*

Core philosophy (Bloomberg-for-students): **data first, signal second, context on demand.** Every output is a structured, validated **signal card** — direction, conviction, the key catalyst, the key risk, and the supply-chain ripple — not a 2000-word essay.

**Differentiator:** second-order supply-chain reasoning ("AI boom → more inference → higher energy demand → benefits 24/7 power providers"), plus a transparent validation layer that shows *which claims were verified*.

---

## 2. The Real Problem We Solve

> *"I see news, I think whether it is just media shaping the narrative or really a buy/sell time. Then I rely on my own analysis on the graph with basic AI analysis."*

Every investor faces the same daily problem:
- Hundreds of headlines, most of them noise.
- No fast way to tell **media narrative** from **genuine fundamental signal**.
- Chart reading is manual and slow.
- ChatGPT has no live data and you must frame the question yourself.

**The market gap is not a smarter report generator. It is a credible, fast, real-data signal engine that tells you what matters and proves it is right over time.**

---

## 3. Why This (vs ChatGPT / FinGPT / FinRobot)

> *(Trimmed from the academic FYP plan — full version lives in `FYP_IMPLEMENTATION_PLAN.md`.)*

Five gaps no existing tool covers simultaneously:

1. **Second-order supply-chain reasoning** — multi-hop causal chains, not first-order "Nvidia news → Nvidia up."
2. **Event-driven anomaly explanation** — when a stock moves ±5% with no obvious news, auto-trigger a deep RAG explanation.
3. **Self-correcting anti-hallucination pipeline** — source grounding → RAG validation → numerical cross-check → self-correction → confidence scoring.
4. **Runs fully local & free** — GLM-4.7-Flash via Ollama in production (DeepSeek-V4-Flash via OpenRouter for dev). ~$0/month.
5. **Structured, auditable output** — every signal is a verifiable, benchmarkable record.

| Dimension | FinGPT | FinRobot | FinRL | **MarketPulse** |
|---|---|---|---|---|
| Multi-agent workflow | ❌ | ✅ | ❌ | ✅ |
| Second-order reasoning | ❌ | ❌ | ❌ | ✅ |
| Anomaly-triggered analysis | ❌ | ❌ | ❌ | ✅ |
| Anti-hallucination validation | ❌ | ❌ | N/A | ✅ |
| Runs fully local (free) | ❌ | ❌ | ✅ | ✅ |
| Explainable + auditable | ❌ | Partial | ❌ | ✅ |
| Supply-chain reasoning | ❌ | ❌ | ❌ | ✅ |

---

## 4. The Product Experience (Four Modes)

The target experience is one coherent product built around four user moments:

1. **Morning Brief** — a watchlist of structured signal cards (direction, conviction, validation score, signal type, supply-chain ripple). Scan in two minutes; substance is the interface, not price tickers.
2. **Board of Analysts** — four built-in agents (Value, Momentum, Supply Chain, Risk) each run the full pipeline on a ticker; the UI shows their agreement/dissent as a structured debate.
3. **Chat Desk** — ask any agent directly; it answers with cited filings and can revise its view or produce a formal signal card on request.
4. **Agent Builder (Premium)** — users write a Markdown "skill" to create a custom analyst; the agent then accumulates its own verified track record over time.

**Commercial framing (for the demo, no billing needed):** Free tier = 4 built-in agents, limited analyses, read-only cards. Paid tier = unlimited analyses, custom agents, skill editor, Supply Chain Explorer, full track record.

---

## 5. Current State — The Honest Version

> Graded against the bar: *a product real retail investors would trust and I'd launch.*

### What genuinely works
- FastAPI + Next.js 16 + PostgreSQL/ChromaDB platform; large passing test suites (backend/root/frontend — frontend at 135 tests).
- LangGraph pipeline: `fetch → summarize → reflect → analyze → validate → score → save`, with retry controls now correctly propagated and **failed validation now blocks publication**.
- Real data sources: Yahoo Finance, multi-feed RSS, SEC EDGAR, FRED macro, locally-computed technicals.
- Numerical validator cross-checks claims against real data (>5% tolerance flags).
- **RAG is wired end-to-end** — the `ingest_vectordb` and `rag_query` nodes write and read ChromaDB; retrieved context (news + filings + the desk's own prior analyses) is injected into the analyze prompt, and `rag_metadata` is persisted and surfaced on the signal-detail page ("Historical context").
- Live SSE pipeline streaming (admin), user-scoped data via Cloudflare Access identity.
- A polished design system and a genuinely strong **Supply Map** visualization.
- **Trust/UX hardening shipped (2026-05-31):** "not financial advice" disclaimers (global footer + on the verdict panel), a global error boundary + request-timeout with calm error copy, a Decision Desk cold-start guide (one-click first run), a persistent low-sample caveat on the accuracy page, honest framing of the Supply Map (uniform nodes — no fake weighting), a mobile card-stack for the report table, plain-language jargon tooltips, and two adversarial eval cases guarding against overconfidence on missing data.
- **Credibility + reliability shipped (2026-06-01):** rule-based **signal-type classification** (`FUNDAMENTAL_SHIFT`/`MEDIA_NARRATIVE`/`TECHNICAL_ONLY`) persisted and surfaced honestly; **"conviction not stated"** propagated end-to-end (no fabricated certainty); out-of-coverage ticker notice; non-color a11y cues on price changes; and **pipeline reliability hardening** — a per-user concurrency cap (HTTP 429 before queuing) plus a bounded, drop-oldest SSE event queue with orphan reaping.

### What is broken, fake, or missing (the brutal list)
- **No real auth.** Cloudflare-header identity + `AUTH_BYPASS_EMAIL` dev bypass. Cannot onboard a second real user today. Production auth-mode footgun if `APP_ENV` is misconfigured.
- **Supply chain is hardcoded** to ~10 AI/semiconductor names (`config/supply_chain_data.py`). Off-script tickers silently under-deliver. → "An AI that only reasons about what you told it is a lookup table."
- **Demo/fallback mock content removed/verified clean** — the product surfaces (landing demo card, analyst gallery, accuracy preview) now fetch real API data with explicit empty/error states; no `DEMO_SIGNALS`/`FALLBACK_AGENTS` fabricated content remains. (The quick-pick ticker chips keep a clearly-labelled offline fallback list only.)
- **Output still largely freeform** with extraction heuristics — Phase 1 structured-JSON hardening pending.
- **Evals are still thin** — golden-path cases plus two new adversarial cases; not yet enough to defend a headline accuracy claim.
- **No backtester / proof of edge** yet.
- **Two parallel codebases** — legacy Streamlit/CLI (`app.py`, `ui/`, `main.py`) still present alongside the FastAPI+Next.js stack, and still carry old "Supply Chain Alpha" naming.
- ~~No run-rate limiting on pipeline endpoints; worker-pool saturation risk under fanout.~~ **Done (2026-06-01)** — per-user pending+running cap returns HTTP 429 before queuing, and the SSE queue is now bounded (drop-oldest) with orphan reaping. Distributed/IP-level limiting still pending for multi-instance deploys.

### Readiness
- Internal use: **High** · Private beta: **Medium** · Public launch: **Medium-Low** until trust + auth + hardening are done.

### UX problems
Tracked in detail (severity + UX-damage ratings, fix order) in **`UX_FINDINGS.md`**. Fix UX Tier 1–2 before adding new tools.

---

## 6. Roadmap

Ordered by **user value delivered, not technical complexity**: foundation → credibility → differentiation → proof.

### Phase 0 — Trust & Polish (UX-first) — *in progress*
From `UX_FINDINGS.md`. **Shipped (2026-05-31):** "not financial advice" disclaimers (footer + verdict panel), global error boundary + request timeout, Decision Desk cold-start guide, accuracy low-sample caveat, honest Supply Map framing, mobile card-stack for the report table, jargon tooltips. **Shipped (2026-06-01):** removed dead controls (`saved_sectors` theater card; mobile nav parity), verified product surfaces are mock-free with honest empty/error states, non-color a11y cues on price changes (and filter `aria-label`s). **Still open:** add "data as of" freshness timestamps everywhere, and finish consistent empty/error states on the remaining secondary pages.

### Phase 1 — Core Signal Engine
**Goal: the most credible, thorough per-ticker analysis (quality over speed).**
- Replace sector pipeline with **per-ticker** pipeline (sector data stays as *input* context; output is one ticker card).
- **Structured JSON output** (signal/conviction/catalyst/risk/sources/numerical_claims) — replaces essays; makes validation trivial.
- **HK/China stock support** (`0700.HK` etc.; SCMP/HKEX feeds; UTC+8 hours).
- **Move validation upstream** — validate each JSON field, annotate `verified:false`, no full-analysis retries; show `validation_score` prominently.

### Phase 2 — Credibility Layer
- ~~**Signal-type classification:** `FUNDAMENTAL_SHIFT` / `MEDIA_NARRATIVE` / `TECHNICAL_ONLY` (rule-based).~~ **Shipped (2026-06-01)** — classifier + tests; persisted on the signal card and surfaced in the UI with a plain-language label.
- **Supply-chain auto-discovery agent:** extract supplier/customer relations from 10-Ks into a `supply_chain_relationships` graph; surface ripple alerts. Replaces the hardcoded config.
- **Simple backtester:** store signal + price; after 5 trading days compute directional accuracy; rolling 30-day track record per ticker / signal type.

### Phase 3 — Skill-Based Agent Builder (Premium)
- Four built-in agents (Value, Momentum, Supply Chain, Risk).
- No-code **skill editor**; agents accumulate a self-evolving `PREDICTION_SKILL.md` from their own verified outcomes.

### Phase 4 — Academic Validation & Commercial Narrative
- Backtest-based evaluation, broader eval datasets (failure/adversarial cases), P&L-vs-benchmark chart, commercial pitch.

### Cross-cutting hardening
- Real authentication; production startup guardrails; ~~per-user run caps + rate limiting~~ (**done 2026-06-01**) + queue visibility; delete legacy Streamlit/CLI; keep frontend/backend API types in strict sync (contract tests).

---

## 7. Action Items

| # | Task | Priority | Status |
|---|---|---|---|
| 1 | UX Phase 0 trust quick-wins (disclaimers, timestamps, remove mock data, dev indicator, dead controls) | High | ◧ In progress — disclaimers/error-states/mobile/dead-controls/mock-data-verification/a11y cues done; "data as of" timestamps pending |
| 2 | Critical/important-news filter feature | High | ☐ |
| 3 | Rename app UI + codebase from "Alpha Lens" → **MarketPulse** | Medium | ◧ Mostly done — app UI, API, agents, frontend renamed; residual strings in legacy CLI/Streamlit + comments |
| 4 | Real mobile navigation + responsive Decision Desk | High | ◧ Mobile nav + report card-stack shipped; TickerBoard responsive pass still pending |
| 5 | Phase 1 structured-JSON output + upstream validation | High | ☐ |
| 6 | Supply-chain auto-discovery (replace hardcoded config) | Medium | ☐ |
| 7 | Simple backtester + track-record page | Medium | ☐ |
| 8 | Skill auto-generation from conversations | Low (defer) | ☐ |
| 9 | Real auth (replace Cloudflare-header bypass) | High (pre-launch) | ☐ |
| 10 | Delete legacy Streamlit/CLI stack | Low | ☐ |
| 11 | Architecture diagram slide for presentation | Low | ☐ |

> Completed historically: Streamlit→Next.js+FastAPI migration; chat functionality; MD→JSON data format; multi-tenancy & user profiles; failed-validation publication gate; **RAG wired end-to-end (ingest + retrieval + prompt injection)**; **trust/UX hardening batch (disclaimers, error boundary, cold-start guide, mobile card-stack, adversarial evals)**; **signal-type classification + "conviction not stated" honesty + a11y cues (2026-06-01)**; **pipeline reliability: per-user run cap (429) + bounded SSE queue with orphan reaping (2026-06-01)**.

---

## 8. Feature Backlog — the "Rich Toolbox"

Goal: users should feel *"this gives me so many great tools — I gain a lot here"* — **without** the product feeling unfinished. Rule: each new tool ships only on top of a trustworthy base (Phase 0 + Phase 1 first).

Candidate tools (to be prioritized, not all committed):
- **Critical-news filter** — surface only market-moving news per ticker (high value, plays to existing RSS+LLM strength).
- **Watchlist + weekly "what changed" digest.**
- **Backtest / P&L-vs-benchmark chart** — proves edge, builds trust.
- **Compare two tickers / sector heatmap.**
- **Saved views & alerts.**
- **Anomaly explainer** — auto-explain unexplained ±5% moves.
- **Interactive Supply Map** — click a node → drill into affected tickers/signals.

---

## 9. Tech Stack & Layout

| Layer | Technology |
|---|---|
| Frontend | Next.js 16 (App Router), TanStack Query v5, Tailwind CSS, shadcn/ui |
| Backend API | FastAPI 0.115, Pydantic v2, SQLAlchemy Core (async) |
| Database | PostgreSQL (prod) · SQLite (dev/tests) |
| Vector store | ChromaDB (RAG context — *active: ingested and injected into the analyze node*) |
| LLM | GLM-4.7-Flash via Ollama (local/prod) · DeepSeek-V4-Flash via OpenRouter (dev) |
| Auth | Cloudflare Access header *(real auth pending)* |
| Orchestration | LangGraph nodes (`workflows/`) |
| Observability | Langfuse (optional) |

```
backend/        FastAPI app, SQLAlchemy tables, repositories, routes, tests
frontend/       Next.js 16 app, TanStack Query hooks, Vitest tests
agents/         LLM agents (analyst, validator, llm_client)
workflows/      LangGraph pipeline nodes
data_sources/   Live connectors (Yahoo Finance, SEC EDGAR, FRED, RSS, technicals)
evals/          Scoring, LLM-judge, metrics, runner
config/         Settings, sectors, supply_chain_data (hardcoded — to be replaced)
database/       Legacy SQLite reports DB
ui/, app.py, main.py   Legacy Streamlit/CLI (scheduled for deletion)
```
