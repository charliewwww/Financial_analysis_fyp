# MarketPulse — Product Roadmap
### Building a Market Intelligence Platform for the Modern Investor

*Version 1.1 — April 2026 (historical)*

> ℹ️ **Superseded:** This roadmap is kept as a historical record. The canonical,
> up-to-date plan and honest current-state assessment now live in
> [MASTER_PLAN.md](MASTER_PLAN.md). The product was previously named *"Supply Chain Alpha"* / *"Alpha Lens"*; the official name is now **MarketPulse**.

---

## Build Status

| Milestone | Status | Notes |
|---|---|---|
| Platform foundation (FastAPI + Next.js + PostgreSQL) | ✅ Complete | 117 backend / 69 frontend tests passing |
| Multi-tenancy & user profiles | ✅ Complete | See Part 0 below |
| Phase 1 — Core Signal Engine | 🔲 Next | Structured JSON output, validation loop fix |
| Phase 2 — Credibility Layer | 🔲 Planned | Signal type classification, backtester |
| Phase 3 — Skill-Based Agent Builder | 🔲 Planned | Skill editor, four built-in agents |
| Phase 4 — Academic Validation | 🔲 Planned | Backtest evaluation, commercial pitch |

---

## Part 0: Multi-Tenancy & User Profiles — Completed April 2026

Before Phase 1 work begins, the platform needed proper user identity and data isolation.
Authentication is provided by Cloudflare Access — every request arrives with a
`Cf-Access-Authenticated-User-Email` header that the backend extracts as the canonical user identity.

### What was built

**Backend (`backend/`)**

- `backend/app/core/auth.py` — `get_current_user` FastAPI dependency. Reads the Cloudflare header,
  raises HTTP 401 if absent. Local dev bypass via `AUTH_BYPASS_EMAIL` setting.
- `backend/app/db/tables.py` — `user_email TEXT` column added to `signal_cards`, `pipeline_runs`,
  `reports`, `watchlist`, `annotations`. New `user_details` table: `email`, `username`,
  `saved_sectors` (JSONB), `preferences` (JSONB), timestamps.
- `backend/app/db/repositories/` — all list/get methods now accept `user_email` and filter:
  `(user_email = $1 OR user_email IS NULL)`. New rows always carry the owner's email.
  Legacy rows (`user_email IS NULL`) remain visible to all users.
- `backend/app/db/repositories/users.py` — `get_or_create` (auto-provisions profile on first login),
  `update_profile` (partial PATCH).
- `backend/app/schemas/users.py` — `UserDetailSchema` (response), `UserUpdateRequest` (PATCH body,
  `username` max 64 chars).
- `backend/app/api/routes/users.py` — `GET /api/v1/users/me`, `PATCH /api/v1/users/me`.
- All three existing routers (`signals`, `reports`, `pipeline`) inject `CurrentUser` via dependency.

**Frontend (`frontend/`)**

- `frontend/src/types/api.ts` — `UserDetail` and `UserUpdateRequest` interfaces.
- `frontend/src/lib/api.ts` — `fetchMe()` and `updateMe(body)` fetch wrappers.
- `frontend/src/app/profile/page.tsx` — Profile page: display-name editor, saved-sectors badge
  toggle grid (8 sectors), account info card with Cloudflare Access badge.
- Root layout: "Profile" nav link added.

**Tests** — 117 backend / 69 frontend, all passing.

---

## Part 1: Current State Assessment

Our production pipeline, as measured by operational logs, establishes the baseline we are designing from:

```
⏱  SECTOR TOTAL    383.3s        ← 6.4 minutes for ONE sector
⏱  analyze         92.7s + 96.3s ← LLM ran TWICE (retry loop triggered)
⏱  validate_reasoning 48.4s + 35.1s ← validator ran TWICE
Validation FAILED after 1 retries — scoring anyway  ← saved a failed report
Checked 23 claims: 2 verified, 5 discrepancies, 16 unchecked
```

Reading these numbers plainly:

- **6.4 minutes** to produce one sector report with no defined audience
- The LLM ran **4 times** on the same data due to a failed retry loop
- The Validation Loop **failed both times** — the anti-hallucination architecture is not functioning as designed
- Of 23 numerical claims, only **2 were verified**. 16 were never checked at all.
- The system **saved the failed report anyway**

The current design optimises for pipeline complexity rather than user value. The output is a 2000-word Markdown file that costs 6 minutes and 4 LLM calls to produce, fails its own quality check, and delivers no actionable insight.

This is not a reason to abandon the architecture. It is the data we need to make the right design decisions going forward.

---

## Part 2: The Real Problem We Are Solving

User research surfaces a consistent pattern in how retail investors process a news-heavy morning:

> "I see news, I think whether it is just media shaping the narrative or really a buy/sell time.
> Then I rely on my own analysis on the graph with basic AI analysis."

This is the product requirement in one sentence. Not "generate a 2000-word report."
The core user need is a single question: **"Is this real or noise, and what should I do?"**

Every investor, retail or professional, faces the same problem every day:
- Hundreds of news headlines, most of which are noise
- No fast way to tell if a headline is media narrative vs genuine fundamental signal
- Chart reading is manual and time-consuming
- Even with ChatGPT, you have to frame the question yourself, and it has no live data

**The gap in the market is not "a smarter report generator." The gap is a credible, fast, real-data signal engine that tells you what matters and proves it is right over time.**

That is what we are building.

---

## Part 3: Why the Current Architecture Cannot Get There

### Problem 1: Wrong Unit of Output

The current system thinks in **sectors**. The user thinks in **tickers**.

When you read that TSMC cut its guidance this morning, you do not think
"let me run the full semiconductor sector report." You think "what does this mean for NVDA?"

