# MarketPulse — UX Findings & Improvement Backlog

> **Author:** Technical Co-Founder review
> **Date:** 2026-05-29 · **Status update:** 2026-05-31
> **Method:** Code-level review of `frontend/` + live click-through of the running app (localhost:3000) + backend cross-check.
> **Audience bar:** *Real retail investors / a launchable product* — every issue below is graded against "would a real user trust this and feel they're gaining an edge?"
> **Scope of this document:** **User-experience problems only.** Functional/architectural problems (auth, RAG, hardcoded supply chain, evals) are tracked separately and fixed in a later phase.

---

## Status update — 2026-05-31

Shipped since the original review:

- **1.1 Disclaimers** — *partially done.* "Not financial advice" now appears in the global footer and persistently on the Decision Desk verdict panel. **Still open:** per-card "Data as of …" / "Generated …" freshness timestamps.
- **1.2 Mock/fallback data** — *partially done.* The fabricated track-record fallback on the accuracy page was removed (it now shows real, sometimes-empty data with a low-sample caveat). **Still open:** `DEMO_SIGNALS` (landing demo card) and `FALLBACK_AGENTS` (analyst catalog) are still rendered as fallbacks.
- **3.1 Mobile navigation** — *done.* A hamburger/drawer (`MobileNav.tsx`) replaces the scrolling nav below the breakpoint.
- **3.2 Decision Desk on phones** — *partially done.* The report table now has a mobile card-stack; a full responsive pass on `TickerBoard` itself is still pending.
- **4.x States & resilience** — a global error boundary (`global-error.tsx`) and a request timeout with calm, plain-language error copy were added.
- **New: cold-start guidance** — the Decision Desk now shows a one-click "Run the board" first-run guide instead of an empty screen, and finance jargon has plain-language tooltips.

The items below remain the authoritative backlog; treat the notes above as deltas.

---

## How to read this document

Each issue has two ratings:

- **Severity** — how broken it is technically.
  `🔴 Critical` · `🟠 High` · `🟡 Medium` · `⚪ Low`
- **UX Damage** — how much it hurts a real user's trust or ability to get value.
  `★★★★★` (destroys trust / blocks the core job) → `★` (cosmetic).

Issues are ordered by combined impact. Fix top-to-bottom.

---

## Tier 1 — Trust & Credibility Killers (fix first)

These don't just look bad — they make a finance user *distrust the numbers*, which is fatal for this category of product.

### 1.1 No disclaimers, no "not financial advice", no data-freshness labels
- **Severity:** 🔴 Critical · **UX Damage:** ★★★★★
- **What I saw:** Live pages present BULLISH/BEARISH calls, conviction dots, and "recommendations" with **zero** "not financial advice" disclaimer and **no "data as of <timestamp>"** anywhere.
- **Why it's bad:** (a) Legal/liability exposure — directional calls read as advice. (b) Sophisticated retail users will not trust a signal whose freshness and limitations they can't see. A stale price behind a confident "BULLISH" call is worse than no call.
- **Fix:** Global footer disclaimer + per-card/per-page "Data as of …" and "Generated …" timestamps + a short "limitations" line on every signal.

### 1.2 Mock/fallback data ships to users when the backend hiccups
- **Severity:** 🔴 Critical · **UX Damage:** ★★★★★
- **What I saw:** `DEMO_SIGNALS` and `FALLBACK_AGENTS` are bundled and rendered if a query fails or returns empty (`frontend/src/components/AgentGallery.tsx`, landing fallback).
- **Why it's bad:** In a finance app, silently showing *fake* signals/agents as if real is a credibility bomb. A user could act on invented data.
- **Fix:** Replace all fallback mock data with explicit empty/error states ("Couldn't load signals — retry"). Never render fabricated financial content.

### 1.3 Visible dev artifact on screen
- **Severity:** 🟠 High · **UX Damage:** ★★★☆☆
- **What I saw:** The black Next.js **"N"** dev indicator overlaps the "Analysis Progress" text on the Decision Desk.
- **Why it's bad:** Instantly reads as "unfinished hackathon project" — the exact impression you said you want to avoid.
- **Fix:** Disable the dev indicator in the shared/demo build (`devIndicators` in `next.config.ts`).

