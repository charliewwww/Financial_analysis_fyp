# Backend Overview — What Was Built and What Changes

## What Was Built

The `backend/` folder is a new FastAPI application that exposes everything the
Streamlit UI currently does as a proper HTTP API. Once the Next.js frontend is
wired up this backend is the **only** server that needs to run; Streamlit can
then be deleted.

```
backend/
├── app/
│   ├── main.py                   # FastAPI app entry-point, lifespan, CORS
│   ├── core/config.py            # Typed settings (pydantic-settings, reads .env)
│   ├── api/
│   │   └── routes/
│   │       ├── reports.py        # GET /api/v1/reports/*
│   │       ├── signals.py        # GET /api/v1/signals/*
│   │       └── pipeline.py       # POST/GET /api/v1/pipeline/runs, SSE stream
│   ├── db/
│   │   ├── engine.py             # AsyncEngine singleton + get_db dependency
│   │   ├── tables.py             # SQLAlchemy Core table definitions (9 tables)
│   │   └── repositories/
│   │       ├── reports.py        # CRUD for legacy reports table
│   │       ├── signals.py        # CRUD for signal_cards + pipeline_runs
│   │       └── predictions.py    # Accuracy-loop CRUD
│   ├── pipeline/runner.py        # Async/sync bridge to the LangGraph pipeline
│   └── schemas/
│       ├── common.py             # HealthResponse, PaginatedResponse, etc.
│       ├── analysis.py           # SignalCardSchema, PipelineStateSchema, etc.
│       ├── pipeline.py           # RunRequest, PipelineRunSchema, SSEEvent, etc.
│       └── reports.py            # ReportSummary, AccuracyStats, etc.
├── tests/
│   ├── conftest.py               # SQLite fixtures (raw DDL, no PostgreSQL needed)
│   ├── test_schemas.py           # 36 Pydantic validation tests
│   ├── test_repositories.py      # 36 async CRUD tests (in-memory SQLite)
│   └── test_routes.py            # 25 route integration tests (dependency mocked)
└── requirements.txt
```

---

## Route Map

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/health` | Liveness check |
| GET | `/api/v1/reports/` | Paginated report list (filter by `sector_id`) |
| GET | `/api/v1/reports/{id}` | Single report detail |
| GET | `/api/v1/reports/{id}/predictions` | Predictions for a report |
| GET | `/api/v1/signals/` | Paginated signal-card list (filters: `ticker`, `signal`, `signal_type`) |
| GET | `/api/v1/signals/accuracy` | Global accuracy stats |
| GET | `/api/v1/signals/latest/{ticker}` | Most-recent signal for a ticker |
| GET | `/api/v1/signals/{card_id}` | Single signal card |
| GET | `/api/v1/signals/{card_id}/predictions` | Predictions for a signal card |
| POST | `/api/v1/pipeline/runs` | Trigger a new pipeline run (202 Accepted; per-user concurrency cap → 429) |
| POST | `/api/v1/pipeline/runs/fanout` | Board-of-analysts fanout for one ticker (rate-limited) |
| POST | `/api/v1/pipeline/runs/sector-fanout` | Sector-wide board fanout (rate-limited) |
| POST | `/api/v1/pipeline/runs/sector-synthesis` | Single board-level sector synthesis (rate-limited) |
| GET | `/api/v1/pipeline/runs` | List pipeline runs (filters: `ticker`, `status`) |
| GET | `/api/v1/pipeline/runs/{run_id}` | Single run status |
| GET | `/api/v1/pipeline/runs/{run_id}/stream` | SSE live-progress stream (bounded queue, drop-oldest) |

Interactive docs: `http://localhost:8000/api/docs`

---

## What Each Part Replaces in the Streamlit App

| Old Streamlit code | New backend equivalent |
|--------------------|------------------------|
| `database/reports_db.py` — `save_report()`, `get_all_reports()` | `db/repositories/reports.py` — `create_report_from_state`, `list_reports`, `get_report` |
| `ui/page_reports.py` — loads and displays reports | `GET /api/v1/reports/` + `GET /api/v1/reports/{id}` |
| `ui/page_predictions.py` — shows accuracy loop | `GET /api/v1/signals/accuracy` + `GET /api/v1/signals/{id}/predictions` |
| `ui/page_pipeline.py` — trigger form + status display | `POST /api/v1/pipeline/runs` + `GET …/stream` (SSE) |
| `ui/page_dashboard.py` — morning-brief signal cards | `GET /api/v1/signals/` + `GET /api/v1/signals/latest/{ticker}` |
| `ui/page_supply_chain.py` — supply-chain links | Phase 2 (not yet exposed, table `supply_chain_relationships` created) |
| `app.py` / `main.py` — Streamlit entry-point | Deleted once Next.js frontend is live |

Files that can be deleted after the frontend is complete:
```
app.py
main.py
ui/          (all 7 files)
generate_ppt.py
```

---

## Changes Made to Fix Test Issues

### 1. `app/schemas/common.py` — `HealthResponse.version` default

```python
# Before
class HealthResponse(BaseModel):
    version: str          # required field — broke test_defaults_empty_version

# After
class HealthResponse(BaseModel):
    version: str = ""     # optional, defaults to empty string
```

### 2. `tests/conftest.py` — SQLite-compatible table creation

The production tables use `JSONB` (PostgreSQL-specific).  SQLite has no
`visit_JSONB` handler, so `create_all_tables(engine)` crashed in tests.

Fix: replaced `create_all_tables()` with raw DDL using `TEXT` instead of
`JSONB`.  The repository helpers (`_coerce_jsonb`) already handle `TEXT →
dict` deserialization, so all 35 repository tests pass unchanged.

### 3. `tests/test_routes.py` — FastAPI dependency override

The original fixture patched `get_engine` to raise `RuntimeError`, but
`get_db` calls `get_engine()` on every request → every route returned 500.

Fix: use FastAPI's `dependency_overrides` to replace `get_db` with an
async generator that yields a `MagicMock`, so the route handlers receive a
valid (mock) connection without touching the engine.

```python
from app.db.engine import get_db

async def _mock_db():
    yield AsyncMock()

app.dependency_overrides[get_db] = _mock_db
```

---

## Test Results

```
223 passed
  - test_repositories     (SQLite in-memory, full CRUD lifecycle)
  - test_routes           (TestClient, mocked DB dependency; incl. 429 quota tests)
  - test_schemas          (Pydantic validation)
  - test_runner_persistence (pipeline bridge; incl. bounded-queue + orphan-reaper tests)
  - test_signal_extractor (signal-type classifier + conviction honesty)
  - test_prediction_resolver
```

Legacy/root tests are unaffected: 267/267 still passing in the root
`tests/` folder.

---

## Running the Backend

```powershell
# From repo root, with .env in place
venv\Scripts\python.exe -m uvicorn backend.app.main:app --reload --port 8000

# Run backend tests only
cd backend
$env:PYTHONPATH = (Get-Location).Path
..\venv\Scripts\python.exe -m pytest tests/ -v
```