A product that requires you to run a 6-minute sector analysis to answer a one-ticker question
will never be used daily. Usage requires zero friction.

### Problem 2: Wrong Time Cadence

The system is designed for **weekly** runs. Markets move daily — sometimes hourly.
A weekly essay published on Sunday morning is already stale by Monday open.

If the goal is to help with buy/sell decisions, the output must be **daily at minimum**,
ideally available on-demand for any ticker at any time.

### Problem 3: The Validation Loop Architecture is Broken — But the Principle is Right

The logs show the loop ran twice, failed twice, and saved a failed result anyway.
That is not a reason to remove validation. It is a reason to fix where validation happens.

The root cause: you are trying to validate a 2000-word essay after the fact.
That is like trying to spell-check a speech after it has already been given.
The LLM had already embedded its hallucinations into flowing prose — there is nowhere
for the validator to grab hold.

The Validation Loop is one of the core values of this project. It stays.
But it moves upstream.

With structured JSON output, every field becomes a validatable assertion:
- `"signal": "BULLISH"` — is this consistent with the cited sources?
- `"numerical_claims[0].claim": "H200 ASP $35,000"` — does this match SEC/earnings data?
- `"sources[0]"` — does this URL actually exist and say what we claim?

Validation on structured fields is instant, precise, and cannot be "mostly failed."
A field is either verified or marked `"verified": false`. No retrying the entire analysis.
No silent saves of broken reports. The loop survives — it just operates on clean data.

### Problem 4: The Supply Chain Maps Are a Config File, Not AI

The signature differentiator of this project is supply chain reasoning.
But the current implementation stores supply chain relationships in
`config/supply_chain_data.py` as hardcoded Python dictionaries.

The LLM does not discover supply chains. You discovered them and put them in a file.
This means the system cannot reason about any company outside the 3 curated sectors,
and it cannot discover a new supply chain relationship that was not already known.

**An AI that can only reason about what you already told it is not AI. It is a lookup table.**

### Problem 5: No Feedback Loop, No Proof of Accuracy

The prediction tracking exists in the database schema, but there is no
backtesting, no accuracy dashboard, and no way to evaluate whether the system's
signals are better than random.

Without this, the product cannot defend its value proposition.
Any investor, stakeholder, or evaluator will ask: "How is this better than just asking ChatGPT?"
Without a measurable track record, that question has no data-backed answer.

---

## Part 4: Product Vision

### Commercial Direction: Subscription-Based, Public Audience

This product is not a personal tool or a student project demo.
The target is a subscription-based service accessible to the general investing public.

**Freemium model:**
- Free tier: access to 4 pre-built analyst agents, limited analyses per month,
  read-only signal cards, no custom skill creation, no skill evolution history
- Paid tier: unlimited analyses, custom agent creation, skill editor, skill evolution
  data, Supply Chain Explorer, API access, full prediction history and track record

This framing changes what gets built and in what order:
- The 4 built-in agents (Phase 3) are the free-tier product
- The skill editor (Phase 3) is the paid-tier differentiator
- The self-improving prediction loop (Phase 3.3) is the reason paid users stay
- The Supply Chain Explorer (Phase 2.5) is the premium exploration tool

For the FYP, you do not need to implement billing infrastructure.
You need to implement the feature split clearly enough that the business model is legible.
A working demo with "Free" and "Premium" modes is sufficient for academic and company presentation.

---

### The Core Concept: A Market Radar, Not a Report Factory

Think of Bloomberg Terminal for a student / solo investor.
Bloomberg does not give you essays. It gives you:
- A number (price)
- A direction (up/down and by how much)
- The top reason why
- A signal you can act on

We are not building Bloomberg. But we are adopting that philosophy:
**data first, signal second, context on demand.**

### The Experience We Are Building

MarketPulse is a market intelligence platform. The product's central question is not *how is my portfolio performing?* — it is *what is the market telling me, and is it real?*

The experience is structured around four distinct modes, each designed for a different kind of user moment.

---

#### The Morning Brief — Analyst Briefings, Not Price Tickers

The dashboard opens to a watchlist, but the primary content is not price movement. It is a structured briefing from the agent pipeline, run overnight for every ticker the user is tracking:

```
NVDA    ▲ BULLISH   Conviction: 4/5   Signal Type: FUNDAMENTAL_SHIFT
        Validation: 3/4 claims verified ✓
        ──────────────────────────────────────────────────────────
        Jensen confirmed H200 backorders through Q3 2026.
        Volume +2.1σ above 30-day average — institutional accumulation pattern.
        TSMC CoWoS capacity +40% removes packaging bottleneck.
        ──────────────────────────────────────────────────────────
        Supply chain ripple  →  TSM ▲   CEG ▲   ANET ▲

TSM     ◆ NEUTRAL   Conviction: 2/5   Signal Type: TECHNICAL_ONLY
        Guidance in line with prior quarter. No supply chain events.
        RSI 52 — no directional signal present.

0700.HK ▼ BEARISH   Conviction: 3/5   Signal Type: FUNDAMENTAL_SHIFT
        Tencent Q1 revenue −8% vs consensus. Regulatory risk resurfaces
        in gaming licensing segment. CNY macro headwind confirmed by PBOC data.
```

Users spend two minutes scanning. Conviction score, validation score, and signal classification are all visible before clicking into a card. The design forces transparency: a 4/5 conviction signal with only 1/4 claims verified reads very differently from a 3/5 signal with 4/4 verified. The analytical substance is the interface — not price movement.

---

#### The Board of Analysts — Four Perspectives on Every Ticker

Clicking any signal card opens a four-panel view. Each of the four built-in agents has independently run the full pipeline through its own analytical lens:

