"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchSystemHealth } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorState } from "@/components/StateMessage";
import { formatClock } from "@/lib/format";

function StatusBadge({ ok, label }: { ok: boolean; label: string }) {
  return (
    <Badge
      variant="outline"
      className={
        ok
          ? "bg-emerald-500/20 text-emerald-300 border-emerald-500/30"
          : "bg-red-500/20 text-red-300 border-red-500/30"
      }
    >
      {ok ? "✓" : "✗"} {label}
    </Badge>
  );
}

export default function SystemHealthPage() {
  const { data, isLoading, isError, dataUpdatedAt, refetch } = useQuery({
    queryKey: ["system", "health"],
    queryFn: fetchSystemHealth,
    refetchInterval: 30_000,
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">System Health</h1>
        <p className="text-sm text-muted-foreground">
          Live snapshot of LLM provider, vector store, and external API
          configuration. Auto-refreshes every 30s.
          {dataUpdatedAt ? (
            <span aria-live="polite"> Updated {formatClock(dataUpdatedAt)}.</span>
          ) : null}
        </p>
      </div>

      {isLoading && <Skeleton className="h-40 w-full" />}
      {isError && (
        <ErrorState title="Failed to load system status" onRetry={() => refetch()} />
      )}

      {data && (
        <div className="grid gap-4 md:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle className="text-sm">LLM</CardTitle>
            </CardHeader>
            <CardContent className="space-y-1 text-sm">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Provider</span>
                <span className="font-mono">{data.llm_provider}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Model</span>
                <span className="font-mono text-xs">{data.llm_model}</span>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-sm">Pipeline & vectors</CardTitle>
            </CardHeader>
            <CardContent className="space-y-1 text-sm">
              <div className="flex justify-between">
                <span className="text-muted-foreground">LangGraph</span>
                <StatusBadge ok={data.langgraph_ok} label={data.langgraph_ok ? "ready" : "down"} />
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">ChromaDB docs</span>
                <span className="font-mono">{data.chromadb_docs.toLocaleString()}</span>
              </div>
            </CardContent>
          </Card>

          <Card className="md:col-span-2">
            <CardHeader>
              <CardTitle className="text-sm">External APIs</CardTitle>
            </CardHeader>
            <CardContent className="flex gap-2 flex-wrap">
              <StatusBadge ok={data.fred_key_set} label="FRED API key" />
              <StatusBadge
                ok={data.sec_edgar_configured}
                label="SEC EDGAR email"
              />
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
