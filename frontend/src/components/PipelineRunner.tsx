"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  AlertCircle,
  CheckCircle2,
  Clock,
  FileText,
  Loader2,
  Radio,
  ShieldCheck,
} from "lucide-react";

import { fetchRun, fetchSectors, sseStreamUrl, triggerRun } from "@/lib/api";
import {
  PIPELINE_STAGES,
  buildPipelineStageStates,
  currentPipelineStage,
  currentStageLabel,
  elapsedRunSeconds,
  formatDuration,
  getPipelineStage,
  runProgressPct,
  runTimingLabel,
  type PipelineStageId,
} from "@/lib/pipeline-progress";
import type { NodeExecution, PipelineRun, RunRequest, RunStatus, SSEEvent, SSEEventType } from "@/types/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  PipelineTopology,
  type NodeStatus,
  type TopologyNodeState,
} from "@/components/PipelineTopology";
import { cn } from "@/lib/utils";

const STATUS_COLOR: Record<RunStatus, string> = {
  pending: "bg-zinc-100 text-zinc-700 border-zinc-300 dark:bg-zinc-500/20 dark:text-zinc-300 dark:border-zinc-500/30",
  running: "bg-blue-50 text-blue-800 border-blue-300 dark:bg-blue-500/20 dark:text-blue-200 dark:border-blue-500/30",
  completed: "bg-emerald-50 text-emerald-800 border-emerald-300 dark:bg-emerald-500/20 dark:text-emerald-200 dark:border-emerald-500/30",
  failed: "bg-red-50 text-red-800 border-red-300 dark:bg-red-500/20 dark:text-red-200 dark:border-red-500/30",
};

const NODE_STATUS_COLOR: Record<NodeStatus | "skipped", string> = {
  pending: "text-muted-foreground",
  running: "text-blue-300",
  completed: "text-emerald-300",
  failed: "text-red-300",
  skipped: "text-muted-foreground",
};

interface TriggerFormProps {
  onRun: (runId: string) => void;
}

function TriggerForm({ onRun }: TriggerFormProps) {
  const [ticker, setTicker] = useState("NVDA");
  const [sectorId, setSectorId] = useState("ai_semiconductors");

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
    <form onSubmit={handleSubmit} className="grid gap-3 md:grid-cols-[minmax(120px,0.6fr)_minmax(220px,1fr)_auto] md:items-end">
      <div className="flex flex-col gap-1">
        <label className="text-xs font-medium text-muted-foreground">Ticker</label>
        <input
          value={ticker}
          onChange={(e) => setTicker(e.target.value)}
          placeholder="NVDA"
          className="h-10 rounded-lg border border-border bg-background px-3 font-mono text-sm uppercase outline-none focus:ring-2 focus:ring-ring"
          disabled={mutation.isPending}
        />
      </div>
      <div className="flex flex-col gap-1">
        <label className="text-xs font-medium text-muted-foreground">Sector context</label>
        <select
          value={sectorId}
          onChange={(e) => setSectorId(e.target.value)}
          className="h-10 rounded-lg border border-border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-ring"
          disabled={mutation.isPending || sectors.isLoading}
        >
          <option value="">
            {sectors.isLoading ? "Loading sectors..." : "Select a sector..."}
          </option>
          {sectors.data?.map((sector) => (
            <option key={sector.id} value={sector.id}>
              {sector.name}
            </option>
          ))}
        </select>
      </div>
      <Button type="submit" className="h-10 rounded-full px-5" disabled={mutation.isPending || !ticker || !sectorId}>
        {mutation.isPending ? (
          <Loader2 data-icon="inline-start" className="size-4 animate-spin" aria-hidden />
        ) : (
          <Activity data-icon="inline-start" className="size-4" aria-hidden />
        )}
        {mutation.isPending ? "Queuing" : "Run analysis"}
      </Button>
      {mutation.isError ? (
        <div className="md:col-span-3 rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-200">
          {mutation.error instanceof Error ? mutation.error.message : "Could not queue the run."}
        </div>
      ) : null}
    </form>
  );
}

interface StreamViewProps {
  runId: string;
}

function eventPayload(evt: SSEEvent | Record<string, unknown>): Record<string, unknown> {
  const data = "data" in evt ? evt.data : null;
  return data && typeof data === "object" ? (data as Record<string, unknown>) : (evt as Record<string, unknown>);
}