```
┌─────────────────────────────────────┬─────────────────────────────────────┐
│  VALUE ANALYST          ▲ BULLISH   │  MOMENTUM ANALYST       ▲ BULLISH   │
│  Conviction: 3/5                    │  Conviction: 4/5                    │
│                                     │                                     │
│  "At 28× forward earnings with      │  "Volume +2σ on RSI reset 45→62.   │
│   35% growth — fair value, room     │   Textbook accumulation phase.      │
│   to run if Q3 guidance holds."     │   Momentum confirms fundamentals." │
├─────────────────────────────────────┼─────────────────────────────────────┤
│  SUPPLY CHAIN ANALYST   ▲ BULLISH   │  RISK ANALYST           ◆ NEUTRAL   │
│  Conviction: 5/5                    │  Conviction: 2/5                    │
│                                     │                                     │
│  "TSMC CoWoS +40% is the            │  "China export controls remain      │
│   bottleneck removal NVDA has       │   unresolved. ~20% of addressable   │
│   been waiting for. H200            │   market at risk if policy          │
│   production ramp begins Q3."       │   escalates. Not priced in."       │
└─────────────────────────────────────┴─────────────────────────────────────┘
  Aggregated:  ▲ BULLISH   4/5   (3 of 4 analysts agree)
```

The user is not receiving a single opinion. They are receiving a structured debate between four specialist perspectives. The risk analyst's concern is surfaced even when the consensus is bullish — users can see the dissent and decide how to weight it. This is what a research desk looks like, not what a trading app looks like.

---

#### The Chat Desk — Asking Your Analyst Directly

At any point, users open a chat interface and address any agent directly. This is the mode that most clearly distinguishes the product from a dashboard:

```
You:  "What do you think about 0016.HK given the HKMA decision last week?"

HK Property Analyst:
  The March rate hold is marginally positive for mortgage volumes, but the
  more consequential data point is the Q1 land bank release — Sun Hung Kai's
  pipeline is 18 months thin. That pattern historically precedes a cycle of
  aggressive land acquisition at elevated prices, which compresses near-term
  margins even as longer-term supply tightens.

  Net view: NEUTRAL leaning BEARISH. Rental yield at 3.1% against the HK
  10-year bond at 4.2% — the spread has inverted. This condition preceded
  a 12–18 month correction in HK property equities in 4 of 5 historical
  instances since 2008.

  [Sources: HKMA Monthly Statistics Apr 2026 · HKEX Filing 0016.HK Q1 2026
   · RICS HK Property Index Q1 2026]

You:  "Is the yield inversion a leading or lagging signal here?"

HK Property Analyst:
  Coincident, not leading. The leading signal is land auction premiums — if
  government sales clear at more than 15% above reserve in the next two
  quarters, that is when speculative pressure is confirmed against a
  rate-constrained buyer pool.
```

The agent cites real filings and holds a point of view formed by its skill set. It handles follow-up questions, can revise its position given new information introduced in the conversation, and produces a formal signal card on request. Users are not prompting a general AI — they are consulting a specialist who has read the relevant documents.

---

#### Building a New Analyst — The Skill Editor (Premium)

Paid users can create their own agents without writing a single line of code. The flow is intentionally minimal:

**Step 1 — Name the agent:** *"HK Property Analyst"*

**Step 2 — Write the skill** (a Markdown editor opens):

```markdown
# HK Property Sector Skill
## Focus
Analyse Hong Kong listed property developers (0016.HK, 0688.HK, 0101.HK).
Primary factors: land bank depth, rental yield vs mortgage rate spread, HKMA policy.

## Data Sources
- HKEX announcements and CCASS institutional flow data
- HKMA Monthly Statistics (mortgage approval volumes)
- RICS Hong Kong property index

## Reasoning Approach
HK property is equally rate-sensitive and regulatory-sensitive.
When HKMA raises rates OR the government announces new SSD/BSD measures,
weight BEARISH even if near-term fundamentals appear stable.
Land sale results are a 12–18 month leading indicator for developer margins.

## Output Emphasis
Always include: rental yield vs HK 10-year bond spread.
Flag immediately: any government land sale clearing outside expected range.
```

**Step 3 — The agent is live.** The HK Property Analyst appears in the user's agent roster alongside the four built-in agents. It inherits the platform's fixed identity layer (guardrails, compliance constraints, output format) and uses the user's skill document as its domain expertise. It accesses the same internal data sources — ChromaDB, HKEX filings, FRED macro, signal history — and starts generating signals immediately.

From its first prediction, the agent begins accumulating its own `PREDICTION_SKILL.md`. Over time, that document evolves from what the user wrote into what the agent has learned: which HKMA signals actually preceded price moves, which land sale data was noise, which regulatory announcements mattered more than the news cycle suggested. Those patterns are the product of the agent's own verified track record. The user wrote the methodology. The agent builds the evidence base.

This is not a chatbot with a custom system prompt. It is a specialist analyst that learns from its own outcomes.

---

These four modes — morning brief, board of analysts, chat desk, and agent builder — form a single coherent product experience. Each one reinforces the same idea: the value is not in the price data, it is in the reasoning. Everything in the technical plan exists to deliver that reasoning at the highest possible quality.

---

## Part 5: The Architecture We Are Moving Towards

### From Sector-Based to Ticker-Based

```
BEFORE:
User selects sector → fetch all 10 tickers → one big essay about all of them

AFTER:
User maintains a watchlist → per-ticker pipeline → per-ticker signal card
```

This is not just a UX change. It enables:
- Analysing any ticker, not just 3 hardcoded sectors
- HK/China stocks (yfinance supports XXXX.HK format)
- Running analysis on one ticker in 45 seconds instead of 6 minutes for a sector

