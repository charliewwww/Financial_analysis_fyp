"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";

import { fetchAccuracyStats, fetchRuns, fetchSignals } from "@/lib/api";
import type { Signal } from "@/types/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

// ── Helpers ────────────────────────────────────────────────────────

const SIGNAL_COLOR: Record<Signal, string> = {
  BULLISH: "bg-emerald-500/20 text-emerald-400 border-emerald-500/30",
  BEARISH: "bg-red-500/20 text-red-400 border-red-500/30",
  NEUTRAL: "bg-zinc-500/20 text-zinc-400 border-zinc-500/30",
};

const RUN_COLOR: Record<string, string> = {
  pending: "bg-zinc-500/20 text-zinc-400 border-zinc-500/30",
  running: "bg-blue-500/20 text-blue-400 border-blue-500/30 animate-pulse",
  completed: "bg-emerald-500/20 text-emerald-400 border-emerald-500/30",
  failed: "bg-red-500/20 text-red-400 border-red-500/30",
};

function fmtPct(v: number | null | undefined, digits = 1): string {
  if (v == null || Number.isNaN(v)) return "—";
  return `${v.toFixed(digits)}%`;
}

function Kpi({ label, value, hint }: { label: string; value: string | number; hint?: string }) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
          {label}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="text-3xl font-semibold tabular-nums">{value}</div>
        {hint && <p className="mt-1 text-xs text-muted-foreground">{hint}</p>}
      </CardContent>
    </Card>
  );
}

// ── Page ───────────────────────────────────────────────────────────

export default function DashboardPage() {
  const acc = useQuery({
    queryKey: ["accuracy"],
    queryFn: fetchAccuracyStats,
    staleTime: 60_000,
  });
  const signals = useQuery({
    queryKey: ["signals", { page_size: 6 }],
    queryFn: () => fetchSignals({ page_size: 6 }),
  });
  const runs = useQuery({
    queryKey: ["runs", { page_size: 5 }],
    queryFn: () => fetchRuns({ page_size: 5 }),
  });

  return (
    <div className="space-y-8">
      <header className="flex items-baseline justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Morning Brief</h1>
          <p className="text-sm text-muted-foreground">
            Latest market signals, recent pipeline activity, and accuracy at a glance.
          </p>
        </div>
        <Link href="/pipeline">
          <Button>Run Analysis</Button>
        </Link>
      </header>

      {/* ── KPIs ──────────────────────────────────────────────── */}
      <section className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Kpi
          label="Direction Accuracy"
          value={acc.isLoading ? "—" : fmtPct(acc.data?.direction_accuracy_pct, 1)}
          hint={
            acc.data
              ? `${acc.data.direction_correct} of ${acc.data.checked} verified`
              : undefined
          }
        />
        <Kpi
          label="Verified Predictions"
          value={acc.isLoading ? "—" : (acc.data?.checked ?? 0)}
          hint={acc.data ? `${acc.data.unchecked} pending check` : undefined}
        />
        <Kpi
          label="Avg Abs Error"
          value={acc.isLoading ? "—" : fmtPct(acc.data?.avg_absolute_error_pct, 2)}
        />
        <Kpi
          label="Active Signals"
          value={signals.isLoading ? "—" : (signals.data?.total ?? 0)}
        />
      </section>

      {/* ── Latest Signals ────────────────────────────────────── */}
      <section className="space-y-3">
        <div className="flex items-baseline justify-between">
          <h2 className="text-lg font-semibold">Latest Signals</h2>
          <Link href="/signals" className="text-xs text-muted-foreground hover:text-foreground">
            View all →
          </Link>
        </div>

        {signals.isLoading ? (
          <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
            {Array.from({ length: 3 }).map((_, i) => (
              <Skeleton key={i} className="h-28" />
            ))}
          </div>
        ) : signals.data?.items.length ? (
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3">
            {signals.data.items.map((s) => (
              <Link
                key={s.id}
                href={`/signals/${s.id}`}
                className="group rounded-lg border border-border bg-card p-4 transition-colors hover:border-primary"
              >
                <div className="flex items-center justify-between">
                  <span className="font-mono text-sm font-semibold">{s.ticker}</span>
                  <Badge variant="outline" className={SIGNAL_COLOR[s.signal] ?? ""}>
                    {s.signal}
                  </Badge>
                </div>
                {s.one_line && (
                  <p className="mt-2 line-clamp-3 text-sm text-muted-foreground group-hover:text-foreground">
                    {s.one_line}
                  </p>
                )}
                <div className="mt-3 flex items-center gap-3 text-xs text-muted-foreground">
                  {s.conviction != null && <span>Conviction {s.conviction}/5</span>}
                  {s.confidence != null && (
                    <span>Confidence {(s.confidence * 100).toFixed(0)}%</span>
                  )}
                </div>
              </Link>
            ))}
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">
            No signals yet — trigger your first run from the{" "}
            <Link href="/pipeline" className="underline">
              Pipeline page
            </Link>
            .
          </p>
        )}
      </section>

      {/* ── Recent Runs ───────────────────────────────────────── */}
      <section className="space-y-3">
        <div className="flex items-baseline justify-between">
          <h2 className="text-lg font-semibold">Recent Runs</h2>
          <Link href="/pipeline" className="text-xs text-muted-foreground hover:text-foreground">
            Open Pipeline →
          </Link>
        </div>

        {runs.isLoading ? (
          <Skeleton className="h-32" />
        ) : runs.data?.items.length ? (
          <div className="overflow-hidden rounded-lg border border-border">
            <table className="w-full text-sm">
              <thead className="bg-muted/40 text-xs uppercase tracking-wide text-muted-foreground">
                <tr>
                  <th className="px-3 py-2 text-left">Ticker</th>
                  <th className="px-3 py-2 text-left">Sector</th>
                  <th className="px-3 py-2 text-left">Status</th>
                  <th className="px-3 py-2 text-left">Started</th>
                  <th className="px-3 py-2 text-left">Result</th>
                </tr>
              </thead>
              <tbody>
                {runs.data.items.map((r) => (
                  <tr key={r.run_id} className="border-t border-border hover:bg-muted/40">
                    <td className="px-3 py-2 font-mono">{r.ticker}</td>
                    <td className="px-3 py-2 text-muted-foreground">{r.sector_id}</td>
                    <td className="px-3 py-2">
                      <Badge variant="outline" className={RUN_COLOR[r.status] ?? ""}>
                        {r.status}
                      </Badge>
                    </td>
                    <td className="px-3 py-2 text-xs text-muted-foreground">
                      {new Date(r.created_at).toLocaleString()}
                    </td>
                    <td className="px-3 py-2">
                      {r.signal_card_id ? (
                        <Link
                          href={`/signals/${r.signal_card_id}`}
                          className="text-xs underline text-emerald-400"
                        >
                          Signal #{r.signal_card_id}
                        </Link>
                      ) : (
                        <span className="text-xs text-muted-foreground">—</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">No runs recorded yet.</p>
        )}
      </section>
    </div>
  );
}
