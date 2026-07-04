"use client";

/**
 * RunProgressDock — a persistent, global floating indicator that shows
 * active analyst pipeline runs from anywhere in the app.
 *
 * It polls the pipeline runs endpoint and stays visible while any run is
 * pending/running, and briefly keeps just-finished or failed runs on screen
 * so a crash/error never makes progress silently disappear.
 */

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Loader2, CheckCircle2, AlertCircle, Minus, ArrowRight } from "lucide-react";
import { fetchRuns } from "@/lib/api";
import type { PipelineRun, RunStatus, RunSummary } from "@/types/api";
import { cn } from "@/lib/utils";
import {
  runProgressPct,
  estimateRemainingSeconds,
  formatDuration,
} from "@/lib/pipeline-progress";

// The dock polls the lightweight list endpoint (RunSummary), but the
// pipeline-progress helpers reason over the richer PipelineRun shape. A
// RunSummary carries everything the elapsed-based ETA needs (status,
// current_node, started_at/created_at); node_executions is simply absent,
// which the helpers treat as "no completed stages yet".
function asPipelineRun(run: RunSummary): PipelineRun {
  return {
    run_id: run.run_id,
    ticker: run.ticker,
    sector_id: run.sector_id,
    agent_id: run.agent_id ?? null,
    agent_name: run.agent_name ?? null,
    status: run.status,
    current_node: run.current_node ?? null,
    error: run.error ?? null,
    created_at: run.created_at,
    started_at: run.started_at ?? null,
    finished_at: run.finished_at,
    signal_card_id: run.signal_card_id,
    node_executions: [],
  };
}

const RECENT_WINDOW_MS = 90_000;

function isRecentlyFinished(run: RunSummary): boolean {
  if (run.status !== "completed" && run.status !== "failed") return false;
  const ts = run.finished_at ?? run.created_at;
  if (!ts) return false;
  const finished = new Date(ts).getTime();
  if (Number.isNaN(finished)) return false;
  return Date.now() - finished < RECENT_WINDOW_MS;
}