### From Long Essay to Structured Signal

LLM output changes from:

```
BEFORE (current):
2000-word Markdown narrative with embedded claims,
mixed analysis and opinion, no clear verdict

AFTER (target):
{
  "ticker": "NVDA",
  "signal": "BULLISH",
  "conviction": 4,
  "one_line": "H200 backorder confirmation + volume spike = accumulation phase",
  "key_catalyst": "Jensen confirmed backorders through Q3 2026",
  "key_risk": "TSMC CoWoS yield issues could delay H200 production",
  "supply_chain_impact": ["TSM ▲", "CEG ▲ (power demand)", "ANET ▲ (datacenter networking)"],
  "sources": ["reuters.com/...", "cnbc.com/...", "sec.gov/..."],
  "numerical_claims": [
    {"claim": "H200 ASP $35,000", "verified": true, "source": "earnings call"},
    {"claim": "CoWoS capacity +40%", "verified": true, "source": "TSMC IR"}
  ],
  "signal_type": "FUNDAMENTAL_SHIFT",  // vs MEDIA_NARRATIVE vs TECHNICAL_ONLY
  "confidence": 0.78
}
```

This structure makes hallucination impossible to hide, makes validation trivial,
and makes the UI obvious. You cannot hallucinate a bullish/bearish enum.
You cannot hide a wrong number inside a structured verified field.

### From Hardcoded Supply Chains to Auto-Discovery

The supply chain maps in config are replaced by a **Supply Chain Discovery Agent**:

1. When a user adds a ticker to their watchlist, the agent fetches its latest 10-K
2. It extracts "Suppliers", "Customers", "Strategic Partners" from Risk Factors + Business section
3. It builds a dynamic graph of relationships — stored in the database, updated quarterly
4. When a supply chain event is detected (e.g., TSMC news), the system automatically
   checks who in the watchlist is upstream or downstream of TSMC

This is the feature that genuinely has no equivalent in ai-hedge-fund or FinRobot.
**It turns supply chain intelligence from a config file into a live AI capability.**

---

## Part 6: The Concrete Build Plan

### Philosophy Behind the Phases

The plan is ordered by **user value delivered, not technical complexity**.

Phase 1 delivers a functional core experience — something that can be used and demonstrated.
Phase 2 makes it credible and trustworthy.
Phase 3 delivers the platform differentiators that justify the subscription model.
Phase 4 locks in quantitative evidence of value and prepares the commercial narrative.

This ordering is deliberate: foundation before differentiation, utility before polish.
A sophisticated evaluation framework built on top of a broken product impresses no one.

---

### Phase 1 — Core Signal Engine (Weeks 1–3)
**Goal: The most credible, thorough analysis you can produce for a given ticker**

#### Design Principle: Quality Over Speed

The 383-second pipeline was slow for the wrong reason — it ran the LLM 4 times on the
same data, failed validation twice, and saved a broken report. That is not thoroughness.
That is waste.

The new pipeline is not designed to be fast. It is designed to be **right**. A deep
analysis that takes 5–10 minutes and produces a verified, evidence-grounded signal card
is worth far more than a 45-second guess. Speed is a nice-to-have — accuracy is the product.

The user chooses which ticker to analyse. The system takes the time it needs to do it properly.

#### 1.1 Hybrid Context Model: Sector Intelligence + Ticker-Level Output

This is the resolution to the tension between "sector context is valuable" and "I think in tickers":

**The problem with the old design** was not that it used sector context — it was that
it *output* at the sector level. One 2000-word essay about all 10 semiconductor companies
is not useful. But sector dynamics are essential context: you cannot understand why
NVDA is moving without understanding what TSMC, ASML, and SK Hynix are doing.

**The new design keeps sector context as input, but outputs per-ticker signal cards:**

```
Fetch layer:
  ├── Sector news (ecosystem dynamics — TSMC, ASML, macro)
  ├── Ticker-specific news (earnings, filings, analyst reports)
  └── SEC filings, FRED macro data, technical indicators — all fetched deeply

Context layer:
  └── LLM sees ALL data — sector context + ticker specifics + macro
       (quality of context = quality of output)

Output layer:
  └── One structured signal card for the target ticker
       → Signal, conviction, catalyst, risk, supply chain impact, all claims verified
```

This gives you the analytical depth of sector reasoning with the actionability of
a per-ticker output. Breadth of context, precision of output.

- Replace `weekly_analysis.py` with `ticker_pipeline.py`
- Input: target ticker + sector membership (which sector it belongs to)
- Fetch deeply: ticker news + sector news + SEC filings + technical indicators + macro
- The pipeline takes as long as it needs. There is no latency target. There is an accuracy target.

#### 1.2 Structured JSON Output
- Redesign the main LLM prompt to output structured JSON (signal, conviction, reasons, sources)
- Remove the long essay generation entirely from the primary pipeline
- Keep essay generation as an optional "deep dive" mode, not the default

The structural advantage: a 2000-word essay cannot be validated — every claim is embedded in prose
and can always be argued either way. A JSON field either matches its source or it does not.
Structured output is what makes the Validation Loop work as designed: instead of 16/23 claims
unchecked, every claim becomes a verifiable, annotated field.

#### 1.3 HK/China Stock Support
- yfinance handles HK tickers as-is (e.g., `0700.HK`, `9988.HK`, `2318.HK`)
- Add Hong Kong exchange trading hours awareness (UTC+8)
- Add HK-specific news sources (SCMP RSS, HKEX announcements feed)
- No new architecture needed — this is a config change + one extra RSS feed

HK stocks are a meaningful point of differentiation from every US-only competitor in the market.
They are also directly relevant to financial clients operating in the Asia-Pacific region —
a strategic consideration for any company building enterprise financial AI products.

