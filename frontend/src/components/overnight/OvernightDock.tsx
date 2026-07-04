"use client";

/**
 * OvernightDock — a persistent floating indicator for an active overnight
 * session. Sits bottom-right (RunProgressDock owns bottom-left) and exposes a
 * single Stop control so the loop can be halted from anywhere in the app.
 */

import { useEffect, useState } from "react";
import { Moon, Square } from "lucide-react";
import { useOvernight } from "@/components/overnight/OvernightContext";

function formatElapsed(ms: number): string {
  const total = Math.max(0, Math.floor(ms / 1000));
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  if (h > 0) return `${h}h ${m}m`;
  if (m > 0) return `${m}m ${s}s`;
  return `${s}s`;
}

export function OvernightDock() {
  const { status, stop } = useOvernight();
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    if (!status.running) return;
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, [status.running]);

  if (!status.running) return null;

  const elapsed = status.startedAt ? formatElapsed(now - status.startedAt) : "0s";
  const position = status.tickers.length
    ? `${Math.min(status.currentIndex + 1, status.tickers.length)}/${status.tickers.length}`
    : "—";

  return (
    <div
      className="fixed bottom-4 right-4 z-50 w-[300px] max-w-[calc(100vw-2rem)] rounded-2xl border border-border bg-background/95 shadow-xl backdrop-blur"
      role="status"
      aria-live="polite"
    >
      <div className="flex items-center gap-2 border-b border-border px-3 py-2">
        <Moon className="size-4" style={{ color: "var(--al-gold)" }} aria-hidden />
        <span className="text-xs font-semibold">
          Overnight {status.mode === "loop" ? "loop" : "run"} active
        </span>
        <button
          type="button"
          onClick={stop}
          className="ml-auto inline-flex items-center gap-1 rounded-md border border-border px-2 py-0.5 text-[11px] font-semibold text-red-600 hover:bg-muted dark:text-red-400"
          aria-label="Stop overnight session"
        >
          <Square className="size-3" aria-hidden /> Stop
        </button>
      </div>

      <div className="px-3 py-2 text-[11px]" style={{ color: "var(--al-on-surface-muted)" }}>
        <div className="flex items-center justify-between">
          <span>
            {status.currentTicker ? (
              <>
                Analysing <span className="font-mono font-semibold text-foreground">{status.currentTicker}</span>
              </>
            ) : (
              "Preparing next ticker…"
            )}
          </span>
          <span>{position}</span>
        </div>
        <div className="mt-1 flex items-center justify-between">
          <span>
            {status.mode === "loop" ? `Cycle ${status.cycle}` : "Single pass"} · {elapsed}
          </span>
          <span>
            <span className="text-green-600 dark:text-green-400">{status.completedRuns} done</span>
            {status.failedRuns > 0 ? (
              <span className="text-red-600 dark:text-red-400"> · {status.failedRuns} failed</span>
            ) : null}
          </span>
        </div>
        {status.lastError ? (
          <div className="mt-1 truncate text-amber-600 dark:text-amber-400" title={status.lastError}>
            {status.lastError}
          </div>
        ) : null}
      </div>
    </div>
  );
}