export function RunProgressDock() {
  const [dismissed, setDismissed] = useState<Set<string>>(() => new Set());
  const [minimized, setMinimized] = useState(false);
  const [now, setNow] = useState(() => Date.now());

  const runs = useQuery({
    queryKey: ["runs", "dock"],
    queryFn: () => fetchRuns({ page: 1, page_size: 20 }),
    retry: false,
    refetchInterval: (query) => {
      const items = query.state.data?.items ?? [];
      const anyActive = items.some(
        (r) => r.status === "pending" || r.status === "running"
      );
      return anyActive ? 2500 : 15000;
    },
  });

  const items = useMemo(() => runs.data?.items ?? [], [runs.data]);

  const active = useMemo(
    () => items.filter((r) => r.status === "pending" || r.status === "running"),
    [items]
  );
  const recentlyDone = useMemo(
    () => items.filter((r) => isRecentlyFinished(r) && !dismissed.has(r.run_id)),
    // `now` forces re-evaluation as the recent window elapses
    [items, dismissed, now] // eslint-disable-line react-hooks/exhaustive-deps
  );

  // Tick so the "recently finished" window expires without a refetch, and so
  // the live ETA counts down smoothly between polls.
  useEffect(() => {
    if (recentlyDone.length === 0 && active.length === 0) return;
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, [recentlyDone.length, active.length]);

  // When new active runs appear, clear stale dismissals so the dock returns.
  useEffect(() => {
    if (active.length > 0 && dismissed.size > 0) {
      setDismissed(new Set());
    }
  }, [active.length]); // eslint-disable-line react-hooks/exhaustive-deps

  const visible = useMemo<RunSummary[]>(() => {
    const map = new Map<string, RunSummary>();
    for (const r of active) map.set(r.run_id, r);
    for (const r of recentlyDone) map.set(r.run_id, r);
    return Array.from(map.values());
  }, [active, recentlyDone]);

  if (visible.length === 0) return null;

  const total = visible.length;
  const done = visible.filter((r) => r.status === "completed").length;
  const failed = visible.filter((r) => r.status === "failed").length;
  const running = active.length;
  const nowDate = new Date(now);
  const overallPct = Math.round(
    visible.reduce((sum, r) => sum + runProgressPct(asPipelineRun(r)), 0) / total
  );

  // Live ETA: the longest remaining time across the still-active runs, since
  // the batch is only "done" once the slowest run finishes.
  const remainingSeconds = active.reduce<number | null>((longest, r) => {
    const eta = estimateRemainingSeconds(asPipelineRun(r), nowDate);
    if (eta == null) return longest;
    return longest == null ? eta : Math.max(longest, eta);
  }, null);
  const etaLabel =
    running > 0
      ? remainingSeconds != null
        ? `~${formatDuration(remainingSeconds)} left`
        : "Estimating finish"
      : null;

  const headline =
    running > 0
      ? `Analyzing — ${running} run${running === 1 ? "" : "s"} active`
      : failed > 0 && done === 0
        ? `${failed} run${failed === 1 ? "" : "s"} failed`
        : `${done} run${done === 1 ? "" : "s"} ready`;

  const statusTint: Record<RunStatus, string> = {
    pending: "var(--al-gold)",
    running: "var(--al-gold)",
    completed: "#16a34a",
    failed: "#dc2626",
  };

  // Collapsed state — a small floating ball that keeps the loading signal
  // visible without taking up screen space. Click it to restore the panel.
  if (minimized) {
    return (
      <button
        type="button"
        onClick={() => setMinimized(false)}
        className="fixed bottom-4 left-4 z-50 grid size-12 place-items-center rounded-full border border-border bg-background/95 shadow-xl backdrop-blur transition hover:scale-105"
        aria-label={`${headline}${etaLabel ? ` · ${etaLabel}` : ""} — expand progress`}
        title={`${headline}${etaLabel ? ` · ${etaLabel}` : ""}`}
      >
        {running > 0 ? (
          <Loader2 className="size-5 animate-spin" style={{ color: "var(--al-gold)" }} aria-hidden />
        ) : failed > 0 && done === 0 ? (
          <AlertCircle className="size-5 text-red-600" aria-hidden />
        ) : (
          <CheckCircle2 className="size-5 text-green-600" aria-hidden />
        )}
        <span
          className="absolute -right-1 -top-1 grid min-w-[18px] place-items-center rounded-full px-1 text-[10px] font-bold text-white"
          style={{ background: running > 0 ? "var(--al-gold)" : failed > 0 && done === 0 ? "#dc2626" : "#16a34a" }}
          aria-hidden
        >
          {running > 0 ? running : total}
        </span>
      </button>
    );
  }

  return (
    <div
      className="fixed bottom-4 left-4 z-50 w-[320px] max-w-[calc(100vw-2rem)] rounded-2xl border border-border bg-background/95 shadow-xl backdrop-blur"
      role="status"
      aria-live="polite"
    >
      <div className="flex items-center gap-2 border-b border-border px-3 py-2">
        {running > 0 ? (
          <Loader2 className="size-4 animate-spin" style={{ color: "var(--al-gold)" }} aria-hidden />
        ) : failed > 0 && done === 0 ? (
          <AlertCircle className="size-4 text-red-600" aria-hidden />
        ) : (
          <CheckCircle2 className="size-4 text-green-600" aria-hidden />
        )}
        <span className="text-xs font-semibold">{headline}</span>
        {etaLabel && (
          <span className="text-[10px] font-medium text-muted-foreground tabular-nums">
            {etaLabel}
          </span>
        )}
        <button
          type="button"
          onClick={() => setMinimized(true)}
          className="ml-auto rounded-md p-1 text-muted-foreground hover:bg-muted"
          aria-label="Minimize progress"
          title="Minimize"
        >
          <Minus className="size-3.5" aria-hidden />
        </button>
      </div>

      <div className="px-3 py-2">
        <div className="mb-2 h-1.5 w-full overflow-hidden rounded-full bg-muted">
          <div
            className="h-full rounded-full transition-all"
            style={{
              width: `${overallPct}%`,
              background: failed > 0 && running === 0 && done === 0 ? "#dc2626" : "var(--al-gold)",
            }}
          />
        </div>

        <ul className="max-h-40 space-y-1 overflow-y-auto">
          {visible.slice(0, 6).map((run) => {
            const label = (
              <>
                <span
                  className="inline-block size-1.5 shrink-0 rounded-full"
                  style={{ background: statusTint[run.status] }}
                  aria-hidden
                />
                <span className="font-mono font-semibold">{run.ticker}</span>
                <span className="truncate text-muted-foreground">
                  {run.agent_name ?? "Analyst"}
                  {run.status === "running" && run.current_node ? ` · ${run.current_node}` : ""}
                  {run.status === "failed" ? " · failed" : ""}
                  {run.status === "completed" ? " · ready" : ""}
                </span>
              </>
            );
            return (
              <li key={run.run_id} className="text-[11px]">
                {run.status === "completed" && run.signal_card_id != null ? (
                  <Link
                    href={`/signals/${run.signal_card_id}`}
                    className="flex items-center gap-2 rounded-md px-1 py-0.5 hover:bg-muted"
                  >
                    {label}
                  </Link>
                ) : (
                  <div className="flex items-center gap-2 px-1 py-0.5">{label}</div>
                )}
              </li>
            );
          })}
        </ul>

        <Link
          href="/tickers"
          className={cn(
            "mt-2 inline-flex items-center gap-1 text-[11px] font-semibold hover:underline"
          )}
          style={{ color: "var(--al-gold)" }}
        >
          Open analysis board <ArrowRight className="size-3" aria-hidden />
        </Link>
      </div>
    </div>
  );
}
