@echo off
REM ── MarketPulse — PRODUCTION-mode Quick Start ──
REM Starts the FastAPI backend and a PRODUCTION Next.js build in two windows.
REM
REM  Window 1: FastAPI  → http://localhost:8000   (API docs: /docs)
REM  Window 2: Next.js  → http://localhost:3000   (prod build — fast, no dev recompiles)
REM
REM Note: the backend runs in DEV identity mode so the local auth-bypass works.
REM Full production auth would require Google OAuth env vars to be configured.
REM
REM Requirements:
REM  - venv\ must exist at the repo root  (python -m venv venv)
REM  - cd frontend && npm install         (run once before first launch)

cd /d "%~dp0"

REM ── Backend: FastAPI (production server — no reload) ────────────
start "FastAPI Backend" cmd /k "call venv\Scripts\activate.bat && cd backend && python -m uvicorn app.main:app --port 8000"

REM ── Frontend: PRODUCTION build, then serve it ─────────────────
start "Next.js Frontend (prod)" cmd /k "cd frontend && npm run build && npm start"

echo.
echo  PRODUCTION mode starting in two windows.
echo  Backend  -^>  http://localhost:8000
echo  API docs -^>  http://localhost:8000/docs
echo  Frontend -^>  http://localhost:3000   ^(builds first ~30s, then serves prod^)
echo.
pause
