"use client";

import { type ReactNode } from "react";
import { CheckCircle2, Circle, Loader2, XCircle } from "lucide-react";

import { PIPELINE_STAGES, type PipelineStageId } from "@/lib/pipeline-progress";
import { cn } from "@/lib/utils";

export type NodeStatus = "pending" | "running" | "completed" | "failed";

export interface TopologyNodeState {
  node: PipelineStageId | string;
  status: NodeStatus;
}

const STATUS_STYLE: Record<NodeStatus, string> = {
  pending: "border-border bg-background/80 text-slate-600 dark:text-slate-300",
  running: "border-blue-400/70 bg-blue-50 text-blue-800 shadow-[0_0_0_1px_rgba(37,99,235,0.12)] dark:bg-blue-500/10 dark:text-blue-200",
  completed: "border-emerald-400/70 bg-emerald-50 text-emerald-800 dark:bg-emerald-500/10 dark:text-emerald-200",
  failed: "border-red-400/70 bg-red-50 text-red-800 dark:bg-red-500/10 dark:text-red-200",
};

function StatusIcon({ status }: { status: NodeStatus }) {
  if (status === "completed") return <CheckCircle2 className="size-4" aria-hidden />;
  if (status === "failed") return <XCircle className="size-4" aria-hidden />;
  if (status === "running") return <Loader2 className="size-4 animate-spin" aria-hidden />;
  return <Circle className="size-4" aria-hidden />;
}

export function PipelineTopology({
  states,
  compact = false,
}: {
  states: TopologyNodeState[];
  compact?: boolean;
}): ReactNode {
  const byId = new Map(states.map((state) => [state.node, state.status] as const));

  return (
    <div className={cn("rounded-2xl border border-border bg-background/50", compact ? "p-3" : "p-4")}>
      <ol className={cn("grid gap-2", compact ? "sm:grid-cols-2 xl:grid-cols-7" : "md:grid-cols-2 xl:grid-cols-7")}>
        {PIPELINE_STAGES.map((stage, index) => {
          const status = byId.get(stage.id) ?? "pending";
          return (
            <li key={stage.id} className="min-w-0">
              <div
                className={cn(
                  "flex h-full min-h-28 gap-3 rounded-xl border p-3 transition-colors",
                  compact && "min-h-24",
                  STATUS_STYLE[status]
                )}
                aria-label={`${stage.label}: ${status}`}
              >
                <div className="mt-0.5 flex shrink-0 flex-col items-center gap-2">
                  <StatusIcon status={status} />
                  <span className="font-mono text-[10px] opacity-70">{index + 1}</span>
                </div>
                <div className="min-w-0">
                  <div className="text-xs font-semibold uppercase leading-4 tracking-wide">
                    {stage.label}
                  </div>
                  <div className="mt-1 text-[11px] leading-4 opacity-80">
                    {stage.description}
                  </div>
                  {!compact ? (
                    <div className="mt-2 rounded-lg border border-current/15 px-2 py-1 text-[11px] leading-4 opacity-90">
                      {stage.output}
                    </div>
                  ) : null}
                </div>
              </div>
            </li>
          );
        })}
      </ol>
    </div>
  );
}