function stageStatesFromEvents(nodes: NodeExecution[]): TopologyNodeState[] {
  const byId = new Map<PipelineStageId, NodeStatus>();
  for (const node of nodes) {
    const stage = getPipelineStage(node.node ?? node.node_name ?? null);
    if (!stage) continue;
    byId.set(stage.id, node.status === "skipped" ? "completed" : node.status);
  }
  return PIPELINE_STAGES.map((stage) => ({ node: stage.id, status: byId.get(stage.id) ?? "pending" }));
}

function progressFromEvents(nodes: NodeExecution[], status: RunStatus): number {
  if (status === "completed") return 100;
  if (!nodes.length) return status === "running" ? 5 : 0;
  const completed = nodes.filter((node) => node.status === "completed" || node.status === "skipped").length;
  const running = nodes.some((node) => node.status === "running") ? 0.4 : 0;
  return Math.max(5, Math.min(99, Math.round(((completed + running) / PIPELINE_STAGES.length) * 100)));
}

function formatNodeDuration(node: NodeExecution): string | null {
  if (typeof node.duration_seconds === "number" && node.duration_seconds > 0) {
    return formatDuration(node.duration_seconds);
  }
  if (!node.started_at || !node.finished_at) return null;
  const started = new Date(node.started_at).getTime();
  const finished = new Date(node.finished_at).getTime();
  if (Number.isNaN(started) || Number.isNaN(finished)) return null;
  return formatDuration((finished - started) / 1000);
}

function RunMetric({
  label,
  value,
  detail,
  icon,
}: {
  label: string;
  value: string;
  detail: string;
  icon: React.ReactNode;
}) {
  return (
    <div className="rounded-xl border border-border bg-background/60 p-3">
      <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        {icon}
        {label}
      </div>
      <div className="mt-2 text-sm font-semibold">{value}</div>
      <div className="mt-1 text-xs leading-4 text-muted-foreground">{detail}</div>
    </div>
  );
}

