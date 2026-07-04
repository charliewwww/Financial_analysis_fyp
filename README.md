# MarketPulse

> Multi-agentic financial intelligence platform — FYP by Wong Tsz Hei Charlie (57141182)

A market intelligence system that performs second-order supply-chain reasoning on live
financial data, classifies signals as `FUNDAMENTAL_SHIFT / MEDIA_NARRATIVE / TECHNICAL_ONLY`,
and self-improves its prediction methodology through a structured LLM-as-judge feedback loop.

---

## Architecture

```
┌──────────────────────────────────────────────────────┐
│  Next.js 16 (App Router)  ←→  FastAPI 0.115          │
│  TanStack Query v5             SQLAlchemy Core 2.0    │
│  Cloudflare Access (auth)      PostgreSQL + ChromaDB  │
└──────────────────────────────────────────────────────┘
```

| Layer | Technology |
|---|---|
| Frontend | Next.js 16, TanStack Query v5, Tailwind CSS |
| Backend API | FastAPI 0.115, Pydantic v2, SQLAlchemy Core (async) |
| Database | PostgreSQL (prod) · SQLite (tests) |
| Vector store | ChromaDB — RAG context retrieved and injected into the analyze node (news + filings + the desk's own prior analyses) |
| LLM | GLM-4.7-Flash via Ollama (local, prod) · DeepSeek-V4-Flash via OpenRouter (dev) — configurable per provider |
| Authentication | Cloudflare Access — identity via `Cf-Access-Authenticated-User-Email` header |
| Pipeline orchestration | LangGraph nodes (`workflows/nodes.py`) |

---

## Project Layout

```
backend/        FastAPI app, SQLAlchemy tables, repositories, routes, tests
frontend/       Next.js 16 app, TanStack Query hooks, Vitest tests
agents/         LLM agent implementations (analyst, validator, llm_client)
workflows/      LangGraph pipeline nodes (ticker_pipeline, weekly_analysis)
data_sources/   Live data connectors (Yahoo Finance, SEC EDGAR, FRED, RSS)
vectordb/       ChromaDB store wrapper
config/         Sector maps, supply chain data, settings
evals/          LLM-as-judge evaluation framework and ablation studies
```

---

## Running Locally

### Prerequisites
- Python 3.11+ with the project `venv` activated
- Node.js 20+
- PostgreSQL (or set `DATABASE_URL` to a SQLite path for quick dev)
- Ollama running locally with `glm4:flash` pulled, or an OpenRouter API key

### Environment

Copy `.env.example` to `.env` and set:

```
DATABASE_URL=postgresql+asyncpg://user:pass@localhost/marketpulse
OPENROUTER_API_KEY=sk-...          # or leave blank to use local Ollama
AUTH_BYPASS_EMAIL=dev@local         # bypass Cloudflare header during local dev
                                    # !! remove this in production !!
```

### Backend

```powershell
# from repo root
venv\Scripts\Activate.ps1
cd backend
python -m uvicorn app.main:app --reload --port 8000
```

API docs available at `http://localhost:8000/docs`.

### Frontend

```powershell
cd frontend
npm install
npm run dev    # → http://localhost:3000
```

---

## Tests

### Backend & root (pytest)

```powershell
cd backend
$env:PYTHONPATH = "C:\path\to\fyp\backend"
..\venv\Scripts\python.exe -m pytest tests/ -v
```

> Note: run `backend/tests` and the repo-root `tests/` in separate invocations —
> mixing both in one `pytest` run triggers an `ImportPathMismatchError`.

### Frontend — 135 / 135

```powershell
cd frontend
npm test
```

---

## API Routes

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/signals/` | List signal cards (scoped to current user) |
| `GET` | `/api/v1/signals/{id}` | Get one signal card |
| `GET` | `/api/v1/signals/latest` | Latest signal for a ticker |
| `GET` | `/api/v1/reports/` | List reports (scoped to current user) |
| `GET` | `/api/v1/reports/{id}` | Get one report |
| `POST` | `/api/v1/pipeline/trigger` | Trigger pipeline run |
| `GET` | `/api/v1/pipeline/runs` | List pipeline runs (scoped to current user) |
| `GET` | `/api/v1/pipeline/runs/{id}` | Get one run |
| `GET` | `/api/v1/users/me` | Get current user's profile |
| `PATCH` | `/api/v1/users/me` | Update profile (username, saved sectors, preferences) |

---

## Multi-Tenancy

Authentication is handled by Cloudflare Access. Every request carries a
`Cf-Access-Authenticated-User-Email` header that the backend extracts via the
`get_current_user` dependency (`backend/app/core/auth.py`).

All data rows in `signal_cards`, `pipeline_runs`, `reports`, `watchlist`, and `annotations`
carry a `user_email` column. Repository list/get methods filter by that column so users only
see their own data. Legacy rows (pre-auth, `user_email IS NULL`) remain visible to all users.

A `user_details` table holds optional profile data: `username`, `saved_sectors` (JSONB),
and `preferences` (JSONB). The profile is created on first login via `get_or_create`.

---

## Roadmap

See [MASTER_PLAN.md](MASTER_PLAN.md) for the canonical, phased build plan and the
honest current-state assessment. (`PRODUCT_ROADMAP.md` is retained as a historical record.)

| Phase | Status |
|---|---|
| Platform foundation (FastAPI + Next.js + PostgreSQL) | ✅ Complete |
| Multi-tenancy & user profiles | ✅ Complete |
| RAG context wired into the analyze node (ChromaDB) | ✅ Complete |
| Trust & UX hardening (disclaimers, error boundary, mobile nav, cold-start guide) | 🟡 In progress |
| Phase 1 — Core Signal Engine (structured JSON output, upstream validation) | 🔲 Next |
| Phase 2 — Credibility Layer (signal-type classification, backtester) | 🔲 Planned |
| Phase 3 — Skill-Based Agent Builder | 🔲 Planned |
| Phase 4 — Academic Validation & Commercial Pitch | 🔲 Planned |

---

## Documentation

| Doc | Purpose |
|---|---|
| [MASTER_PLAN.md](MASTER_PLAN.md) | Canonical product plan, roadmap, and honest current-state assessment |
| [UX_FINDINGS.md](UX_FINDINGS.md) | UX backlog with severity ratings and fix order |
| [docs/ARCHITECTURE_DIAGRAM.md](docs/ARCHITECTURE_DIAGRAM.md) | Deployment & data-flow diagrams |
| [backend/BACKEND_OVERVIEW.md](backend/BACKEND_OVERVIEW.md) | Backend architecture walkthrough |
| [frontend/FRONTEND_OVERVIEW.md](frontend/FRONTEND_OVERVIEW.md) | Frontend architecture walkthrough |

## License

Academic Final-Year Project — not currently licensed for external redistribution.

