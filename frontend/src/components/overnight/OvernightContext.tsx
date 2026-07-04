"use client";

/**
 * OvernightContext — a browser-driven "run all night" controller.
 *
 * Two modes:
 *   • "loop"  — cycle through the chosen tickers on repeat until the user
 *               presses Stop. Ideal for leaving a watchlist analysing overnight.
 *   • "once"  — run the chosen ticker(s) a single time, then stop.
 *
 * The loop lives entirely in the browser so the user's own API key (sent per
 * request from localStorage) is never held server-side. Each ticker is launched
 * via the normal board fanout endpoint and we wait for those runs to finish
 * before moving to the next, so we never stampede the LLM provider.
 *
 * State + config are persisted to localStorage so a page reload resumes an
 * in-flight overnight session.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { useQueryClient } from "@tanstack/react-query";
import { fetchRun, triggerBoardRun } from "@/lib/api";

export type OvernightMode = "loop" | "once";

export interface OvernightConfig {
  mode: OvernightMode;
  tickers: string[];
  agentIds?: number[];
  model?: string;
  /** Pause between cycles in loop mode (ms). */
  cycleDelayMs: number;
}

export interface OvernightStatus {
  running: boolean;
  mode: OvernightMode | null;
  tickers: string[];
  currentTicker: string | null;
  currentIndex: number;
  cycle: number;
  completedRuns: number;
  failedRuns: number;
  startedAt: number | null;
  lastError: string | null;
}

interface OvernightContextValue {
  status: OvernightStatus;
  start: (config: OvernightConfig) => void;
  stop: () => void;
}

const STORAGE_KEY = "marketpulse-overnight";
const DEFAULT_CYCLE_DELAY_MS = 30_000;
// Don't wait on a single ticker's runs forever — move on after this long.
const PER_TICKER_TIMEOUT_MS = 15 * 60_000;
const POLL_INTERVAL_MS = 4_000;

const IDLE_STATUS: OvernightStatus = {
  running: false,
  mode: null,
  tickers: [],
  currentTicker: null,
  currentIndex: 0,
  cycle: 0,
  completedRuns: 0,
  failedRuns: 0,
  startedAt: null,
  lastError: null,
};

const OvernightContext = createContext<OvernightContextValue | null>(null);

