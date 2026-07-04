import type { PipelineRun } from "@/types/api";

export type PipelineStageId =
  | "fetch"
  | "summarize"
  | "reflect"
  | "analyze"
  | "validate"
  | "score"
  | "save";

export type PipelineStageStatus = "pending" | "running" | "completed" | "failed";

export interface PipelineStageDefinition {
  id: PipelineStageId;
  label: string;
  description: string;
  output: string;
  typicalSeconds: number;
}

export const PIPELINE_STAGES: PipelineStageDefinition[] = [
  {
    id: "fetch",
    label: "Market intake",
    description: "News, prices, filings, macro context",
    output: "Raw evidence pack",
    typicalSeconds: 35,
  },
  {
    id: "summarize",
    label: "Signal extraction",
    description: "Ticker-specific facts and changes",
    output: "Condensed market brief",
    typicalSeconds: 45,
  },
  {
    id: "reflect",
    label: "Coverage review",
    description: "Gap, bias, and sufficiency check",
    output: "Refetch or proceed decision",
    typicalSeconds: 30,
  },
  {
    id: "analyze",
    label: "Analyst reasoning",
    description: "RAG context, thesis, supply-chain impact",
    output: "Investment thesis draft",
    typicalSeconds: 150,
  },
  {
    id: "validate",
    label: "Claim validation",
    description: "Numerical checks and source grounding",
    output: "Validation score",
    typicalSeconds: 60,
  },
  {
    id: "score",
    label: "Trust scoring",
    description: "Confidence, catalyst, risk, conviction",
    output: "Actionability gate",
    typicalSeconds: 25,
  },
  {
    id: "save",
    label: "Report packaging",
    description: "Report, signal card, prediction rows",
    output: "Decision Desk update",
    typicalSeconds: 20,
  },
];

const STAGE_INDEX = new Map(PIPELINE_STAGES.map((stage, index) => [stage.id, index] as const));
const ESTIMATED_TOTAL_SECONDS = PIPELINE_STAGES.reduce(
  (sum, stage) => sum + stage.typicalSeconds,
  0
);

export function normalizePipelineNode(node: string | null | undefined): PipelineStageId | null {
  if (!node) return null;
  const value = node.toLowerCase().trim();
  if (STAGE_INDEX.has(value as PipelineStageId)) return value as PipelineStageId;
  if (value.includes("fetch")) return "fetch";
  if (value.includes("summar")) return "summarize";
  if (value.includes("reflect") || value.includes("sufficien") || value.includes("coverage")) return "reflect";
  if (value.includes("validat") || value.includes("claim")) return "validate";
  if (value.includes("analy") || value.includes("reason")) return "analyze";
  if (value.includes("score") || value.includes("confidence") || value.includes("conviction")) return "score";
  if (value.includes("save") || value.includes("persist") || value.includes("package")) return "save";
  return null;
}

export function getPipelineStage(stageId: string | null | undefined): PipelineStageDefinition | null {
  const normalized = normalizePipelineNode(stageId);
  return normalized ? PIPELINE_STAGES[STAGE_INDEX.get(normalized) ?? 0] : null;
}

function executionNodeName(execution: unknown): string | null {
  if (!execution || typeof execution !== "object") return null;
  const record = execution as Record<string, unknown>;
  const raw = record.node ?? record.node_name;
  return typeof raw === "string" ? raw : null;
}

function executionStatus(execution: unknown): string | null {
  if (!execution || typeof execution !== "object") return null;
  const record = execution as Record<string, unknown>;
  return typeof record.status === "string" ? record.status : null;
}

function parseDate(value: string | null | undefined): Date | null {
  if (!value) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

export function completedPipelineStages(run: PipelineRun | null | undefined): Set<PipelineStageId> {
  const completed = new Set<PipelineStageId>();
  for (const execution of run?.node_executions ?? []) {
    const status = executionStatus(execution);
    if (status !== "completed" && status !== "skipped") continue;
    const stageId = normalizePipelineNode(executionNodeName(execution));
    if (stageId) completed.add(stageId);
  }
  return completed;
}

export function currentPipelineStage(run: PipelineRun | null | undefined): PipelineStageDefinition | null {
  const direct = getPipelineStage(run?.current_node);
  if (direct) return direct;

  const executions = run?.node_executions ?? [];
  for (let index = executions.length - 1; index >= 0; index -= 1) {
    const stage = getPipelineStage(executionNodeName(executions[index]));
    if (stage) return stage;
  }
  return null;
}

export function buildPipelineStageStates(
  run: PipelineRun | null | undefined
): Array<{ node: PipelineStageId; status: PipelineStageStatus }> {
  const completed = completedPipelineStages(run);
  const current = currentPipelineStage(run)?.id ?? null;
  const currentIndex = current ? STAGE_INDEX.get(current) ?? -1 : -1;
  const status = run?.error && run.status !== "completed" ? "failed" : run?.status;

  return PIPELINE_STAGES.map((stage, index) => {
    if (!run || status === "pending") return { node: stage.id, status: "pending" };
    if (status === "completed") return { node: stage.id, status: "completed" };
    if (completed.has(stage.id)) return { node: stage.id, status: "completed" };
    if (status === "failed" && current === stage.id) return { node: stage.id, status: "failed" };
    if (status === "failed" && currentIndex >= 0 && index < currentIndex) return { node: stage.id, status: "completed" };
    if (status === "running" && current === stage.id) return { node: stage.id, status: "running" };
    if (status === "running" && currentIndex >= 0 && index < currentIndex) return { node: stage.id, status: "completed" };
    return { node: stage.id, status: "pending" };
  });
}

export function aggregatePipelineStageStates(
  runs: Array<PipelineRun | null | undefined>
): Array<{ node: PipelineStageId; status: PipelineStageStatus }> {
  if (!runs.length) return PIPELINE_STAGES.map((stage) => ({ node: stage.id, status: "pending" }));

  const perRun = runs.map(buildPipelineStageStates);
  return PIPELINE_STAGES.map((stage, index) => {
    const statuses = perRun.map((states) => states[index]?.status ?? "pending");
    if (statuses.includes("failed")) return { node: stage.id, status: "failed" };
    if (statuses.includes("running")) return { node: stage.id, status: "running" };
    if (statuses.every((status) => status === "completed")) return { node: stage.id, status: "completed" };
    if (statuses.includes("completed")) return { node: stage.id, status: "running" };
    return { node: stage.id, status: "pending" };
  });
}

export function runProgressPct(run: PipelineRun | null | undefined): number {
  if (!run) return 0;
  const status = run.error && run.status !== "completed" ? "failed" : run.status;
  if (status === "completed") return 100;
  if (status === "pending") return 0;

  const current = currentPipelineStage(run);
  const completedCount = completedPipelineStages(run).size;
  const index = current ? STAGE_INDEX.get(current.id) ?? completedCount : completedCount;
  const stageCredit = status === "failed" ? 0.15 : 0.4;
  const pct = ((Math.max(index, completedCount) + stageCredit) / PIPELINE_STAGES.length) * 100;
  return Math.max(5, Math.min(99, Math.round(pct)));
}

export function formatDuration(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds <= 0) return "under 1 min";
  if (seconds < 60) return `${Math.max(1, Math.round(seconds))} sec`;
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = Math.round(seconds % 60);
  if (minutes < 60) return remainingSeconds ? `${minutes}m ${remainingSeconds}s` : `${minutes} min`;
  const hours = Math.floor(minutes / 60);
  const remainingMinutes = minutes % 60;
  return remainingMinutes ? `${hours}h ${remainingMinutes}m` : `${hours}h`;
}