#### 1.4 Restructure the Validation Loop — Upstream, Not Downstream

The Validation Loop is a core project value. It stays. But it moves.

**Current (broken):** LLM generates 2000-word essay → validator tries to check prose → fails → retry entire analysis → fail again → save anyway.

**New (correct):** LLM generates structured JSON → validator checks each field independently → any unverifiable field is marked `"verified": false` → pipeline continues, no full retry.

Concrete changes:
- Keep `numerical_validator.py` — it now validates specific JSON fields, not prose
- Keep the validation node in the LangGraph pipeline — it now returns a `validation_report` dict alongside the signal
- Remove the full analysis retry: if a claim cannot be verified, annotate it, do not rerun the LLM
- Add a `validation_score` field to the signal card: `"validation_score": "3/4 claims verified"`
- The UI shows this score prominently — users can see which signals are well-grounded

This is the validation loop working as designed. The key insight:
you cannot verify an essay, but you can verify a field.
`"claim": "CoWoS capacity +40%"` is either verifiable against TSMC IR or it is not.
There is no ambiguity, no retrying. The loop is fast, precise, and honest.

**Phase 1 Deliverable:** A ticker analysis interface where you select a ticker,
run the deep analysis pipeline, and receive a fully validated structured signal card.
Each card shows a validation score. The Validation Loop works correctly.
The analysis is thorough, not fast — and that is the point.

---

### Phase 2 — Credibility Layer (Weeks 4–6)
**Goal: Answers the question "why should I trust this over ChatGPT?"**

#### 2.1 Signal Type Classification
Every signal gets classified as one of three types:

- `FUNDAMENTAL_SHIFT` — backed by earnings, filings, or confirmed company action
- `MEDIA_NARRATIVE` — heavily covered news with no price action or filing confirmation
- `TECHNICAL_ONLY` — price/volume signal with no fundamental backing

This is your killer feature that no competitor has. It directly addresses the problem
you described: "is this media shaping the narrative or really a buy/sell time?"

The LLM does not decide this alone. It is determined by a rule:
- If claim is cited in SEC filing or earnings transcript → FUNDAMENTAL_SHIFT
- If claim appears in 3+ news sources but price action does not confirm → MEDIA_NARRATIVE
- If RSI/MACD/volume signals exist but no news → TECHNICAL_ONLY
- Mixed signals get a combined classification

#### 2.2 Supply Chain Auto-Discovery Agent
- New agent: `SupplyChainAgent` that processes 10-K filings to extract relationships
- Builds a graph: Supplier → Company → Customer for any ticker in your watchlist
- Stored in SQLite as `supply_chain_relationships` table (ticker, related_ticker, relationship_type, confidence, source_filing)
- When a ticker triggers a FUNDAMENTAL_SHIFT signal, automatically query the graph
  and surface "ripple effect" alerts for related tickers

This replaces the hardcoded `supply_chain_data.py` with live, AI-discovered relationships.
This is the moment "supply chain reasoning" becomes a real AI feature, not a config lookup.

#### 2.3 Simple Backtester
- Store every signal emitted with timestamp and price at time of signal
- After 5 trading days, look up actual price, compute: was the direction correct?
- Aggregate: rolling 30-day accuracy per ticker, per signal type
- Display on a "Track Record" dashboard page: 
  "Last 30 days: 65% directional accuracy on BULLISH signals, 58% on BEARISH"

A system with a measurable track record is a product. A system without one is a demo.
This is the only rigorous answer to "is this better than random?" — and showing
measurable improvement over time carries more weight than any architecture claim.
Even accuracy at 55–60% is compelling when it is honest, verifiable, and improving.

#### 2.4 Multi-Source Agreement Scoring
- Count how many independent sources confirm the key claim in each signal
- Display as: "3/5 sources confirm" next to each reason
- Downweight signals where only one source reports something
- This is your "media narrative detector" — if Bloomberg, Reuters, and price action
  all agree, it is probably real. If only one small site reports it, flag it as weak.

#### 2.5 User Insight Explorer — Give Users Tools to Find Insights Themselves

Right now the product tells users what to think. The next step is giving users
the tools to find insights themselves — the difference between a report and a terminal.

**Signal Filter Panel:**
- Filter watchlist by signal type: show me only `FUNDAMENTAL_SHIFT` signals today
- Filter by conviction: show me only signals with conviction ≥ 4/5
- Filter by validation score: show me only signals with ≥ 3/4 claims verified
- These filters let users apply their own judgement on top of the system's output

**Manual Annotation Layer:**
- User can click any signal card and add their own note: "I agree — already have a position"
- User can override the signal: mark it IGNORED with a reason
- These annotations feed back into the accuracy tracking: did user-overridden signals
  perform differently from accepted ones?

**Supply Chain Explorer:**
- Interactive graph view of the supply chain relationships for any ticker
- User can drag/explore: "show me everything upstream of TSMC"
- Click any node to run an on-demand analysis for that ticker
- This is the feature that makes users feel like they are discovering insights,
  not just receiving conclusions

**Insight Notebook:**
- A personal scratchpad inside the app
- User can save any signal + their own thesis alongside it
- One week later, the app surfaces it: "You flagged NVDA BULLISH 7 days ago.
  Price moved +8.2%. Was your thesis correct?"
- This creates a personal track record alongside the system's track record

The best financial platforms — Bloomberg, FactSet — are not dashboards. They are workspaces.
Users return daily not to read outputs but to explore, cross-reference, and build their own conviction.
Giving users control and the space to document their own thinking is what transforms
a single-session tool into a daily professional habit.