### 1.4 Half-built features exposed as if they work
- **Severity:** 🟠 High · **UX Damage:** ★★★★☆
- **What I saw:**
  - **Sign-out** is a dead placeholder (`frontend/src/components/UserMenu.tsx` — "placeholder until NextAuth").
  - **Profile → saved sectors** is editable and persisted, but **never used** anywhere (no filtering, no effect).
  - **Custom agent skill** form has no validation feedback and no success confirmation.
- **Why it's bad:** Dead/no-op controls teach users the product is unreliable. One dead button casts doubt on every other button.
- **Fix:** Hide/disable controls that don't do anything yet, or make them function. Add success/error toasts to the skill form.

---

## Tier 2 — Core Job & Information Architecture (fix second)

The product doesn't yet answer the retail user's real question fast: *"I hold/eye ticker X — what changed and what should I think?"*

### 2.1 Landing page buries the actual product below metadata
- **Severity:** 🟠 High · **UX Damage:** ★★★★☆
- **What I saw:** "Today Brief" (`/signals`) opens with three large stacked cards — *Published Cards: 74*, *Active Filter: All signals*, *Page 1 / 7* — before any signal is visible.
- **Why it's bad:** The first screen is *metadata about metadata*. No immediate insight, no "aha." Users land and bounce.
- **Fix:** Lead with content (top signals / "what changed today"). Demote counts to a slim toolbar.

### 2.2 IA is built for an analyst team, not a retail user
- **Severity:** 🟠 High · **UX Damage:** ★★★★☆
- **What I saw:** Six top-level destinations — Today Brief, Decision Desk, Supply Map, Archive, Analysts, Accuracy — plus jargon ("Evidence-gated ticker view", "auditable cards", "soft recommendation"). "Today Brief", "Decision Desk", and "Archive" are three overlapping views of largely the same signals.
- **Why it's bad:** Users must learn a vocabulary and a mental model before getting value. Overlapping views create "which one do I use?" paralysis.
- **Fix:** Define a primary "one ticker" hero flow. Merge/clarify the overlapping signal views. Translate jargon to plain language. (Detailed proposal to be agreed during planning.)

### 2.3 Supply Map — your differentiator — is buried 3rd in the nav
- **Severity:** 🟡 Medium · **UX Damage:** ★★★☆☆
- **What I saw:** The layered supply-chain flow (Raw Materials → Fabrication → Chip Design → Server Assembly → Cloud → Energy) is the most unique, "wow" screen, yet it's not the front door and isn't interactive (no click-to-expand, no per-ticker linking).
- **Why it's bad:** The thing that makes this product *different* is the least prominent. Users may never discover the moat.
- **Fix:** Promote Supply Map prominence; make nodes interactive and linked to signals.

### 2.4 Off-script tickers silently under-deliver
- **Severity:** 🟠 High · **UX Damage:** ★★★★☆
- **What I saw:** Supply-chain reasoning is hardcoded to ~10 AI/semiconductor names. Typing `AAPL`/`TSLA` yields no supply-chain depth, with no UI message saying so. *(This has a functional root cause tracked separately, but the UX symptom belongs here.)*
- **Why it's bad:** The headline promise ("deep supply chain analysis") breaks the first time a user goes off-script, with no explanation.
- **Fix (UX-side, now):** When a ticker is out of covered scope, say so clearly ("Supply-chain depth currently covers AI & Semiconductors — here's what we can show"). Set expectations instead of failing silently.

---

## Tier 3 — Responsive & Device Support

### 3.1 No real mobile navigation
- **Severity:** 🟠 High · **UX Damage:** ★★★★☆
- **What I saw:** On narrow viewports the top nav (`frontend/src/components/AppNav.tsx`) becomes a horizontal scrollbar instead of a hamburger/drawer.
- **Why it's bad:** Retail investors check phones first. A scrolling nav bar is broken-feeling.
- **Fix:** Hamburger + slide-out drawer below a breakpoint.

