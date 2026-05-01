"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchAblation, fetchAccuracyStats, fetchSignals } from "@/lib/api";
import { AccuracyStatsDisplay } from "@/components/AccuracyStats";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

function UncheckedPredictions() {
  const { data, isLoading } = useQuery({
    queryKey: ["signals", { page: 1 }],
    queryFn: () => fetchSignals({ page: 1, page_size: 50 }),
  });

  if (isLoading) return <Skeleton className="h-40 w-full" />;

  const cardsWithPredictions = data?.items.filter(
    (c) => c.status === "active"
  ) ?? [];

  if (cardsWithPredictions.length === 0) {
    return (
      <p className="text-sm text-muted-foreground py-6 text-center">
        No active signal cards.
      </p>
    );
  }

  return (
    <Card>
      <CardHeader><CardTitle className="text-sm">Active Signal Cards</CardTitle></CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Ticker</TableHead>
              <TableHead>Signal</TableHead>
              <TableHead>Conviction</TableHead>
              <TableHead>Created</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {cardsWithPredictions.map((c) => (
              <TableRow key={c.id}>
                <TableCell className="font-medium">
                  <a href={`/signals/${c.id}`} className="hover:underline">
                    {c.ticker}
                  </a>
                </TableCell>
                <TableCell>{c.signal}</TableCell>
                <TableCell>{c.conviction ?? "—"}/5</TableCell>
                <TableCell className="text-muted-foreground text-sm">
                  {new Date(c.created_at).toLocaleDateString()}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}

interface AblationResultPayload {
  total_reports_analyzed?: number;
  reports_with_pipeline_state?: number;
  retry_rate_pct?: number;
  avg_discrepancies_before?: number;
  avg_discrepancies_after?: number;
  discrepancy_reduction_pct?: number;
  intervention_rate_pct?: number;
  avg_citation_rate_pct?: number;
  status_counts?: Record<string, number>;
  summary_bullets?: string[];
}

function AblationStudy() {
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["ablation"],
    queryFn: fetchAblation,
    staleTime: 5 * 60_000,
  });

  if (isLoading) return <Skeleton className="h-64 w-full" />;
  if (isError) {
    return (
      <p className="text-sm text-red-400">
        Failed to load ablation: {String(error)}
      </p>
    );
  }
  if (!data) return null;

  const r = data as AblationResultPayload;
  const fmt = (n?: number, d = 1) =>
    n == null || Number.isNaN(n) ? "—" : `${n.toFixed(d)}`;
  const fmtPct = (n?: number) =>
    n == null || Number.isNaN(n) ? "—" : `${n.toFixed(1)}%`;

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Validation layers — impact</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4 text-sm">
          <div>
            <div className="text-xs text-muted-foreground">Reports analysed</div>
            <div className="text-2xl font-semibold tabular-nums">
              {r.total_reports_analyzed ?? 0}
            </div>
          </div>
          <div>
            <div className="text-xs text-muted-foreground">Retry rate</div>
            <div className="text-2xl font-semibold tabular-nums">
              {fmtPct(r.retry_rate_pct)}
            </div>
          </div>
          <div>
            <div className="text-xs text-muted-foreground">
              Discrepancy reduction
            </div>
            <div className="text-2xl font-semibold tabular-nums">
              {fmtPct(r.discrepancy_reduction_pct)}
            </div>
            <div className="text-[11px] text-muted-foreground">
              {fmt(r.avg_discrepancies_before, 2)} →{" "}
              {fmt(r.avg_discrepancies_after, 2)}
            </div>
          </div>
          <div>
            <div className="text-xs text-muted-foreground">
              Citation rate (avg)
            </div>
            <div className="text-2xl font-semibold tabular-nums">
              {fmtPct(r.avg_citation_rate_pct)}
            </div>
          </div>
        </CardContent>
      </Card>

      {r.summary_bullets && r.summary_bullets.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Findings</CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="list-disc pl-5 space-y-1 text-sm">
              {r.summary_bullets.map((b, i) => (
                <li key={i}>{b}</li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      {r.status_counts && Object.keys(r.status_counts).length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">
              Validation status distribution
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="space-y-1 text-sm">
              {Object.entries(r.status_counts).map(([k, v]) => (
                <li key={k} className="flex justify-between">
                  <span>{k}</span>
                  <span className="font-mono">{v}</span>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

export default function AccuracyPage() {
  const { data: stats, isLoading, isError, error } = useQuery({
    queryKey: ["accuracy"],
    queryFn: fetchAccuracyStats,
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Accuracy</h1>
        <p className="text-sm text-muted-foreground">
          Prediction outcomes and accountability loop
        </p>
      </div>

      <Tabs defaultValue="stats">
        <TabsList>
          <TabsTrigger value="stats">Stats</TabsTrigger>
          <TabsTrigger value="cards">Active Cards</TabsTrigger>
          <TabsTrigger value="ablation">Ablation</TabsTrigger>
        </TabsList>

        <TabsContent value="stats" className="pt-4">
          {isError && (
            <p className="text-sm text-red-400">
              Failed to load accuracy stats: {String(error)}
            </p>
          )}
          {isLoading ? (
            <div className="space-y-4">
              <Skeleton className="h-32 w-full" />
              <Skeleton className="h-48 w-full" />
            </div>
          ) : stats ? (
            <AccuracyStatsDisplay stats={stats} />
          ) : null}
        </TabsContent>

        <TabsContent value="cards" className="pt-4">
          <UncheckedPredictions />
        </TabsContent>

        <TabsContent value="ablation" className="pt-4">
          <AblationStudy />
        </TabsContent>
      </Tabs>
    </div>
  );
}