**Phase 2 Deliverable:** Each signal card now shows its type (FUNDAMENTAL/NARRATIVE/TECHNICAL),
source agreement score, and supply chain ripple effects. A Track Record page shows accuracy.
The Supply Chain Explorer is interactive. Users can filter, annotate, and track their own theses.
You can now answer "why should I trust this?" with data — and let users verify it themselves.

---

### Phase 3 — Skill-Based Agent Builder (Weeks 7–8)
**Goal: Turn users from passive readers into active participants who shape the intelligence**

This phase introduces the most commercially significant architectural shift in the product:
**agents are no longer hardcoded — they are assembled from user-editable skills.**

#### 3.1 The Skill Architecture — OpenClaw Pattern Applied

The core insight borrowed from OpenClaw and Hermes Agent:

```
Agent = Identity Layer (fixed, immutable)
      + Skills Layer (modular, user-editable, self-evolving)
```

**Identity Layer (fixed — users cannot edit this):**
- Who the agent is: name, role description
- LLM guardrails: what it will/will not say, compliance disclaimers
- Output format requirements: must return structured JSON, must cite sources
- Safety constraints: no buy/sell instructions, signals only

This layer is injected first as the system prompt. It cannot be overridden by skills.
This is how you allow user customisation without losing control of the product.

**Skills Layer (user-editable Markdown documents):**
- Each skill describes a capability: an analytical methodology, a data access pattern,
  a domain focus, a reasoning style
- Skills are injected into the agent's context after the fixed identity
- Multiple skills compose — an agent can hold 3–5 skills simultaneously
- A skill is plain Markdown: readable, auditable, editable without code

**The result:** adding a skill to an agent is like giving a human analyst a new specialty.
The analyst's professional ethics (guardrails) stay constant. Their expertise grows.

#### 3.2 Four Built-In Agents (Pre-Built Skills — Available to All Users)

These replace the hardcoded personas from the earlier roadmap draft.
Each is now a proper agent with its own skill set:

- **Value Analyst Agent** — skill: `fundamental_valuation.md`
  Focuses on P/E, P/B, FCF yield, earnings quality.
  Voice: "At 28× forward earnings with 15% growth, NVDA is fairly priced, not a bargain."

- **Momentum Analyst Agent** — skill: `technical_momentum.md`
  Focuses on price action, RSI, MACD, volume anomalies.
  Voice: "Volume +2σ above average on an RSI reset from 45 to 62 — textbook accumulation."

- **Supply Chain Analyst Agent** — skill: `supply_chain_intelligence.md`
  Unique to this product. Focuses on ecosystem dynamics, upstream/downstream relationships.
  Voice: "TSMC CoWoS expansion means NVDA packaging bottleneck resolves Q3 — bullish."

- **Risk Analyst Agent** — skill: `downside_risk_assessment.md`
  Focuses on tail risks, regulatory threats, macro headwinds.
  Voice: "China export controls could remove 20% of NVDA's addressable market overnight."

Each agent votes BULLISH / BEARISH / NEUTRAL. The aggregated signal is a weighted vote.
All four are available to all users — free and paid.

#### 3.3 User Skill Editor — Premium Feature

Paid users can create and edit their own skills. The interface is a simple Markdown editor
inside the app. What a user can define in a skill:

```markdown
# HK Property Sector Skill
## Focus
Analyse Hong Kong listed property developers (e.g. 0016.HK, 0688.HK).
Prioritise: land bank data, rental yield vs mortgage rate spread, HKMA policy.

## Data Sources to Emphasise
- HKEX announcements (CCASS data for institutional flows)
- HKMA monthly statistics for mortgage approval volumes  
- RICS Hong Kong property index

## Reasoning Approach
HK property is rate-sensitive and regulatory-sensitive in equal measure.
When HKMA raises rates OR government announces new SSD measures,
weight BEARISH even if fundamentals appear stable.
Supply pipeline (units under construction) is a 12–18 month leading indicator.

## Output Emphasis
Always include: rental yield vs 10-yr HK bond spread.
Flag immediately if: any government land sale produces unexpected result.
```

This skill, once created, spawns a new agent: **HK Property Analyst Agent**.
That agent:
- Uses this skill + the fixed identity/guardrail layer
- Accesses the same internal data (ChromaDB, SEC/HKEX filings, signal history)
- Has its own `PREDICTION_SKILL.md` that evolves from its own prediction track record
- Is private to the user who created it (unless they choose to publish it)

**Why this is a platform, not just a tool:**
A user who creates a HK Property skill is not just customising a dashboard.
They are creating a specialised analyst that learns from its own outcomes.
Over 3 months, their custom agent's PREDICTION_SKILL.md reflects the patterns
that actually predicted HK property moves — patterns no pre-built agent could know.

#### 3.4 "Ask About Any Ticker" Chat Mode
- A chat interface where the user selects which agent to query
- User selects: [HK Property Analyst Agent] then types "What do you think about 0016.HK?"
- The selected agent runs the full pipeline with its skills active
- Returns signal card + that agent's specific analytical lens
- User can run the same ticker through multiple agents to see different perspectives side-by-side

**Freemium boundary for this phase:**
- Free users: access all 4 built-in agents, read-only, 10 analyses/month
- Paid users: create unlimited custom agents, edit skills, full analysis history,
  skill evolution data, ability to publish skills to a public skill library

#### 3.3 Self-Improving Prediction Loop — The Hermes Pattern Applied to Finance

This is the most intellectually interesting feature in the entire roadmap,
and it is directly inspired by how **OpenClaw** and **Hermes Agent** handle skill improvement.

**Background — The OpenClaw/Hermes Skill Learning Pattern:**

