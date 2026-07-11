"""
Point-in-time model backtest — DeepSeek V4 Pro vs V4 Flash vs Gemma-4-31B.

For each (model x ticker x cutoff) it runs the REAL analysis pipeline frozen to
the cutoff date (no lookahead: as-of prices/technicals + dated vector-store
news, no filings/macro, no RAG, no DB writes), then grades:

  * Prediction accuracy : predicted direction vs the ACTUAL move the following
                          week (forward_return).
  * Reasoning depth     : existing LLM-as-judge rubric (1-5).
  * Speed               : wall-clock + summed node LLM time.
  * Cost                : tokens x published per-token price.

Part B is a controlled head-to-head: the SAME fixed prompt through each model
(removes pipeline variance) for a clean speed/tokens/cost/depth comparison.

Outputs a full-provenance Markdown report + a raw JSON sidecar.

Usage:
    python -m evals.run_backtest --smoke      # 1 cell, validates the machinery
    python -m evals.run_backtest              # full 3 x 3 x 3 = 27 cells + Part B
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

# ── Repo-root importable + load env, but DISABLE Langfuse for clean timing ──
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(ROOT / ".env")
# Drop tracing keys BEFORE importing the pipeline so LANGFUSE_ENABLED=False:
os.environ.pop("LANGFUSE_PUBLIC_KEY", None)
os.environ.pop("LANGFUSE_SECRET_KEY", None)

from agents.llm_client import (  # noqa: E402
    llm_credentials_override, call_llm,
    set_call_extra_body, reset_token_meter, get_token_meter,
)
from workflows.weekly_analysis import _run_sector_graph  # noqa: E402
from evals.llm_judge import run_llm_judge  # noqa: E402
from evals.point_in_time import forward_return  # noqa: E402
from models.state import PipelineState  # noqa: E402

DEEPSEEK_BASE = "https://api.deepseek.com"
OPENROUTER_BASE = "https://openrouter.ai/api/v1"

# DeepSeek V4 defaults to (slow) thinking mode; disable it so the batch is
# tractable and the latency/cost comparison is apples-to-apples with Gemma
# (which has no thinking mode). Called out as a caveat in the report.
DEEPSEEK_THINKING_OFF = {"thinking": {"type": "disabled"}}

# Published per-1M-token pricing (input cache-miss / output). Sources:
#   DeepSeek: https://api-docs.deepseek.com/quick_start/pricing
#   Gemma:    OpenRouter /models endpoint (fetched live)
MODELS = [
    {"id": "deepseek-v4-pro",     "label": "DeepSeek V4 Pro",       "key_env": "DEEPSEEK_API_KEY",   "base": DEEPSEEK_BASE,   "in": 0.435, "out": 0.87, "extra_body": DEEPSEEK_THINKING_OFF},
    {"id": "deepseek-v4-flash",   "label": "DeepSeek V4 Flash",     "key_env": "DEEPSEEK_API_KEY",   "base": DEEPSEEK_BASE,   "in": 0.14,  "out": 0.28, "extra_body": DEEPSEEK_THINKING_OFF},
    {"id": "google/gemma-4-31b-it", "label": "Gemma 4 31B (OpenRouter)", "key_env": "OPENROUTER_API_KEY", "base": OPENROUTER_BASE, "in": 0.12,  "out": 0.35, "extra_body": None},
]
# Fixed, independent judge for reasoning-depth (same for all candidates).
JUDGE = {"id": "deepseek-v4-pro", "key_env": "DEEPSEEK_API_KEY", "base": DEEPSEEK_BASE, "extra_body": DEEPSEEK_THINKING_OFF}

TICKERS = [
    ("NVDA", "NVIDIA", "Semiconductors / AI"),
    ("TSLA", "Tesla", "Automotive / EV"),
    ("LLY", "Eli Lilly", "Pharmaceuticals"),
]
CUTOFFS = ["2026-06-11", "2026-06-18", "2026-06-25"]

OUT_DIR = ROOT / "evals" / "backtest_results"


# ── Helpers ────────────────────────────────────────────────────────

def make_sector(ticker: str, company: str, sector_name: str) -> dict:
    return {
        "name": f"{ticker} — {company}",
        "description": f"{company} ({ticker}) — {sector_name}.",
        "tickers": [ticker],
        "keywords": [ticker, company] + [w for w in company.split() if len(w) > 2],
        "supply_chain_map": {},
    }


def cost_usd(model: dict, prompt_tok: int, completion_tok: int) -> float:
    return round(prompt_tok / 1e6 * model["in"] + completion_tok / 1e6 * model["out"], 6)


def judge_depth_1to5(judge: dict) -> float | None:
    v = judge.get("judge_reasoning_depth")
    return round(v * 4 + 1, 2) if isinstance(v, (int, float)) else None


def node_path(state) -> list[dict]:
    out = []
    for n in getattr(state, "node_executions", []) or []:
        out.append({
            "node": n.node_name,
            "status": n.status,
            "seconds": round(n.duration_seconds, 2),
            "model": n.llm_model,
            "in_tok": n.llm_prompt_tokens,
            "out_tok": n.llm_completion_tokens,
            "decision": n.decision,
            "prompt": (n.llm_user_prompt or "")[:4000],
            "response": (n.llm_raw_response or "")[:6000],
        })
    return out


# ── Part A: one point-in-time pipeline cell ────────────────────────

def run_cell(model: dict, ticker: str, company: str, sector_name: str, cutoff: str) -> dict:
    sector = make_sector(ticker, company, sector_name)
    key = os.getenv(model["key_env"], "")
    rec: dict = {
        "model": model["id"], "model_label": model["label"],
        "ticker": ticker, "company": company, "sector": sector_name, "cutoff": cutoff,
    }
    t0 = time.time()
    try:
        with llm_credentials_override(api_key=key, base_url=model["base"], model=model["id"]):
            set_call_extra_body(model.get("extra_body"))
            reset_token_meter()
            state = _run_sector_graph(
                f"{ticker.lower()}_bt", sector,
                agent_name="Backtest",
                max_fetch_retries=0, max_validation_retries=0,
                as_of_date=cutoff,
            )
            pin, pout = get_token_meter()
            set_call_extra_body(None)
    except Exception as e:
        set_call_extra_body(None)
        rec["error"] = f"pipeline: {e}"
        rec["wall_seconds"] = round(time.time() - t0, 2)
        return rec
    rec["wall_seconds"] = round(time.time() - t0, 2)

    preds = getattr(state, "ai_predictions", None) or []
    pred = next((p for p in preds if p.get("ticker") == ticker), preds[0] if preds else None)
    rec["predicted_direction"] = (pred or {}).get("direction")
    rec["predicted_change"] = (pred or {}).get("predicted_change", "")
    rec["reasoning"] = (pred or {}).get("reasoning", "")
    rec["key_risk"] = (pred or {}).get("key_risk", "")
    rec["analysis_excerpt"] = (getattr(state, "analysis_text", "") or "")[:1400]
    rec["analysis_full"] = getattr(state, "analysis_text", "") or ""
    rec["validation_status"] = getattr(state, "validation_status", "")
    rec["validation_issues"] = getattr(state, "validation_issues", []) or []
    rec["confidence_score"] = getattr(state, "confidence_score", None)
    rec["prompt_tokens"] = pin
    rec["completion_tokens"] = pout
    rec["llm_seconds"] = round(sum(
        n.duration_seconds for n in (getattr(state, "node_executions", []) or [])
        if (n.llm_prompt_tokens or n.llm_completion_tokens)
    ), 2)
    rec["articles_used"] = len(getattr(state, "articles", []) or [])
    rec["node_path"] = node_path(state)
    rec["cost_usd"] = cost_usd(model, rec["prompt_tokens"], rec["completion_tokens"])

    # Reasoning depth via fixed independent judge
    try:
        with llm_credentials_override(api_key=os.getenv(JUDGE["key_env"], ""), base_url=JUDGE["base"], model=JUDGE["id"]):
            set_call_extra_body(JUDGE.get("extra_body"))
            judge = run_llm_judge(state)
            set_call_extra_body(None)
        rec["judge"] = judge
        rec["reasoning_depth_1to5"] = judge_depth_1to5(judge)
    except Exception as e:
        rec["judge_error"] = str(e)

    # Actual outcome the following week
    fwd = forward_return(ticker, cutoff, days=7)
    rec["actual"] = fwd
    if fwd and rec.get("predicted_direction"):
        rec["hit"] = rec["predicted_direction"] == fwd["actual_direction"]
    else:
        rec["hit"] = None
    return rec


# ── Part B: identical fixed prompt through each model ──────────────

PART_B_SYSTEM = (
    "You are a senior equity analyst. Be rigorous, cite the given data, and "
    "avoid inventing numbers. End with a '## PRICE PREDICTIONS' section."
)
PART_B_PROMPT = (
    "Using ONLY the data below, analyse NVDA and give a 1-week directional call.\n\n"
    "DATA (as of 2026-06-18):\n"
    "- Price: $141.20 | 1w change: +4.1% | 1m change: +11.8%\n"
    "- RSI(14): 63 | MACD: bullish crossover | above SMA20 and SMA50\n"
    "- Volume: 1.28x the 20-day average\n"
    "- Headlines: (1) hyperscaler capex guidance raised; (2) a peer flagged "
    "packaging (CoWoS) capacity tightness; (3) new export-rule headlines on advanced chips.\n\n"
    "Deliver: (1) a 3-4 sentence thesis, (2) one key catalyst, (3) one key risk, "
    "(4) a '## PRICE PREDICTIONS' section with the line: "
    "**NVDA**: BULLISH|BEARISH|NEUTRAL | Expected move: +/-X%"
)


def run_part_b(model: dict) -> dict:
    key = os.getenv(model["key_env"], "")
    rec = {"model": model["id"], "model_label": model["label"]}
    t0 = time.time()
    try:
        with llm_credentials_override(api_key=key, base_url=model["base"], model=model["id"]):
            set_call_extra_body(model.get("extra_body"))
            reset_token_meter()
            content = call_llm(prompt=PART_B_PROMPT, system_prompt=PART_B_SYSTEM,
                               temperature=0.3, max_tokens=1200)
            pin, pout = get_token_meter()
            set_call_extra_body(None)
        rec["seconds"] = round(time.time() - t0, 2)
        rec["prompt_tokens"] = pin
        rec["completion_tokens"] = pout
        rec["cost_usd"] = cost_usd(model, pin, pout)
        rec["output"] = (content or "")[:4000]
        # Reasoning depth on the fixed-prompt output
        st = PipelineState(sector_name="NVDA fixed-prompt", sector_tickers=["NVDA"])
        st.analysis_text = content or ""
        with llm_credentials_override(api_key=os.getenv(JUDGE["key_env"], ""), base_url=JUDGE["base"], model=JUDGE["id"]):
            set_call_extra_body(JUDGE.get("extra_body"))
            judge = run_part_b_judge(st)
            set_call_extra_body(None)
        rec["reasoning_depth_1to5"] = judge_depth_1to5(judge)
        rec["judge"] = judge
    except Exception as e:
        set_call_extra_body(None)
        rec["error"] = str(e)
        rec["seconds"] = round(time.time() - t0, 2)
    return rec


def run_part_b_judge(state) -> dict:
    try:
        return run_llm_judge(state)
    except Exception:
        return {}


# ── Aggregation + Markdown ─────────────────────────────────────────

def _avg(nums: list) -> float | None:
    nums = [n for n in nums if isinstance(n, (int, float))]
    return round(sum(nums) / len(nums), 2) if nums else None


def summarise(results_a: list[dict]) -> dict:
    by_model: dict[str, dict] = {}
    for m in MODELS:
        cells = [r for r in results_a if r["model"] == m["id"] and "error" not in r]
        graded = [r for r in cells if r.get("hit") is not None]
        hits = [r for r in graded if r["hit"]]
        by_model[m["id"]] = {
            "label": m["label"],
            "runs": len(cells),
            "graded": len(graded),
            "hits": len(hits),
            "hit_rate": round(len(hits) / len(graded) * 100, 1) if graded else None,
            "avg_depth": _avg([r.get("reasoning_depth_1to5") for r in cells]),
            "avg_wall": _avg([r.get("wall_seconds") for r in cells]),
            "avg_tok": _avg([(r.get("prompt_tokens", 0) + r.get("completion_tokens", 0)) for r in cells]),
            "total_cost": round(sum(r.get("cost_usd", 0) for r in cells), 4),
            "avg_cost": round(sum(r.get("cost_usd", 0) for r in cells) / len(cells), 5) if cells else None,
        }
    return by_model


def write_report(results_a: list[dict], results_b: list[dict], stamp: str) -> Path:
    summ = summarise(results_a)
    md: list[str] = []
    A = md.append

    A(f"# Model Backtest — DeepSeek V4 Pro vs V4 Flash vs Gemma-4-31B\n")
    A(f"> Generated: {datetime.now().isoformat(timespec='seconds')}  ")
    A(f"> Point-in-time backtest · 3 models × {len(TICKERS)} tickers × {len(CUTOFFS)} cutoffs = "
      f"{len(MODELS) * len(TICKERS) * len(CUTOFFS)} runs, plus a controlled Part B.\n")

    A("## Methodology\n")
    A("For each **(model, ticker, cutoff)** the REAL analysis pipeline was run frozen to the "
      "cutoff date — **no lookahead**:\n")
    A("- **Prices & technicals**: Yahoo Finance history truncated to on/before the cutoff.\n")
    A("- **News**: only vector-store articles *published ≤ cutoff* (RSS is live-only and cannot be time-travelled).\n")
    A("- **Excluded** (cannot be cleanly reconstructed as-of): SEC filings, FRED macro, and RAG historical context.\n")
    A("- **No DB writes** — backtest runs never touch the live database or vector store.\n")
    A("- The model's **predicted direction** is graded against the **actual close ~7 calendar days later** "
      "(BULLISH >+1%, BEARISH <−1%, else NEUTRAL).\n")
    A("- **Reasoning depth** scored 1–5 by a fixed independent LLM judge (deepseek-v4-pro).\n")
    A("- **Cost** = tokens × published price (DeepSeek cache-miss input; Gemma via OpenRouter).\n")

    A("\n## Executive summary\n")
    A("| Model | Runs | Dir. accuracy | Avg reasoning depth (1–5) | Avg speed (s) | Avg tokens/run | Total cost | Avg cost/run |")
    A("|---|---|---|---|---|---|---|---|")
    for m in MODELS:
        s = summ[m["id"]]
        acc = f"{s['hit_rate']}% ({s['hits']}/{s['graded']})" if s["hit_rate"] is not None else "n/a"
        A(f"| {s['label']} | {s['runs']} | {acc} | {s['avg_depth']} | {s['avg_wall']} | "
          f"{int(s['avg_tok']) if s['avg_tok'] else 'n/a'} | ${s['total_cost']} | ${s['avg_cost']} |")

    # Per-ticker directional tables
    A("\n## Part A — prediction accuracy by ticker\n")
    for tk, company, sec in TICKERS:
        A(f"\n### {tk} — {company} ({sec})\n")
        A("| Cutoff | Actual next-wk | " + " | ".join(m["label"] for m in MODELS) + " |")
        A("|---|---|" + "|".join(["---"] * len(MODELS)) + "|")
        for cut in CUTOFFS:
            fwd = next((r.get("actual") for r in results_a
                        if r["ticker"] == tk and r["cutoff"] == cut and r.get("actual")), None)
            actual_txt = f"{fwd['actual_direction']} ({fwd['change_pct']:+.1f}%)" if fwd else "n/a"
            cells_txt = []
            for m in MODELS:
                r = next((x for x in results_a if x["model"] == m["id"] and x["ticker"] == tk and x["cutoff"] == cut), None)
                if not r or "error" in r:
                    cells_txt.append("error")
                    continue
                d = r.get("predicted_direction") or "—"
                hit = r.get("hit")
                mark = "✅" if hit else ("❌" if hit is False else "•")
                cells_txt.append(f"{d} {mark}")
            A(f"| {cut} | {actual_txt} | " + " | ".join(cells_txt) + " |")

    # Part B
    A("\n## Part B — controlled identical-prompt comparison\n")
    A("Same fixed NVDA prompt through each model (removes pipeline variance).\n")
    A("| Model | Speed (s) | Prompt tok | Completion tok | Cost | Reasoning depth (1–5) |")
    A("|---|---|---|---|---|---|")
    for r in results_b:
        if "error" in r:
            A(f"| {r['model_label']} | {r.get('seconds')} | — | — | — | error: {r['error'][:40]} |")
        else:
            A(f"| {r['model_label']} | {r['seconds']} | {r['prompt_tokens']} | {r['completion_tokens']} | "
              f"${r['cost_usd']} | {r.get('reasoning_depth_1to5')} |")

    # Full provenance ("the path it took")
    A("\n## Part A — full path (provenance) per run\n")
    A("Each run lists its pipeline node timeline (the exact path taken), the prediction, the "
      "graded outcome, and the model's reasoning. Full prompts/responses are in the JSON sidecar.\n")
    for tk, company, sec in TICKERS:
        for cut in CUTOFFS:
            A(f"\n### {tk} @ {cut}\n")
            for m in MODELS:
                r = next((x for x in results_a if x["model"] == m["id"] and x["ticker"] == tk and x["cutoff"] == cut), None)
                if not r:
                    continue
                A(f"\n**{m['label']}**  ")
                if "error" in r:
                    A(f"\n> ⚠️ error: {r['error']}\n")
                    continue
                fwd = r.get("actual") or {}
                hit = r.get("hit")
                mark = "HIT ✅" if hit else ("MISS ❌" if hit is False else "n/a")
                A(f"\n- Prediction: **{r.get('predicted_direction')}** "
                  f"(expected {r.get('predicted_change') or 'n/a'}) → actual "
                  f"{fwd.get('actual_direction','n/a')} ({fwd.get('change_pct','n/a')}%) — **{mark}**  ")
                A(f"- Validation: {r.get('validation_status')} · "
                  f"{len(r.get('validation_issues', []))} numeric issue(s) · "
                  f"confidence {r.get('confidence_score')}/10 · depth {r.get('reasoning_depth_1to5')}/5  ")
                A(f"- Speed {r.get('wall_seconds')}s · tokens {r.get('prompt_tokens')}→{r.get('completion_tokens')} · "
                  f"cost ${r.get('cost_usd')} · {r.get('articles_used')} archived articles  ")
                # node timeline
                path = " → ".join(
                    f"{n['node']}({n['seconds']}s)" for n in r.get("node_path", [])
                )
                A(f"- Path: {path}  ")
                excerpt = (r.get("reasoning") or r.get("analysis_excerpt") or "").strip().replace("\n", " ")
                if excerpt:
                    A(f"- Reasoning: {excerpt[:500]}  ")

    A("\n## Caveats\n")
    A("- **News coverage varies by ticker**: the vector store is AI/semiconductor-heavy, so NVDA has "
      "the richest point-in-time news; TSLA/LLY lean more on technicals. Coverage counts are shown per run.\n")
    A("- **Judge self-preference**: the reasoning-depth judge is deepseek-v4-pro, one of the candidates; "
      "treat depth as indicative. Directional accuracy is objective and judge-independent.\n")
    A("- **No filings/macro as-of**: excluded to avoid lookahead; analyses are news+price+technical driven.\n")
    A("- **Pricing**: DeepSeek cache-miss input rate used (cache hits would be cheaper). Gemma via OpenRouter.\n")
    A(f"\n---\n*Raw data (full prompts, responses, tokens): `{OUT_DIR.name}/backtest_raw_{stamp}.json`*\n")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    md_path = OUT_DIR / f"backtest_report_{stamp}.md"
    md_path.write_text("\n".join(md), encoding="utf-8")
    return md_path


# ── Main ───────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true", help="Run a single cell to validate the machinery.")
    ap.add_argument("--skip-b", action="store_true", help="Skip Part B.")
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    raw_path = OUT_DIR / f"backtest_raw_{stamp}.json"

    models = MODELS[:1] if args.smoke else MODELS
    tickers = TICKERS[:1] if args.smoke else TICKERS
    cutoffs = CUTOFFS[:1] if args.smoke else CUTOFFS

    results_a: list[dict] = []
    total = len(models) * len(tickers) * len(cutoffs)
    i = 0
    for m in models:
        for tk, company, sec in tickers:
            for cut in cutoffs:
                i += 1
                print(f"[{i}/{total}] {m['id']} · {tk} @ {cut} ...", flush=True)
                rec = run_cell(m, tk, company, sec, cut)
                results_a.append(rec)
                status = rec.get("error") or f"{rec.get('predicted_direction')} vs {(rec.get('actual') or {}).get('actual_direction')} ({rec.get('wall_seconds')}s, ${rec.get('cost_usd')})"
                print(f"       -> {status}", flush=True)
                raw_path.write_text(json.dumps({"part_a": results_a}, indent=2, default=str), encoding="utf-8")

    results_b: list[dict] = []
    if not args.skip_b:
        for m in models:
            print(f"[Part B] {m['id']} ...", flush=True)
            results_b.append(run_part_b(m))
            raw_path.write_text(json.dumps({"part_a": results_a, "part_b": results_b}, indent=2, default=str), encoding="utf-8")

    md_path = write_report(results_a, results_b, stamp)
    print(f"\nReport:  {md_path}")
    print(f"Raw:     {raw_path}")


if __name__ == "__main__":
    main()