function isTerminal(status: string): boolean {
  return status === "completed" || status === "failed";
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export function OvernightProvider({ children }: { children: React.ReactNode }) {
  const queryClient = useQueryClient();
  const [status, setStatus] = useState<OvernightStatus>(IDLE_STATUS);

  // Refs let the long-lived async loop read the latest control flags without
  // being recreated (which would restart the loop) on every render.
  const stopRef = useRef(false);
  const loopActiveRef = useRef(false);
  const completedRef = useRef(0);
  const failedRef = useRef(0);

  const persist = useCallback((next: OvernightStatus, config: OvernightConfig | null) => {
    try {
      if (next.running && config) {
        localStorage.setItem(
          STORAGE_KEY,
          JSON.stringify({ config, startedAt: next.startedAt })
        );
      } else {
        localStorage.removeItem(STORAGE_KEY);
      }
    } catch {
      /* ignore storage failures */
    }
  }, []);

  /** Poll the given run ids until all are terminal, stopped, or timed out. */
  const waitForRuns = useCallback(async (runIds: string[]) => {
    if (!runIds.length) return;
    const deadline = Date.now() + PER_TICKER_TIMEOUT_MS;
    const pending = new Set(runIds);
    while (pending.size && !stopRef.current && Date.now() < deadline) {
      await sleep(POLL_INTERVAL_MS);
      if (stopRef.current) return;
      for (const runId of [...pending]) {
        try {
          const run = await fetchRun(runId);
          if (isTerminal(run.status)) {
            pending.delete(runId);
            if (run.status === "completed") completedRef.current += 1;
            else failedRef.current += 1;
            setStatus((prev) => ({
              ...prev,
              completedRuns: completedRef.current,
              failedRuns: failedRef.current,
            }));
          }
        } catch {
          // Transient fetch error — keep polling until the deadline.
        }
      }
    }
  }, []);

  const runLoop = useCallback(
    async (config: OvernightConfig) => {
      if (loopActiveRef.current) return;
      loopActiveRef.current = true;
      stopRef.current = false;

      let cycle = 0;
      try {
        while (!stopRef.current) {
          cycle += 1;
          for (let i = 0; i < config.tickers.length; i += 1) {
            if (stopRef.current) break;
            const ticker = config.tickers[i];
            setStatus((prev) => ({
              ...prev,
              cycle,
              currentIndex: i,
              currentTicker: ticker,
            }));
            try {
              const resp = await triggerBoardRun({
                ticker,
                agent_ids: config.agentIds?.length ? config.agentIds : undefined,
                model: config.model || undefined,
              });
              queryClient.invalidateQueries({ queryKey: ["runs"] });
              await waitForRuns(resp.runs.map((run) => run.run_id));
              queryClient.invalidateQueries({ queryKey: ["runs"] });
              queryClient.invalidateQueries({ queryKey: ["signals"] });
            } catch (err) {
              setStatus((prev) => ({
                ...prev,
                lastError:
                  err instanceof Error ? err.message : `Failed to launch ${ticker}.`,
              }));
            }
          }

          if (config.mode === "once" || stopRef.current) break;

          // Brief pause between cycles, interruptible by Stop.
          const wakeAt = Date.now() + config.cycleDelayMs;
          while (Date.now() < wakeAt && !stopRef.current) {
            await sleep(Math.min(1000, wakeAt - Date.now()));
          }
        }
      } finally {
        loopActiveRef.current = false;
        setStatus((prev) => {
          const next = { ...prev, running: false, currentTicker: null };
          persist(next, null);
          return next;
        });
      }
    },
    [persist, queryClient, waitForRuns]
  );

  const start = useCallback(
    (config: OvernightConfig) => {
      const tickers = config.tickers.map((t) => t.trim().toUpperCase()).filter(Boolean);
      if (!tickers.length || loopActiveRef.current) return;
      completedRef.current = 0;
      failedRef.current = 0;
      const startedAt = Date.now();
      const next: OvernightStatus = {
        running: true,
        mode: config.mode,
        tickers,
        currentTicker: null,
        currentIndex: 0,
        cycle: 0,
        completedRuns: 0,
        failedRuns: 0,
        startedAt,
        lastError: null,
      };
      setStatus(next);
      const normalized = { ...config, tickers };
      persist(next, normalized);
      void runLoop(normalized);
    },
    [persist, runLoop]
  );

  const stop = useCallback(() => {
    stopRef.current = true;
    setStatus((prev) => {
      const next = { ...prev, running: false, currentTicker: null };
      persist(next, null);
      return next;
    });
  }, [persist]);

  // Resume an in-flight overnight session after a reload.
  useEffect(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return;
      const parsed = JSON.parse(raw) as {
        config?: OvernightConfig;
        startedAt?: number;
      };
      const config = parsed.config;
      if (!config || !Array.isArray(config.tickers) || !config.tickers.length) {
        localStorage.removeItem(STORAGE_KEY);
        return;
      }
      completedRef.current = 0;
      failedRef.current = 0;
      const startedAt = parsed.startedAt ?? Date.now();
      setStatus({
        running: true,
        mode: config.mode,
        tickers: config.tickers,
        currentTicker: null,
        currentIndex: 0,
        cycle: 0,
        completedRuns: 0,
        failedRuns: 0,
        startedAt,
        lastError: null,
      });
      void runLoop(config);
    } catch {
      /* ignore malformed storage */
    }
    // Run once on mount.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const value = useMemo<OvernightContextValue>(
    () => ({ status, start, stop }),
    [status, start, stop]
  );

  return <OvernightContext.Provider value={value}>{children}</OvernightContext.Provider>;
}

export function useOvernight(): OvernightContextValue {
  const ctx = useContext(OvernightContext);
  if (!ctx) {
    throw new Error("useOvernight must be used within an OvernightProvider");
  }
  return ctx;
}

export const OVERNIGHT_DEFAULT_CYCLE_DELAY_MS = DEFAULT_CYCLE_DELAY_MS;