OpenClaw (366k ⭐) is a personal AI assistant built around the concept of **skills** —
reusable procedures stored as `SKILL.md` files in the agent's workspace.
Hermes Agent (124k ⭐, by Nous Research), which markets itself as "the agent that grows with you,"
took this further: after completing a complex task, Hermes autonomously creates or updates a
SKILL.md that captures what worked. The skill self-improves during use.

Both systems use the same feedback loop:
```
Agent executes task → observes outcome → updates SKILL.md → better next time
```

The limitation in both: the feedback signal is user approval/disapproval, which is implicit
and subjective. Our financial system has something stronger: **objective market outcomes**.

**Our Adaptation — Prediction Skill Evolution:**

```
┌─────────────────────────────────────────────────────────────────────┐
│  PREDICTION CYCLE (runs daily)                                      │
│                                                                     │
│  1. Prediction Agent generates signal                               │
│     → signal card + FULL rationale chain stored in DB               │
│     → includes: which data points triggered the signal,             │
│       which persona voted which way, which claims were verified      │
└────────────────────────┬────────────────────────────────────────────┘
                         │ 5 trading days pass
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│  EVALUATION CYCLE (runs weekly)                                     │
│                                                                     │
│  2. Outcome retrieval                                               │
│     → fetch actual price at T+5 days                                │
│     → compute: direction correct? magnitude? unexpected events?      │
│                                                                     │
│  3. LLM-as-Judge reviews the original rationale                     │
│     → "The signal was BULLISH. Price moved -3%. Here was the        │
│        rationale. Which reasoning steps were flawed?                │
│        Which data signals were misleading? Which were valid?"        │
│     → Judge produces: reasoning_audit {correct_patterns: [...],     │
│                                        wrong_patterns: [...]}        │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│  SKILL UPDATE CYCLE (runs monthly)                                  │
│                                                                     │
│  4. Pattern aggregation across 30+ predictions                      │
│     → "Volume spike + SEC filing confirm together: 73% accuracy"    │
│     → "Single news source without price confirmation: 48% accuracy" │
│     → "MEDIA_NARRATIVE signals in semiconductor sector: 44%"         │
│                                                                     │
│  5. Skill document updated: PREDICTION_SKILL.md                     │
│     → Evidence-based rules extracted from real outcomes             │
│     → Injected into prediction agent system prompt on next cycle    │
└─────────────────────────────────────────────────────────────────────┘
```

**Why this is better than OpenClaw-RL (which needs 8× GPUs):**

OpenClaw-RL and Hermes's RL training update the model weights using reinforcement learning.
That requires significant compute and is out of scope for this project.

Your system achieves the same improvement loop through **prompt-based skill evolution** —
no GPU, no fine-tuning, no infrastructure beyond what you already have:
- The "skill" is a Markdown document (`PREDICTION_SKILL.md`) that accumulates evidence
- The LLM reads this document as part of its system prompt
- The document updates monthly based on verified outcomes
- The model gets smarter about finance not by changing its weights but by
  receiving better, evidence-grounded instructions

**Concrete implementation:**

- Add `prediction_log` table to SQLite: (ticker, signal, conviction, rationale_json,
  predicted_direction, timestamp, outcome_price, outcome_direction, outcome_verified)
- `weekly_judge.py` — runs every 5 trading days, fetches outcomes, calls LLM-as-judge
- `skill_updater.py` — runs monthly, aggregates judge reports, rewrites `PREDICTION_SKILL.md`
- The skill file is injected into the prediction agent's system prompt automatically

**What the PREDICTION_SKILL.md looks like after 3 months:**

```markdown
# Prediction Skill — Evidence Base (Updated 2026-04-29)
## Patterns with High Accuracy (>65% directional)
- Volume spike (+2σ) confirmed by institutional filing within same week: 71%
- CEO guidance raise + supply chain upstream capacity expansion: 68%
- FUNDAMENTAL_SHIFT signal in semiconductor sector: 66%

## Patterns with Low Accuracy (<50% — treat as MEDIA_NARRATIVE)
- Single analyst upgrade without price action confirmation: 44%
- Geopolitical news without supply chain filing corroboration: 41%
- Social media volume spike without institutional follow-through: 38%

## Sector-Specific Calibration
- HK/China equities: regulatory news has 2× volatility vs US equivalents
- Semiconductor: earnings guidance > analyst estimates as leading indicator
```

This document is the system's institutional memory. It grows with every prediction cycle.
After 3 months, the agent is not running the same prompts it started with —
it is running prompts grounded in its own verified track record.

**This is the product's core academic contribution:** an AI system that improves its
financial prediction methodology through a structured, evidence-based feedback loop,
without fine-tuning, using only LLM-as-judge and market outcomes as ground truth.
No comparable open-source finance AI project — ai-hedge-fund, FinRobot, or FinGPT — implements this loop.

**Phase 3 Deliverable:** A skill editor where users create custom agents. Four built-in agents
provide a "board of analysts" view for any ticker. Each agent runs its own pipeline lens.
The self-improving loop runs per-agent, updating each agent's `PREDICTION_SKILL.md` monthly.
By the end of Phase 4, 2–3 months of skill evolution data per agent will be available to demonstrate.
The freemium boundary is live: free users see the 4 built-in agents, paid users build their own.

---

### Phase 4 — Academic Validation & Commercial Pitch (Weeks 9–10)
**Goal: Quantify the product's value and present it to both academic and commercial audiences**

#### 4.1 Backtest Evaluation
- Backtest the full pipeline against 3 months of historical data (yfinance historical prices)
- For each date in the backtest period, simulate the signals the system would have generated
- Compute: directional accuracy, Sharpe ratio of following all signals vs buy-and-hold benchmark
- Present results as charts in the Streamlit evaluation dashboard