### 3.2 Decision Desk / TickerBoard unusable on phones
- **Severity:** 🟠 High · **UX Damage:** ★★★★☆
- **What I saw:** `TickerBoard.tsx` is a 20+ column table; on mobile it requires heavy horizontal scrolling.
- **Why it's bad:** The "decision" surface is the one users most want on the go, and it's the least mobile-friendly.
- **Fix:** Responsive card/stacked layout below a breakpoint.

### 3.3 Fixed-width inputs and chat clipping
- **Severity:** 🟡 Medium · **UX Damage:** ★★☆☆☆
- **What I saw:** Filter inputs use fixed widths (`.w-36`); the floating evidence chat header can clip on very small phones.
- **Fix:** Fluid widths; verify chat at 320px width.

---

## Tier 4 — States, Feedback & Resilience

### 4.1 Weak/absent empty & error states
- **Severity:** 🟡 Medium · **UX Damage:** ★★★☆☆
- **What I saw:** Errors render as plain text ("Failed to load signals: …") with no retry; `/agents`, `/supply-chain`, `/accuracy` lack proper empty/loading states.
- **Fix:** Consistent empty-state component + error component with a retry button across all data views.

### 4.2 Inconsistent error styling & date formats
- **Severity:** ⚪ Low · **UX Damage:** ★★☆☆☆
- **What I saw:** Errors sometimes `text-red-400`, sometimes `text-destructive`; date formats vary (some with time, some without); System Health auto-refreshes but shows no "last updated" time.
- **Fix:** Standardize on tokens; one date-format helper; show refresh timestamps.

### 4.3 No progress/announcement for live runs (non-admin)
- **Severity:** 🟡 Medium · **UX Damage:** ★★★☆☆
- **What I saw:** Live pipeline SSE is admin-only; regular users get no "analysis running / last updated" indicator.
- **Fix:** Lightweight run-status/last-updated indicator on user-facing pages.

---

## Tier 5 — Accessibility

### 5.1 Color-only signaling for bull/bear
- **Severity:** 🟡 Medium · **UX Damage:** ★★★☆☆
- **What I saw:** Direction conveyed mainly by green/red badges; conviction dots have no aria labels; sector dots undescribed.
- **Why it's bad:** ~8% of men are red-green colorblind — and they trade. Color-only = inaccessible *and* ambiguous.
- **Fix:** Add text/icon labels alongside color; `aria-label` on dots and rings.

### 5.2 Focus management & live regions
- **Severity:** ⚪ Low · **UX Damage:** ★★☆☆☆
- **What I saw:** Floating chat doesn't trap focus when open; user menu doesn't restore focus on close; no `aria-live` for dynamic SSE updates.
- **Fix:** Focus trap + restoration; `aria-live="polite"` for streamed updates.

---

## Suggested fix order (UX-first)

| Phase | Items | Why this order |
|---|---|---|
| **A. Trust quick-wins** | 1.1, 1.2, 1.3, 1.4 | Cheap, high-impact, removes "demo" smell and liability. |
| **B. Core flow & IA** | 2.1, 2.2, 2.3, 2.4 | Makes the product actually answer the user's question. |
| **C. Mobile** | 3.1, 3.2, 3.3 | Unblocks the most common device. |
| **D. States & a11y** | 4.x, 5.x | Polish that makes it feel finished and inclusive. |

---

## Note on the "rich toolbox" goal

You want users to feel *"this site gives me so many great tools — I gain a lot here."* That instinct is good, **but** adding tools on top of the Tier 1–2 problems would amplify the trust issues (more dead/half-built buttons). Recommended sequence: **fix Tier 1 → fix Tier 2 core flow → then layer in new tools** so each new tool lands on a trustworthy base. Candidate tools (to be prioritized during planning, not yet committed):

- Critical/important-news filter (high value, plays to existing strengths)
- Watchlist + per-ticker "what changed this week" digest
- Simple backtest / P&L-vs-benchmark chart (proves edge → builds trust)
- Compare two tickers / sector heatmap
- Saved views & alerts

> These are *candidates*. We will decide which make the cut so the product feels rich **without** feeling unfinished.
