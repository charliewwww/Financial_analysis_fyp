# Supply Chain Alpha

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
| Vector store | ChromaDB (RAG context for LLM nodes) |
| LLM | GLM-4.7-Flash via Ollama (local) / OpenRouter (dev) |
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
DATABASE_URL=postgresql+asyncpg://user:pass@localhost/supplychain
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

### Backend — 117 / 117

```powershell
cd backend
$env:PYTHONPATH = "C:\path\to\fyp\backend"
..\venv\Scripts\python.exe -m pytest tests/ -v
```

### Frontend — 69 / 69

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

See [PRODUCT_ROADMAP.md](PRODUCT_ROADMAP.md) for the full phased build plan.

| Phase | Status |
|---|---|
| Platform foundation (FastAPI + Next.js + PostgreSQL) | ✅ Complete |
| Multi-tenancy & user profiles | ✅ Complete |
| Phase 1 — Core Signal Engine (structured JSON output, validation loop) | 🔲 Next |
| Phase 2 — Credibility Layer (signal type classification, backtester) | 🔲 Planned |
| Phase 3 — Skill-Based Agent Builder | 🔲 Planned |
| Phase 4 — Academic Validation & Commercial Pitch | 🔲 Planned |

## Test and Deploy

Use the built-in continuous integration in GitLab.

- [ ] [Get started with GitLab CI/CD](https://docs.gitlab.com/ee/ci/quick_start/)
- [ ] [Analyze your code for known vulnerabilities with Static Application Security Testing (SAST)](https://docs.gitlab.com/ee/user/application_security/sast/)
- [ ] [Deploy to Kubernetes, Amazon EC2, or Amazon ECS using Auto Deploy](https://docs.gitlab.com/ee/topics/autodevops/requirements.html)
- [ ] [Use pull-based deployments for improved Kubernetes management](https://docs.gitlab.com/ee/user/clusters/agent/)
- [ ] [Set up protected environments](https://docs.gitlab.com/ee/ci/environments/protected_environments.html)

***

# Editing this README

When you're ready to make this README your own, just edit this file and use the handy template below (or feel free to structure it however you want - this is just a starting point!). Thanks to [makeareadme.com](https://www.makeareadme.com/) for this template.

## Suggestions for a good README

Every project is different, so consider which of these sections apply to yours. The sections used in the template are suggestions for most open source projects. Also keep in mind that while a README can be too long and detailed, too long is better than too short. If you think your README is too long, consider utilizing another form of documentation rather than cutting out information.

## Name
Choose a self-explaining name for your project.

## Description
Let people know what your project can do specifically. Provide context and add a link to any reference visitors might be unfamiliar with. A list of Features or a Background subsection can also be added here. If there are alternatives to your project, this is a good place to list differentiating factors.

## Badges
On some READMEs, you may see small images that convey metadata, such as whether or not all the tests are passing for the project. You can use Shields to add some to your README. Many services also have instructions for adding a badge.

## Visuals
Depending on what you are making, it can be a good idea to include screenshots or even a video (you'll frequently see GIFs rather than actual videos). Tools like ttygif can help, but check out Asciinema for a more sophisticated method.

## Installation
Within a particular ecosystem, there may be a common way of installing things, such as using Yarn, NuGet, or Homebrew. However, consider the possibility that whoever is reading your README is a novice and would like more guidance. Listing specific steps helps remove ambiguity and gets people to using your project as quickly as possible. If it only runs in a specific context like a particular programming language version or operating system or has dependencies that have to be installed manually, also add a Requirements subsection.

## Usage
Use examples liberally, and show the expected output if you can. It's helpful to have inline the smallest example of usage that you can demonstrate, while providing links to more sophisticated examples if they are too long to reasonably include in the README.

## Support
Tell people where they can go to for help. It can be any combination of an issue tracker, a chat room, an email address, etc.

## Roadmap
If you have ideas for releases in the future, it is a good idea to list them in the README.

## Contributing
State if you are open to contributions and what your requirements are for accepting them.

For people who want to make changes to your project, it's helpful to have some documentation on how to get started. Perhaps there is a script that they should run or some environment variables that they need to set. Make these steps explicit. These instructions could also be useful to your future self.

You can also document commands to lint the code or run tests. These steps help to ensure high code quality and reduce the likelihood that the changes inadvertently break something. Having instructions for running tests is especially helpful if it requires external setup, such as starting a Selenium server for testing in a browser.

## Authors and acknowledgment
Show your appreciation to those who have contributed to the project.

## License
For open source projects, say how it is licensed.

## Project status
If you have run out of energy or time for your project, put a note at the top of the README saying that development has slowed down or stopped completely. Someone may choose to fork your project or volunteer to step in as a maintainer or owner, allowing your project to keep going. You can also make an explicit request for maintainers.