A measurable, quantitative evaluation of signal quality is what separates a product from a prototype.
Most AI finance projects are assessed on architecture alone — ours will have three months of verifiable outcome data.

#### 4.2 Differentiation Demo — "Why Not Just ChatGPT?"
- A side-by-side comparison view runs the same ticker through our full pipeline and a plain ChatGPT API call
- Our pipeline: real-time price data, SEC filing numbers, verified numerical claims with sources cited
- ChatGPT: training data knowledge, no real-time verification, no supply chain context
- Include documented cases where the numerical validator caught a specific hallucination

The comparison makes the product's differentiation concrete and tangible rather than purely architectural.
Users and evaluators can see exactly where grounded, domain-specific reasoning outperforms a general model.

#### 4.3 Commercial Positioning
MarketPulse demonstrates what enterprise-grade vertical AI agents look like in practice:

1. **Real-time data integration** — not static LLM training knowledge
2. **Structured, verifiable output** — not hallucinated prose with no audit trail
3. **Domain-specific reasoning** — supply chain intelligence that no general model can replicate
4. **Measurable accuracy** — a track record built on market outcomes, not benchmark claims

These principles transfer directly to any domain where trustworthy, grounded AI output matters:
compliance, risk advisory, client reporting, or any workflow where hallucination carries
real consequences. The product is both a standalone tool and a proof of concept for what
a well-architected domain AI agent can achieve.

---

## Part 7: What We Are NOT Building (And Why)

### Not Building a Trading Bot
Executing trades is a regulated activity in every jurisdiction.
Even as a prototype, connecting this to real broker APIs introduces legal complexity
that is out of scope for a student FYP. Keep this strictly advisory — signals only.

### Not Building a DCF Model (Yet)
A proper DCF valuation requires financial modeling expertise beyond what an LLM
can reliably produce. FinRobot does it with FMP's pre-computed financial data.
If we add DCF later, it should use structured financial data (FMP or similar), not LLM math.
This is a Phase 5+ feature.

### Not Expanding to 20+ Sectors Right Now
Each sector the system covers well is worth more than 20 sectors it covers badly.
The supply chain auto-discovery in Phase 2 effectively removes the sector constraint
because any ticker can build its own supply chain graph. Focus on depth, not breadth.

### Not Fine-Tuning an LLM
FinGPT's fine-tuned models require GPU, training data, and time that does not fit a 10-week plan.
More importantly, fine-tuning is the wrong solution to the problem we have.
Our problem is not "the LLM doesn't understand finance."
Our problem is "the LLM output is unstructured and unverifiable."
Structured prompting + tool use solves this without a single GPU.

Note: **OpenClaw-RL** and **Hermes Agent's** RL training path DO fine-tune models
using reinforcement learning from conversation feedback — these require 8× GPUs
and significant infrastructure. Our self-improving loop (Phase 3.3) achieves
the same conceptual goal (skill improvement from outcome feedback) through
prompt-based skill evolution instead. This is deliberate — it fits our constraints
and is actually more academically novel because the feedback signal (market outcomes)
is stronger and more objective than the user-approval signals those systems rely on.

---

## Part 8: Summary — The Argument for This Plan

| Decision | Why It Is Right |
|---|---|
| Quality over speed | A verified, thorough analysis is the product; latency is not a metric |
| Hybrid sector context + ticker output | Analytical depth of sector reasoning with actionability of per-ticker signal |
| Structured JSON over essays | Makes validation real, makes UI obvious, eliminates retry loops |
| Validation loop restructured (not removed) | Core project value preserved — moves upstream to work on fields not prose |
| HK stocks in Phase 1 | Personal relevance + competitive differentiation, zero extra architecture |
| Backtester in Phase 2 (not later) | Without it, you cannot defend the system academically |
| Supply chain auto-discovery | Turns your biggest claimed differentiator into a real AI capability |
| Skill-based agent architecture | Users create specialised agents; agents self-improve; this is the platform moat |
| Freemium boundary on skill editor | 4 built-in agents = free tier; custom skill creation = paid tier differentiator |
| Evaluation in Phase 4 | Academic credibility requires quantitative results, not just descriptions |
| Subscription framing | Positions this as a real product, not a prototype; relevant to company pitch |

**The core argument for this entire plan:**

The current system is impressive engineering that produces unimpressive output.
The target system is simpler engineering that produces a product people will actually use.

The shift is from "look at this complex pipeline" to "look at this useful signal."
From "here is our 5-layer validation architecture" to "here is our 65% directional accuracy over 90 days."
From "here is a sector report" to "here is what NVDA is doing this morning and why."

That shift is the difference between a prototype and a product investors return to daily.
It is also the difference between an architecture demonstration and a defensible business.

---

## Appendix: Phase-by-Phase Summary

| Phase | Duration | Key Deliverable | Success Metric |
|---|---|---|---|
| 1 — Signal Engine | Weeks 1–3 | Deep hybrid pipeline, structured JSON output, restructured Validation Loop | Validation score visible on every card; analysis is thorough and evidence-grounded |
| 2 — Credibility | Weeks 4–6 | Signal types, supply chain auto-discovery, track record, User Insight Explorer | Track record page shows measurable accuracy; users can filter/explore/annotate |
| 3 — Agent Builder | Weeks 7–8 | Skill-based agent architecture, 4 built-in agents, skill editor, self-improving loop, freemium split | Custom agents work; skill evolution running; free/paid boundary is clear |
| 4 — Polish | Weeks 9–10 | Backtest evaluation, ChatGPT comparison, subscription pitch, 2–3 months skill evolution data | Quantitative results + skill evolution evidence + freemium demo ready for academic and commercial presentation |
