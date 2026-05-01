"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchRun, fetchSectors, sseStreamUrl, triggerRun } from "@/lib/api";
import type { NodeExecution, PipelineRun, RunRequest, SSEEvent } from "@/types/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  PipelineTopology,
  type NodeStatus,
  type TopologyNodeState,
} from "@/components/PipelineTopology";

// ── Status colours ────────────────────────────────────────────────────────────

const STATUS_COLOR: Record<string, string> = {
  pending: "bg-zinc-500/20 text-zinc-400 border-zinc-500/30",
  running: "bg-blue-500/20 text-blue-400 border-blue-500/30 animate-pulse",
  completed: "bg-emerald-500/20 text-emerald-400 border-emerald-500/30",
  failed: "bg-red-500/20 text-red-400 border-red-500/30",
};

const NODE_STATUS_ICON: Record<string, string> = {
  running: "⟳",
  completed: "✓",
  failed: "✗",
  skipped: "—",
};

// ── Trigger form ───────────────────────────────────────────────────────────────

interface TriggerFormProps {
  onRun: (runId: string) => void;
}

function TriggerForm({ onRun }: TriggerFormProps) {
  const [ticker, setTicker] = useState("");
  const [sectorId, setSectorId] = useState("");

  const sectors = useQuery({
    queryKey: ["sectors"],
    queryFn: fetchSectors,
    staleTime: 5 * 60 * 1000,
  });

  const mutation = useMutation({
    mutationFn: (body: RunRequest) => triggerRun(body),
    onSuccess: (data) => onRun(data.run_id),
  });

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!ticker.trim() || !sectorId.trim()) return;
    mutation.mutate({ ticker: ticker.toUpperCase().trim(), sector_id: sectorId.trim() });
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-3 sm:flex-row sm:items-end">
      <div className="flex flex-col gap-1">
        <label className="text-xs text-muted-foreground font-medium">Ticker</label>
        <input
          value={ticker}
          onChange={(e) => setTicker(e.target.value)}
          placeholder="e.g. AAPL"
          className="w-32 rounded-md border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring uppercase"
          disabled={mutation.isPending}
        />
      </div>
      <div className="flex flex-col gap-1">
        <label className="text-xs text-muted-foreground font-medium">Sector</label>
        <select
          value={sectorId}
          onChange={(e) => setSectorId(e.target.value)}
          className="w-56 rounded-md border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          disabled={mutation.isPending || sectors.isLoading}
        >
          <option value="">
            {sectors.isLoading ? "Loading sectors…" : "Select a sector…"}
          </option>
          {sectors.data?.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name}
            </option>
          ))}
        </select>
      </div>
      <Button type="submit" disabled={mutation.isPending || !ticker || !sectorId}>
        {mutation.isPending ? "Queuing…" : "Run Pipeline"}
      </Button>
      {mutation.isError && (
        <span className="text-xs text-red-400">{String(mutation.error)}</span>
      )}
    </form>
  );
}

// ── Live stream progress ───────────────────────────────────────────────────────

interface StreamViewProps {
  runId: string;
}

