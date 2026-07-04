import { describe, expect, it } from "vitest";

import {
  aggregatePipelineStageStates,
  buildPipelineStageStates,
  classifyPipelineError,
  currentStageLabel,
  estimateRemainingSeconds,
  normalizePipelineNode,
  runProgressPct,
} from "@/lib/pipeline-progress";
import type { PipelineRun } from "@/types/api";

function makeRun(overrides: Partial<PipelineRun> = {}): PipelineRun {
  return {
    run_id: "run-1",
    ticker: "NVDA",
    sector_id: "ai_semiconductors",
    status: "running",
    current_node: "analyze",
    error: null,
    created_at: "2026-05-25T10:00:00Z",
    started_at: "2026-05-25T10:01:00Z",
    finished_at: null,
    signal_card_id: null,
    node_executions: [],
    ...overrides,
  };
}

describe("pipeline progress helpers", () => {
  it("normalizes backend labels to canonical stages", () => {
    expect(normalizePipelineNode("Fetching data (news, prices, SEC filings, macro)")).toBe("fetch");
    expect(normalizePipelineNode("Validating analysis (numbers + reasoning)")).toBe("validate");
  });

  it("marks previous stages complete and the current stage running", () => {
    const states = buildPipelineStageStates(makeRun({ current_node: "validate" }));
    expect(states.find((stage) => stage.node === "fetch")?.status).toBe("completed");
    expect(states.find((stage) => stage.node === "analyze")?.status).toBe("completed");
    expect(states.find((stage) => stage.node === "validate")?.status).toBe("running");
  });

  it("calculates partial progress before a run is complete", () => {
    const pct = runProgressPct(makeRun({ current_node: "analyze" }));
    expect(pct).toBeGreaterThan(40);
    expect(pct).toBeLessThan(70);
  });

  it("returns terminal labels and progress for completed runs", () => {
    const run = makeRun({ status: "completed", current_node: "save", finished_at: "2026-05-25T10:07:00Z" });
    expect(currentStageLabel(run)).toBe("Report ready");
    expect(runProgressPct(run)).toBe(100);
  });

  it("treats errored running rows as failed", () => {
    const run = makeRun({
      status: "running",
      current_node: "summarize",
      error: "LLM provider quota exceeded",
      finished_at: "2026-05-25T10:02:00Z",
    });
    const states = buildPipelineStageStates(run);
    expect(currentStageLabel(run)).toBe("Needs review");
    expect(states.find((stage) => stage.node === "summarize")?.status).toBe("failed");
  });

  it("aggregates mixed analyst lanes into a live topology", () => {
    const states = aggregatePipelineStageStates([
      makeRun({ run_id: "a", current_node: "validate" }),
      makeRun({ run_id: "b", current_node: "analyze" }),
    ]);
    expect(states.find((stage) => stage.node === "analyze")?.status).toBe("running");
    expect(states.find((stage) => stage.node === "validate")?.status).toBe("running");
    expect(states.find((stage) => stage.node === "save")?.status).toBe("pending");
  });

  it("estimates remaining time for pending and running runs", () => {
    expect(estimateRemainingSeconds(makeRun({ status: "pending", started_at: null }))).toBeGreaterThan(0);
    expect(estimateRemainingSeconds(makeRun(), new Date("2026-05-25T10:03:00Z"))).toBeGreaterThan(0);
  });

  it("classifies OpenRouter quota failures without leaking provider URLs", () => {
    const issue = classifyPipelineError(
      "LLM call failed (google/gemma via openrouter): Error code: 403 - {'error': {'message': 'Key limit exceeded (total limit). Manage it using https://openrouter.ai/workspaces/default/keys/abc123'}}"
    );
    expect(issue?.title).toBe("LLM quota exceeded");
    expect(issue?.detail).toContain(":free model");
    expect(issue?.detail).not.toContain("openrouter.ai/workspaces");
  });
});