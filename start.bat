@echo off
REM ── Supply Chain Alpha — Quick Start ──
REM Starts the FastAPI backend and Next.js frontend in two separate windows.
REM
REM  Window 1: FastAPI  → http://localhost:8000   (API docs: /docs)
REM  Window 2: Next.js  → http://localhost:3000
REM
REM Requirements:
REM  - venv\ must exist at the repo root  (python -m venv venv)
REM  - cd frontend && npm install         (run once before first launch)

cd /d "%~dp0"

REM ── Backend: FastAPI (uvicorn, reload on save) ─────────────────────
start "FastAPI Backend" cmd /k "call venv\Scripts\activate.bat && cd backend && python -m uvicorn app.main:app --reload --port 8000"

REM ── Frontend: Next.js dev server ──────────────────────────────────
start "Next.js Frontend" cmd /k "cd frontend && npm run dev"

echo.
echo  Both servers are starting in separate windows.
echo  Backend  -^>  http://localhost:8000
echo  API docs -^>  http://localhost:8000/docs
echo  Frontend -^>  http://localhost:3000
echo.
pause
