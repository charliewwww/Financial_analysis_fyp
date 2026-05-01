"use client";

import { type ReactNode } from "react";

export type NodeStatus = "pending" | "running" | "completed" | "failed";

export interface TopologyNodeState {
  node: string;
  status: NodeStatus;
}

const NODES: Array<{ id: string; label: string; description: string }> = [
  { id: "fetch", label: "Fetch", description: "Pull RSS, prices, macros" },
  { id: "summarize", label: "Summarize", description: "Condense news per ticker" },
  { id: "reflect", label: "Reflect", description: "Critique gaps + bias" },
  { id: "analyze", label: "Analyze", description: "Generate thesis + predictions" },
  { id: "validate", label: "Validate", description: "Numerical + source checks" },
  { id: "score", label: "Score", description: "Confidence + conviction" },
  { id: "save", label: "Save", description: "Persist report + signal card" },
];

const STATUS_STYLE: Record<NodeStatus, string> = {
  pending: "bg-muted/40 border-muted text-muted-foreground",
  running: "bg-blue-500/10 border-blue-500/60 text-blue-200 animate-pulse",
  completed: "bg-emerald-500/10 border-emerald-500/60 text-emerald-200",
  failed: "bg-red-500/10 border-red-500/60 text-red-200",
};

export function PipelineTopology({
  states,
}: {
  states: TopologyNodeState[];
}): ReactNode {
  const byId = new Map(states.map((s) => [s.node, s.status] as const));

  return (
    <div className="overflow-x-auto">
      <ol className="flex items-stretch gap-2 min-w-fit pb-2">
        {NODES.map((n, i) => {
          const status = byId.get(n.id) ?? "pending";
          return (
            <li key={n.id} className="flex items-stretch">
              <div
                className={`rounded-md border px-3 py-2 min-w-32 ${STATUS_STYLE[status]}`}
              >
                <div className="text-xs font-semibold uppercase tracking-wide">
                  {n.label}
                </div>
                <div className="text-[11px] opacity-80 leading-tight mt-0.5">
                  {n.description}
                </div>
              </div>
              {i < NODES.length - 1 && (
                <div
                  className="self-center mx-1 text-muted-foreground select-none"
                  aria-hidden
                >
                  →
                </div>
              )}
            </li>
          );
        })}
      </ol>
    </div>
  );
}