export function elapsedRunSeconds(run: PipelineRun | null | undefined, now = new Date()): number | null {
  const started = parseDate(run?.started_at) ?? parseDate(run?.created_at);
  if (!started) return null;
  const ended = parseDate(run?.finished_at) ?? now;
  return Math.max(0, (ended.getTime() - started.getTime()) / 1000);
}

export function estimateRemainingSeconds(
  run: PipelineRun | null | undefined,
  now = new Date()
): number | null {
  const status = run?.error && run.status !== "completed" ? "failed" : run?.status;
  if (!run || status === "completed" || status === "failed") return null;
  if (status === "pending") return ESTIMATED_TOTAL_SECONDS;

  const pct = runProgressPct(run);
  const elapsed = elapsedRunSeconds(run, now);
  if (elapsed != null && pct >= 8) {
    return Math.max(20, Math.min(45 * 60, (elapsed * (100 - pct)) / pct));
  }

  const current = currentPipelineStage(run);
  const currentIndex = current ? STAGE_INDEX.get(current.id) ?? 0 : 0;
  return PIPELINE_STAGES.slice(currentIndex).reduce(
    (sum, stage) => sum + stage.typicalSeconds,
    0
  );
}

export function runTimingLabel(run: PipelineRun | null | undefined, now = new Date()): string {
  if (!run) return "Syncing status";
  const status = run.error && run.status !== "completed" ? "failed" : run.status;
  const elapsed = elapsedRunSeconds(run, now);
  if (status === "pending") return "Queued for worker";
  if (status === "completed") return elapsed == null ? "Report ready" : `Finished in ${formatDuration(elapsed)}`;
  if (status === "failed") return elapsed == null ? "Stopped" : `Stopped after ${formatDuration(elapsed)}`;
  const remaining = estimateRemainingSeconds(run, now);
  return remaining == null ? "Estimating finish" : `About ${formatDuration(remaining)} left`;
}

export function currentStageLabel(run: PipelineRun | null | undefined): string {
  if (!run) return "Waiting for status";
  const status = run.error && run.status !== "completed" ? "failed" : run.status;
  if (status === "pending") return "Queued";
  if (status === "completed") return "Report ready";
  if (status === "failed") return "Needs review";
  return currentPipelineStage(run)?.label ?? "Starting pipeline";
}

function sanitizeError(error: string): string {
  return error
    .replace(/https?:\/\/\S+/g, "the provider console")
    .replace(/keys\/[A-Za-z0-9_-]+/g, "keys/[redacted]")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, 220);
}

export function classifyPipelineError(error: string | null | undefined): {
  title: string;
  detail: string;
} | null {
  if (!error) return null;
  const lower = error.toLowerCase();
  if (lower.includes("key limit exceeded") || lower.includes("quota") || lower.includes("limit exceeded")) {
    return {
      title: "LLM quota exceeded",
      detail: "OpenRouter rejected the run because the current API key is out of credits. Switch to an OpenRouter :free model, add credits, rotate the key, or use local Ollama, then rerun.",
    };
  }
  if ((lower.includes("openrouter") && lower.includes("403")) || lower.includes("unauthorized") || lower.includes("api key")) {
    return {
      title: "LLM authentication failed",
      detail: "The model provider rejected the request. Check the API key or switch to local Ollama, then rerun.",
    };
  }
  if (lower.includes("validation failed")) {
    return {
      title: "Validation needs review",
      detail: "The analysis finished, but claim validation found issues. New runs publish a review-only signal card so the evidence can still be inspected.",
    };
  }
  return {
    title: "Run failed",
    detail: sanitizeError(error),
  };
}