# Frontend Overview — What Was Built and What Changes

## Stack

| Concern | Choice |
|---|---|
| Framework | Next.js 16 (App Router, RSC) |
| Language | TypeScript strict |
| Styling | Tailwind CSS v4 + shadcn/ui v4 |
| Data fetching | TanStack Query v5 (30 s stale time) |
| Test runner | Vitest v4 + React Testing Library |
| API origin | `NEXT_PUBLIC_API_URL` env var → `http://localhost:8000` in dev |

---

## File Map

```
frontend/
├── .env.local                        NEXT_PUBLIC_API_URL=http://localhost:8000
├── vitest.config.ts                  Vitest + jsdom + @/ alias
├── src/
│   ├── types/api.ts                  TypeScript interfaces for every backend schema
│   ├── lib/
│   │   ├── api.ts                    Typed fetch wrappers for all 13 endpoints
│   │   └── query-client.tsx          QueryProvider (TanStack Query, 30 s stale)
│   ├── app/
│   │   ├── layout.tsx                Root layout — sticky nav, dark mode, providers
│   │   ├── page.tsx                  redirect("/signals")
│   │   ├── signals/page.tsx          Morning Brief — paginated signal card grid
│   │   ├── signals/[id]/page.tsx     Signal card detail + predictions table
│   │   ├── pipeline/page.tsx         Trigger form + live SSE progress stream
│   │   ├── reports/page.tsx          Paginated reports list
│   │   ├── reports/[id]/page.tsx     Report detail — analysis, validation, predictions
│   │   └── accuracy/page.tsx         Accuracy stats + active cards tabs
│   ├── components/
│   │   ├── SignalCard.tsx            Card grid item (signal badge, conviction dots, supply chain)
│   │   ├── PipelineRunner.tsx        Form + EventSource SSE live progress
│   │   ├── ReportTable.tsx           Sortable report list table
│   │   └── AccuracyStats.tsx         Overall stats + per-signal-type breakdown
│   └── tests/
│       ├── setup.ts                  @testing-library/jest-dom matchers
│       ├── types.test.ts             TypeScript shape tests
│       ├── api.test.ts               fetch mock tests (URL building + error handling)
│       ├── components.test.tsx       render tests (incl. signal-type + conviction-not-stated)
│       ├── trust.test.ts             trust/disclaimer copy + honest-label tests
│       ├── primitives.test.tsx       shared UI primitive tests
│       ├── pipeline-progress.test.ts SSE progress mapping tests
│       └── parse-analysis.test.ts    analysis-parsing tests
```

---

## Routes

| URL | Page | Data |
|---|---|---|
| `/` | Redirects → `/signals` | — |
| `/signals` | Morning Brief | `GET /api/v1/signals/` (paginated, filtered) |
| `/signals/[id]` | Signal detail | `GET /api/v1/signals/{id}` + `…/predictions` |
| `/pipeline` | Pipeline runner | `POST /api/v1/pipeline/runs` + SSE stream |
| `/reports` | Report list | `GET /api/v1/reports/` (paginated) |
| `/reports/[id]` | Report detail | `GET /api/v1/reports/{id}` |
| `/accuracy` | Accuracy + cards | `GET /api/v1/signals/accuracy` + signals list |

---

## Key Design Decisions

**RSC vs `"use client"`** — All pages are server components by default.  Any component
that calls `useQuery`, `useState`, or `useEffect` has `"use client"` at the top.
This means the nav and outer shells render on the server; data-fetching widgets run
in the browser.

**Single `lib/api.ts`** — Every backend call is a typed function here.  No raw
`fetch()` calls in components.  The base URL is `process.env.NEXT_PUBLIC_API_URL`
so switching environments (staging, prod) requires only an env var change.

**SSE in `PipelineRunner`** — Uses the native `EventSource` API inside a `useEffect`.
The component is `"use client"`.  On unmount or on completion the stream is
closed.  After pipeline completion, `queryClient.invalidateQueries` refreshes
the signals list and run list automatically.

**TanStack Query cache keys** — The convention is `["resource", params]`, e.g.
`["signals", { ticker, signal, page }]`.  Pipeline completion invalidates
`["signals"]` and `["runs"]` so the morning brief refreshes without a page reload.

---

## What Replaces What from Streamlit

| Streamlit `ui/` file | Frontend equivalent |
|---|---|
| `page_dashboard.py` — signal card list | `/signals` page + `SignalCard.tsx` |
| `page_pipeline.py` — trigger + status | `/pipeline` page + `PipelineRunner.tsx` |
| `page_reports.py` — report list | `/reports` page + `ReportTable.tsx` |
| `page_predictions.py` — accuracy loop | `/accuracy` page + `AccuracyStats.tsx` |
| `page_supply_chain.py` | Phase 2 (not yet built) |
| `app.py` / `main.py` — Streamlit entry | Deleted after frontend is live |

---

## Changes Made During Audit

### 1. Removed unused `Separator` import — `PipelineRunner.tsx`

```diff
- import { Separator } from "@/components/ui/separator";
```
`Separator` was imported but never used in JSX.  This was causing an ESLint
`no-unused-vars` warning and added dead weight.

### 2. Fixed ambiguous test assertion — `components.test.tsx`

```diff
- expect(screen.getByText("5")).toBeInTheDocument();
+ expect(screen.getByText("awaiting price data")).toBeInTheDocument();
```
`getByText("5")` matched two elements (`unchecked` stat + macro row in the
breakdown table), causing a `Found multiple elements` error.  Changed the
assertion to target the unique sub-label text instead.

---

## Test Results

```
 Test Files  7 passed (7)
      Tests  135 passed (135)
```

The suite has grown beyond the original three files (types/api/components) to
also cover trust copy, signal-type labels, "conviction not stated" rendering,
and TickerBoard coverage/active-row behaviour.

### What each test file covers

**`types.test.ts`** — Structural shape tests for every exported TypeScript interface.
Confirms nullable fields accept `null`, union types accept all valid literals, and
nested objects compose correctly.

**`api.test.ts`** — Mocks `global.fetch` and asserts the exact URL each function
builds (including query-string params), verifies POST body serialisation, and
confirms that non-ok responses throw with the status code.

**`components.test.tsx`** — Renders `SignalCard`, `ReportTable`, and `AccuracyStats`
with RTL, asserts visible text, links, conditional rendering (empty state, null
fields, zero-state stats), and CSS class names for signal colours.

---

## Running the Frontend

```powershell
# Dev server (hot-reload)
cd frontend
npm run dev          # → http://localhost:3000

# Production build (also validates TypeScript)
npm run build

# Tests
npm test             # single run
npm run test:watch   # watch mode
npm run test:coverage
```

> The FastAPI backend must be running on port 8000 for data to load.
> Start it with: `uvicorn backend.app.main:app --reload --port 8000`