function StreamView({ runId }: StreamViewProps) {
  const [nodes, setNodes] = useState<NodeExecution[]>([]);
  const [terminalStatus, setTerminalStatus] = useState<RunStatus | null>(null);
  const [eventError, setEventError] = useState<string | null>(null);
  const [streamIssue, setStreamIssue] = useState<string | null>(null);
  const esRef = useRef<EventSource | null>(null);
  const qc = useQueryClient();

  const { data: run } = useQuery<PipelineRun>({
    queryKey: ["run", runId],
    queryFn: () => fetchRun(runId),
    refetchInterval: (query) => {
      const status = (query.state.data as PipelineRun | undefined)?.status;
      return terminalStatus || status === "completed" || status === "failed" ? false : 3000;
    },
  });

  useEffect(() => {
    const url = sseStreamUrl(runId);
    const es = new EventSource(url, { withCredentials: true });
    esRef.current = es;

    const handleEvent = (e: MessageEvent) => {
      try {
        const evt = JSON.parse(e.data) as SSEEvent | Record<string, unknown>;
        const eventType = (("event" in evt && evt.event) || e.type) as SSEEventType;
        const payload = eventPayload(evt);

        if (eventType === "heartbeat") {
          setStreamIssue(null);
          return;
        }

        if (eventType === "node_started") {
          const node = typeof payload.node === "string" ? payload.node : "";
          const label = typeof payload.label === "string" ? payload.label : getPipelineStage(node)?.label ?? node;
          if (!node) return;
          setNodes((prev) => [
            ...prev.filter((item) => (item.node ?? item.node_name) !== node),
            {
              node,
              label,
              status: "running",
              started_at: typeof payload.started_at === "string" ? payload.started_at : new Date().toISOString(),
              finished_at: null,
              error: null,
            },
          ]);
          return;
        }

        if (eventType === "node_completed") {
          const node = typeof payload.node === "string" ? payload.node : "";
          if (!node) return;
          setNodes((prev) => {
            const exists = prev.some((item) => (item.node ?? item.node_name) === node);
            const next = prev.map((item) =>
              (item.node ?? item.node_name) === node
                ? { ...item, status: "completed" as const, finished_at: typeof payload.finished_at === "string" ? payload.finished_at : new Date().toISOString() }
                : item
            );
            if (exists) return next;
            return [
              ...next,
              {
                node,
                label: getPipelineStage(node)?.label ?? node,
                status: "completed",
                started_at: null,
                finished_at: typeof payload.finished_at === "string" ? payload.finished_at : new Date().toISOString(),
                error: null,
              },
            ];
          });
          return;
        }

        if (eventType === "pipeline_completed" || eventType === "pipeline_failed") {
          if (eventType === "pipeline_failed") {
            const message = typeof payload.message === "string" ? payload.message : typeof payload.error === "string" ? payload.error : "Pipeline failed";
            setEventError(message);
            setTerminalStatus("failed");
          } else {
            setTerminalStatus("completed");
          }
          qc.invalidateQueries({ queryKey: ["signals"] });
          qc.invalidateQueries({ queryKey: ["reports"] });
          qc.invalidateQueries({ queryKey: ["runs"] });
          es.close();
        }
      } catch {
        setStreamIssue("Live event could not be parsed; polling status instead.");
      }
    };

    const eventNames = [
      "node_started",
      "node_completed",
      "pipeline_completed",
      "pipeline_failed",
      "heartbeat",
    ] as const;
    for (const name of eventNames) {
      es.addEventListener(name, handleEvent);
    }
    es.onopen = () => setStreamIssue(null);
    es.onmessage = handleEvent;
    es.onerror = () => {
      setStreamIssue("Live stream paused; polling run status every few seconds.");
      es.close();
    };

    return () => {
      for (const name of eventNames) {
        es.removeEventListener(name, handleEvent);
      }
      es.close();
    };
  }, [runId, qc]);

  const effectiveStatus: RunStatus = run?.status ?? terminalStatus ?? "running";
  const effectiveError = eventError ?? run?.error ?? null;
  const stageStates = useMemo(
    () => (run ? buildPipelineStageStates(run) : stageStatesFromEvents(nodes)),
    [nodes, run]
  );
  const progressPct = run ? runProgressPct(run) : progressFromEvents(nodes, effectiveStatus);
  const activeStage = run ? currentPipelineStage(run) : getPipelineStage(nodes.find((node) => node.status === "running")?.node ?? null);
  const timing = run ? runTimingLabel(run) : nodes.length ? "Receiving live events" : "Connecting to worker";
  const elapsed = run ? elapsedRunSeconds(run) : null;
  const signalCardId = run?.signal_card_id;

  return (
    <div className="space-y-5">
      <section className="rounded-2xl border border-border bg-background/60 p-4">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="outline" className={STATUS_COLOR[effectiveStatus]}>
                {effectiveStatus}
              </Badge>
              <Badge variant="outline" className={streamIssue ? STATUS_COLOR.pending : STATUS_COLOR.running}>
                <Radio className="mr-1 size-3" aria-hidden />
                {streamIssue ? "polling fallback" : "live stream"}
              </Badge>
            </div>
            <div className="mt-3 break-all font-mono text-xs text-muted-foreground">{runId}</div>
          </div>
          {signalCardId ? (
            <Link
              href={`/signals/${signalCardId}`}
              className="inline-flex h-10 items-center justify-center gap-2 rounded-full bg-primary px-4 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
            >
              <FileText className="size-4" aria-hidden />
              Open signal card
            </Link>
          ) : null}
        </div>

        <div className="mt-4 grid gap-3 md:grid-cols-4">
          <RunMetric
            label="Current stage"
            value={run ? currentStageLabel(run) : activeStage?.label ?? "Starting"}
            detail={activeStage?.description ?? "Waiting for the first pipeline event"}
            icon={<Activity className="size-3.5" aria-hidden />}
          />
          <RunMetric
            label="Finish estimate"
            value={timing}
            detail={elapsed == null ? "Timer starts when the worker begins" : `${formatDuration(elapsed)} elapsed`}
            icon={<Clock className="size-3.5" aria-hidden />}
          />
          <RunMetric
            label="Trust gate"
            value={effectiveStatus === "completed" ? "Ready" : effectiveStatus === "failed" ? "Blocked" : "In progress"}
            detail="Claims are validated before a signal card is published"
            icon={<ShieldCheck className="size-3.5" aria-hidden />}
          />
          <RunMetric
            label="Progress"
            value={`${progressPct}%`}
            detail={activeStage?.output ?? "Pipeline handshake"}
            icon={effectiveStatus === "completed" ? <CheckCircle2 className="size-3.5" aria-hidden /> : <Loader2 className="size-3.5 animate-spin" aria-hidden />}
          />
        </div>

        <div className="mt-4 h-2 overflow-hidden rounded-full bg-muted">
          <div className="h-full rounded-full bg-[var(--al-gold)] transition-all duration-500" style={{ width: `${progressPct}%` }} />
        </div>
      </section>

      {streamIssue ? (
        <div className="flex items-start gap-2 rounded-xl border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-sm text-amber-100">
          <AlertCircle className="mt-0.5 size-4 shrink-0" aria-hidden />
          <span>{streamIssue}</span>
        </div>
      ) : null}

      {effectiveError ? (
        <div className="flex items-start gap-2 rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800 dark:border-red-500/30 dark:bg-red-500/10 dark:text-red-100">
          <AlertCircle className="mt-0.5 size-4 shrink-0 text-red-600 dark:text-red-300" aria-hidden />
          <span>{effectiveError}</span>
        </div>
      ) : null}

      <section className="space-y-3">
        <div className="flex flex-wrap items-end justify-between gap-2">
          <div>
            <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Pipeline topology</div>
            <h3 className="text-base font-semibold">LangGraph execution path</h3>
          </div>
          <span className="text-xs text-muted-foreground">7 stages from evidence intake to report packaging</span>
        </div>
        <PipelineTopology states={stageStates} />
      </section>

      <section className="grid gap-3 lg:grid-cols-[1fr_0.8fr]">
        <div className="rounded-2xl border border-border bg-background/50 p-4">
          <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Stage ledger</div>
          <div className="mt-3 space-y-2">
            {PIPELINE_STAGES.map((stage) => {
              const status = stageStates.find((item) => item.node === stage.id)?.status ?? "pending";
              return (
                <div key={stage.id} className="flex items-start justify-between gap-3 rounded-xl bg-muted/30 px-3 py-2 text-sm">
                  <div>
                    <div className="font-medium">{stage.label}</div>
                    <div className="text-xs leading-4 text-muted-foreground">{stage.output}</div>
                  </div>
                  <span className={cn("shrink-0 text-xs font-semibold", NODE_STATUS_COLOR[status])}>{status}</span>
                </div>
              );
            })}
          </div>
        </div>

        <div className="rounded-2xl border border-border bg-background/50 p-4">
          <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Live events</div>
          <div className="mt-3 space-y-2">
            {nodes.length ? (
              nodes.slice(-7).reverse().map((node) => {
                const nodeId = node.node ?? node.node_name ?? "unknown";
                const stage = getPipelineStage(nodeId);
                return (
                  <div key={`${nodeId}-${node.status}`} className="flex items-center gap-3 rounded-xl bg-muted/30 px-3 py-2 text-sm">
                    <span className={cn("h-2.5 w-2.5 rounded-full", node.status === "completed" ? "bg-emerald-400" : node.status === "failed" ? "bg-red-400" : "bg-blue-400")} />
                    <div className="min-w-0 flex-1">
                      <div className="truncate font-medium">{stage?.label ?? node.label ?? nodeId}</div>
                      <div className="text-xs text-muted-foreground">{node.status}</div>
                    </div>
                    {formatNodeDuration(node) ? <span className="font-mono text-xs text-muted-foreground">{formatNodeDuration(node)}</span> : null}
                  </div>
                );
              })
            ) : (
              <div className="rounded-xl bg-muted/30 px-3 py-4 text-sm text-muted-foreground">
                Waiting for the worker to emit its first node event.
              </div>
            )}
          </div>
        </div>
      </section>
    </div>
  );
}