function StreamView({ runId }: StreamViewProps) {
  const [nodes, setNodes] = useState<NodeExecution[]>([]);
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const esRef = useRef<EventSource | null>(null);
  const qc = useQueryClient();
  const router = useRouter();

  // Poll the run status once done for final state
  const { data: run } = useQuery<PipelineRun>({
    queryKey: ["run", runId],
    queryFn: () => fetchRun(runId),
    enabled: done,
  });

  useEffect(() => {
    const url = sseStreamUrl(runId);
    const es = new EventSource(url);
    esRef.current = es;

    es.onmessage = (e) => {
      try {
        const evt: SSEEvent = JSON.parse(e.data);

        if (evt.event === "node_started" && evt.data) {
          const d = evt.data as { node: string; label: string; started_at?: string };
          setNodes((prev) => [
            ...prev.filter((n) => n.node !== d.node),
            {
              node: d.node,
              label: d.label,
              status: "running",
              started_at: d.started_at ?? null,
              finished_at: null,
              error: null,
            },
          ]);
        } else if (evt.event === "node_completed" && evt.data) {
          const d = evt.data as { node: string; label: string; finished_at?: string };
          setNodes((prev) =>
            prev.map((n) =>
              n.node === d.node
                ? { ...n, status: "completed", finished_at: d.finished_at ?? null }
                : n
            )
          );
        } else if (evt.event === "pipeline_completed" || evt.event === "pipeline_failed") {
          if (evt.event === "pipeline_failed") {
            const d = evt.data as { error?: string };
            setError(d?.error ?? "Pipeline failed");
          } else {
            // Auto-navigate to the new signal card so the user lands on the
            // result instead of staring at a finished progress timeline.
            const d = evt.data as { signal_card_id?: number | null };
            if (d?.signal_card_id) {
              setTimeout(() => router.push(`/signals/${d.signal_card_id}`), 600);
            }
          }
          setDone(true);
          // Invalidate all query keys that pipeline completion affects so
          // the dashboard and reports page refresh automatically.
          qc.invalidateQueries({ queryKey: ["signals"] });
          qc.invalidateQueries({ queryKey: ["reports"] });
          qc.invalidateQueries({ queryKey: ["runs"] });
          es.close();
        }
      } catch {
        // ignore parse errors on heartbeat etc.
      }
    };

    es.onerror = () => {
      setDone(true);
      es.close();
    };

    return () => {
      es.close();
    };
  }, [runId, qc, router]);

  const finalStatus = run?.status;

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <span className="text-sm font-mono text-muted-foreground">{runId}</span>
        {(finalStatus || done) && (
          <Badge
            variant="outline"
            className={STATUS_COLOR[finalStatus ?? (error ? "failed" : "completed")] ?? ""}
          >
            {finalStatus ?? (error ? "failed" : done ? "completed" : "running")}
          </Badge>
        )}
        {!done && (
          <Badge variant="outline" className={STATUS_COLOR["running"]}>
            running
          </Badge>
        )}
      </div>

      {error && (
        <p className="text-sm text-red-400 bg-red-500/10 rounded-md px-3 py-2">{error}</p>
      )}

      <PipelineTopology
        states={nodes.map<TopologyNodeState>((n) => ({
          node: n.node,
          status: (n.status as NodeStatus) ?? "pending",
        }))}
      />

      <div className="space-y-1">
        {nodes.map((n) => (
          <div
            key={n.node}
            className="flex items-center gap-3 rounded-md px-3 py-2 bg-muted/40 text-sm"
          >
            <span
              className={`w-4 text-center font-mono ${
                n.status === "completed"
                  ? "text-emerald-400"
                  : n.status === "failed"
                  ? "text-red-400"
                  : n.status === "running"
                  ? "text-blue-400"
                  : "text-muted-foreground"
              }`}
            >
              {NODE_STATUS_ICON[n.status]}
            </span>
            <span className="flex-1">{n.label}</span>
            {n.finished_at && n.started_at && (
              <span className="text-xs text-muted-foreground font-mono">
                {(
                  (new Date(n.finished_at).getTime() -
                    new Date(n.started_at).getTime()) /
                  1000
                ).toFixed(1)}
                s
              </span>
            )}
          </div>
        ))}
        {!done && nodes.length === 0 && (
          <p className="text-sm text-muted-foreground animate-pulse px-3">
            Waiting for pipeline to start…
          </p>
        )}
      </div>

      {done && run?.signal_card_id && (
        <p className="text-sm text-emerald-400">
          ✓ Signal card{" "}
          <a href={`/signals/${run.signal_card_id}`} className="underline">
            #{run.signal_card_id}
          </a>{" "}
          generated.
        </p>
      )}
    </div>
  );
}

// ── Main export ────────────────────────────────────────────────────────────────

export function PipelineRunner() {
  const [activeRunId, setActiveRunId] = useState<string | null>(null);
  const [history, setHistory] = useState<string[]>([]);

  function handleRun(runId: string) {
    setActiveRunId(runId);
    setHistory((h) => [runId, ...h]);
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Trigger Analysis</CardTitle>
        </CardHeader>
        <CardContent>
          <TriggerForm onRun={handleRun} />
        </CardContent>
      </Card>

      {activeRunId && (
        <Card>
          <CardHeader>
            <CardTitle>Live Progress</CardTitle>
          </CardHeader>
          <CardContent>
            <StreamView key={activeRunId} runId={activeRunId} />
          </CardContent>
        </Card>
      )}

      {history.length > 1 && (
        <div className="space-y-2">
          <p className="text-xs text-muted-foreground font-medium uppercase tracking-wide">
            Previous runs this session
          </p>
          {history.slice(1).map((id) => (
            <button
              key={id}
              onClick={() => setActiveRunId(id)}
              className="block text-sm font-mono text-muted-foreground hover:text-foreground transition-colors"
            >
              {id}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
