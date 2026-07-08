"""
Prepare the demo with REAL analyst-board runs.

Unlike ``scripts/seed_db.py`` (which inserts *mock* rows for local UI testing),
this script drives the **real** pipeline through the running backend API, so
every resulting signal card, chief verdict, validation score and supply-chain
read a grader sees is genuine and defensible.

It runs the full Board of Analysts on each starter ticker, one ticker at a time,
and polls each run to completion so you can watch the app fill up with real data
before you present.

Prerequisites
-------------
1. Backend running:
       cd backend && python -m uvicorn app.main:app --port 8000
2. An LLM configured in ``../.env`` — either your own key
   (``OPENROUTER_API_KEY=...``) or local Ollama (``LLM_PROVIDER=ollama``).
3. (Optional) Frontend running so you can watch the cards appear live.

Usage (venv activated, run from backend/)
-----------------------------------------
    python scripts/prepare_demo.py                     # default starter tickers
    python scripts/prepare_demo.py NVDA TSM AMD        # a custom ticker list
    python scripts/prepare_demo.py --model deepseek/deepseek-chat
    python scripts/prepare_demo.py --sector us_technology

Notes
-----
* A full board can take several minutes per ticker — this is normal; the
  analysts read live news, filings, prices and macro before answering.
* HTTP 429 (daily quota) → set ``DAILY_RUN_QUOTA=0`` in ``../.env`` and rerun.
* HTTP 503 (LLM) → configure ``OPENROUTER_API_KEY`` or start Ollama, then rerun.
* Auth: in local dev (``APP_ENV=development``) the backend attributes runs to
  ``test@example.com`` automatically. For a secured instance, pass a session
  cookie via ``PREPARE_DEMO_COOKIE="session=<token>"``.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

# ── Load .env from repo root (so PREPARE_DEMO_* / local config resolve) ─────────
_BACKEND = Path(__file__).resolve().parents[1]
_REPO_ROOT = _BACKEND.parent
try:
    from dotenv import load_dotenv

    _env_path = _REPO_ROOT / ".env"
    if _env_path.exists():
        load_dotenv(_env_path, override=False)
except ImportError:  # python-dotenv optional — rely on real env vars
    pass

import httpx  # noqa: E402  (import after .env load for consistency with seed_db.py)

# Matches the starter chips on the frontend landing page so the guided beginner
# flow always lands on a ticker that already has a real board behind it.
STARTER_TICKERS = ["NVDA", "TSM", "AMD", "AVGO", "MSFT"]

API = "/api/v1"
TERMINAL_STATES = {"completed", "failed"}


def _build_client(base_url: str) -> httpx.Client:
    cookie = os.environ.get("PREPARE_DEMO_COOKIE", "").strip()
    headers: dict[str, str] = {}
    cookies: dict[str, str] = {}
    if cookie:
        if "=" in cookie and ";" not in cookie:
            name, _, value = cookie.partition("=")
            cookies[name.strip()] = value.strip()
        else:
            headers["Cookie"] = cookie
    return httpx.Client(base_url=base_url, headers=headers, cookies=cookies, timeout=30.0)


def _die(message: str) -> "None":
    print(f"\n[prepare_demo] ERROR: {message}", file=sys.stderr)
    sys.exit(1)


def _check_backend(client: httpx.Client) -> None:
    try:
        resp = client.get("/health")
        resp.raise_for_status()
    except Exception as exc:  # noqa: BLE001 — surface any connection/HTTP error
        _die(
            f"backend not reachable at {client.base_url} ({exc}).\n"
            "  Start it first:  cd backend && python -m uvicorn app.main:app --port 8000"
        )


def _launch_board(
    client: httpx.Client, ticker: str, model: str | None, sector: str | None
) -> list[dict]:
    """POST a board fanout for one ticker; return the launched run items."""
    body: dict[str, object] = {"ticker": ticker}
    if model:
        body["model"] = model
    if sector:
        body["sector_id"] = sector

    resp = client.post(f"{API}/pipeline/runs/fanout", json=body)
    if resp.status_code == 202:
        return resp.json().get("runs", [])

    # Friendly, actionable messages for the common failure modes.
    try:
        detail = resp.json().get("detail", resp.text)
    except Exception:  # noqa: BLE001
        detail = resp.text
    if resp.status_code == 503:
        _die(f"LLM provider not ready: {detail}\n  Set OPENROUTER_API_KEY in ../.env or start Ollama.")
    if resp.status_code == 429:
        _die(f"Rate/quota limit: {detail}\n  Set DAILY_RUN_QUOTA=0 in ../.env and rerun.")
    if resp.status_code == 401:
        _die(f"Unauthorized: {detail}\n  Set APP_ENV=development locally, or pass PREPARE_DEMO_COOKIE.")
    _die(f"fanout failed for {ticker} (HTTP {resp.status_code}): {detail}")
    return []  # unreachable — _die exits


def _run_status(client: httpx.Client, run_id: str) -> dict:
    resp = client.get(f"{API}/pipeline/runs/{run_id}")
    if resp.status_code != 200:
        return {"status": "unknown", "signal_card_id": None}
    return resp.json()


def _poll_to_completion(
    client: httpx.Client, runs: list[dict], timeout: int, interval: int
) -> list[dict]:
    """Poll every run for a ticker until all terminal or the timeout elapses."""
    run_ids = [r["run_id"] for r in runs]
    names = {r["run_id"]: r.get("agent_name", f"agent {r.get('agent_id')}") for r in runs}
    deadline = time.monotonic() + timeout
    results: dict[str, dict] = {}

    while time.monotonic() < deadline:
        pending = [rid for rid in run_ids if rid not in results]
        for rid in pending:
            row = _run_status(client, rid)
            if row.get("status") in TERMINAL_STATES:
                results[rid] = row

        done = len(results)
        line = "  ".join(
            f"{names[rid][:16]}:{'ok' if results.get(rid, {}).get('signal_card_id') else results[rid]['status'] if rid in results else '…'}"
            for rid in run_ids
        )
        print(f"    [{done}/{len(run_ids)}] {line}")
        if done == len(run_ids):
            break
        time.sleep(interval)

    # Anything still unresolved is reported as a timeout.
    for rid in run_ids:
        results.setdefault(rid, {"status": "timeout", "signal_card_id": None})
    return [{"run_id": rid, "agent_name": names[rid], **results[rid]} for rid in run_ids]


def main() -> None:
    parser = argparse.ArgumentParser(description="Run real analyst-board analyses to prepare a demo.")
    parser.add_argument("tickers", nargs="*", default=None, help="Tickers to analyse (default: starter set).")
    parser.add_argument("--model", default=None, help="Optional per-run model override (must be allowed unless BYO key).")
    parser.add_argument("--sector", default=None, help="Optional sector id override (else inferred).")
    parser.add_argument("--base-url", default=os.environ.get("PREPARE_DEMO_BASE_URL", "http://localhost:8000"))
    parser.add_argument("--timeout", type=int, default=900, help="Per-ticker timeout in seconds (default 900).")
    parser.add_argument("--poll-interval", type=int, default=5, help="Seconds between status polls (default 5).")
    args = parser.parse_args()

    tickers = [t.strip().upper() for t in (args.tickers or STARTER_TICKERS) if t.strip()]
    client = _build_client(args.base_url)

    print(f"[prepare_demo] target: {client.base_url}")
    _check_backend(client)
    print(f"[prepare_demo] running the analyst board on {len(tickers)} ticker(s): {', '.join(tickers)}")
    print("[prepare_demo] one ticker at a time — a full board takes a few minutes each.\n")

    summary: list[tuple[str, int, int]] = []
    for index, ticker in enumerate(tickers, start=1):
        print(f"[{index}/{len(tickers)}] {ticker}: launching the board…")
        runs = _launch_board(client, ticker, args.model, args.sector)
        if not runs:
            print(f"  {ticker}: no runs launched.")
            summary.append((ticker, 0, 0))
            continue
        outcomes = _poll_to_completion(client, runs, args.timeout, args.poll_interval)
        published = sum(1 for o in outcomes if o.get("signal_card_id"))
        print(f"  {ticker}: {published}/{len(outcomes)} analyst cards published.\n")
        summary.append((ticker, published, len(outcomes)))

    print("\n[prepare_demo] Summary")
    print("─" * 40)
    total_ok = total = 0
    for ticker, published, count in summary:
        total_ok += published
        total += count
        print(f"  {ticker:<10} {published}/{count} cards")
    print("─" * 40)
    print(f"  TOTAL      {total_ok}/{total} analyst cards published")
    print("\n[prepare_demo] Done. Open the app — the Decision Desk and signal list are now populated with real data.")


if __name__ == "__main__":
    main()