export function PipelineRunner() {
  const [activeRunId, setActiveRunId] = useState<string | null>(null);
  const [history, setHistory] = useState<string[]>([]);

  function handleRun(runId: string) {
    setActiveRunId(runId);
    setHistory((items) => [runId, ...items.filter((item) => item !== runId)].slice(0, 8));
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Run analysis pipeline</CardTitle>
          <CardDescription>
            Start a ticker run and watch the evidence, reasoning, validation, and report packaging stages move in real time.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <TriggerForm onRun={handleRun} />
        </CardContent>
      </Card>

      {activeRunId ? (
        <Card>
          <CardHeader>
            <CardTitle>Analysis progress</CardTitle>
            <CardDescription>
              Live SSE events are shown first; the polling endpoint keeps the run readable if the stream drops.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <StreamView key={activeRunId} runId={activeRunId} />
          </CardContent>
        </Card>
      ) : null}

      {history.length > 1 ? (
        <section className="rounded-2xl border border-border bg-background/50 p-4">
          <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Session runs</div>
          <div className="mt-3 flex flex-wrap gap-2">
            {history.slice(1).map((id) => (
              <button
                key={id}
                type="button"
                onClick={() => setActiveRunId(id)}
                className="rounded-full border border-border px-3 py-1.5 font-mono text-xs text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
              >
                {id.slice(0, 8)}
              </button>
            ))}
          </div>
        </section>
      ) : null}
    </div>
  );
}