/**
 * Tests for src/types/api.ts
 *
 * These are pure TypeScript shape tests — we construct objects and assert
 * their properties to catch any regression in type definitions.
 * No rendering, no network calls.
 */

import { describe, expect, it } from "vitest";
import type {
  AccuracyStats,
  NodeExecution,
  PaginatedResponse,
  PipelineRun,
  Prediction,
  ReportDetail,
  ReportSummary,
  RunRequest,
  RunSummary,
  SignalCard,
  SignalTypeBreakdown,
  SSEEvent,
  UserDetail,
  UserUpdateRequest,
} from "@/types/api";

// ── Helpers ───────────────────────────────────────────────────────────────────

function makeSignalCard(overrides: Partial<SignalCard> = {}): SignalCard {
  return {
    id: 1,
    ticker: "AAPL",
    run_id: null,
    signal: "BULLISH",
    conviction: 4,
    one_line: "Strong earnings beat expected.",
    key_catalyst: "iPhone demand",
    key_risk: "Supply chain disruption",
    confidence: 0.82,
    signal_type: "earnings",
    validation_score: "8/10",
    supply_chain_impact: null,
    sources: null,
    numerical_claims: null,
    sector_context: null,
    created_at: "2026-04-30T09:00:00Z",
    status: "active",
    ...overrides,
  };
}

// ── PaginatedResponse ─────────────────────────────────────────────────────────

describe("PaginatedResponse<T>", () => {
  it("holds typed items array", () => {
    const page: PaginatedResponse<SignalCard> = {
      items: [makeSignalCard()],
      total: 1,
      page: 1,
      page_size: 12,
    };
    expect(page.items).toHaveLength(1);
    expect(page.items[0].ticker).toBe("AAPL");
  });

  it("can be empty", () => {
    const page: PaginatedResponse<SignalCard> = {
      items: [],
      total: 0,
      page: 1,
      page_size: 12,
    };
    expect(page.total).toBe(0);
    expect(page.items).toHaveLength(0);
  });
});

// ── SignalCard ────────────────────────────────────────────────────────────────

describe("SignalCard", () => {
  it("accepts all three signal values", () => {
    const signals = ["BULLISH", "BEARISH", "NEUTRAL"] as const;
    signals.forEach((s) => {
      const card = makeSignalCard({ signal: s });
      expect(card.signal).toBe(s);
    });
  });

  it("nullable fields can be null", () => {
    const card = makeSignalCard({
      conviction: null,
      confidence: null,
      supply_chain_impact: null,
      sources: null,
      numerical_claims: null,
    });
    expect(card.conviction).toBeNull();
    expect(card.confidence).toBeNull();
  });

  it("supply chain impact direction values", () => {
    const card = makeSignalCard({
      supply_chain_impact: [
        { ticker: "TSM", direction: "▲", reason: "Chip demand up" },
        { ticker: "QCOM", direction: "▼", reason: "Inventory excess" },
        { ticker: "INTC", direction: "◆", reason: "Neutral exposure" },
      ],
    });
    expect(card.supply_chain_impact).toHaveLength(3);
    expect(card.supply_chain_impact![0].direction).toBe("▲");
    expect(card.supply_chain_impact![1].direction).toBe("▼");
    expect(card.supply_chain_impact![2].direction).toBe("◆");
  });

  it("numerical claims carry verified flag", () => {
    const card = makeSignalCard({
      numerical_claims: [
        { claim: "Revenue up 12%", verified: true, source: "10-K" },
        { claim: "Margin 40%", verified: false, source: "" },
      ],
    });
    expect(card.numerical_claims![0].verified).toBe(true);
    expect(card.numerical_claims![1].verified).toBe(false);
  });
});

// ── PipelineRun ───────────────────────────────────────────────────────────────

describe("PipelineRun", () => {
  it("has expected shape", () => {
    const run: PipelineRun = {
      run_id: "abc-123",
      ticker: "AAPL",
      sector_id: "technology",
      status: "completed",
      current_node: null,
      error: null,
      created_at: "2026-04-30T08:00:00Z",
      started_at: "2026-04-30T08:00:01Z",
      finished_at: "2026-04-30T08:05:00Z",
      signal_card_id: 42,
      node_executions: [],
    };
    expect(run.status).toBe("completed");
    expect(run.signal_card_id).toBe(42);
  });

  it("node_executions can hold multiple nodes", () => {
    const nodes: NodeExecution[] = [
      { node: "fetch", label: "Fetch News", status: "completed", started_at: "t1", finished_at: "t2", error: null },
      { node: "analyze", label: "Analyze", status: "running", started_at: "t3", finished_at: null, error: null },
    ];
    const run: PipelineRun = {
      run_id: "xyz",
      ticker: "TSLA",
      sector_id: "auto",
      status: "running",
      current_node: "analyze",
      error: null,
      created_at: "t0",
      started_at: "t0",
      finished_at: null,
      signal_card_id: null,
      node_executions: nodes,
    };
    expect(run.node_executions).toHaveLength(2);
    expect(run.node_executions[1].status).toBe("running");
  });
});

// ── RunSummary ────────────────────────────────────────────────────────────────

describe("RunSummary", () => {
  it("subset of PipelineRun with no node details", () => {
    const summary: RunSummary = {
      run_id: "abc",
      ticker: "MSFT",
      sector_id: "technology",
      status: "pending",
      created_at: "2026-04-30T07:00:00Z",
      finished_at: null,
      signal_card_id: null,
    };
    expect(summary.status).toBe("pending");
  });
});

// ── RunRequest ────────────────────────────────────────────────────────────────

describe("RunRequest", () => {
  it("only ticker and sector_id are required", () => {
    const req: RunRequest = { ticker: "NVDA", sector_id: "semiconductors" };
    expect(req.ticker).toBe("NVDA");
    expect(req.agent_id).toBeUndefined();
  });

  it("accepts optional fields", () => {
    const req: RunRequest = {
      ticker: "NVDA",
      sector_id: "semiconductors",
      agent_id: 7,
      max_fetch_retries: 2,
      max_validation_retries: 3,
    };
    expect(req.max_fetch_retries).toBe(2);
  });
});

// ── SSEEvent ──────────────────────────────────────────────────────────────────

describe("SSEEvent", () => {
  it("heartbeat has null data", () => {
    const evt: SSEEvent = { event: "heartbeat", run_id: "r1", data: null };
    expect(evt.event).toBe("heartbeat");
    expect(evt.data).toBeNull();
  });

  it("node_started carries node update", () => {
    const evt: SSEEvent = {
      event: "node_started",
      run_id: "r1",
      data: { node: "fetch", label: "Fetching…", started_at: "t1" },
    };
    expect((evt.data as { node: string }).node).toBe("fetch");
  });
});

// ── Reports ───────────────────────────────────────────────────────────────────

describe("ReportSummary", () => {
  it("has required fields", () => {
    const r: ReportSummary = {
      id: 1,
      sector_id: "technology",
      sector_name: "Technology",
      created_at: "2026-04-30T00:00:00Z",
      status: "active",
      confidence_score: 0.75,
      validation_status: "passed",
      news_used: 12,
    };
    expect(r.news_used).toBe(12);
    expect(r.confidence_score).toBe(0.75);
  });

  it("optional fields can be null", () => {
    const r: ReportSummary = {
      id: 2,
      sector_id: "energy",
      sector_name: "Energy",
      created_at: "2026-04-29T00:00:00Z",
      status: "active",
      confidence_score: null,
      validation_status: null,
      news_used: 0,
    };
    expect(r.confidence_score).toBeNull();
    expect(r.validation_status).toBeNull();
  });
});

describe("ReportDetail", () => {
  it("extends ReportSummary with analysis and predictions", () => {
    const rd: ReportDetail = {
      id: 1,
      sector_id: "technology",
      sector_name: "Technology",
      created_at: "2026-04-30T00:00:00Z",
      status: "active",
      confidence_score: 0.8,
      validation_status: "passed",
      news_used: 5,
      analysis: "Strong sector momentum...",
      validation: null,
      news_summary: "Markets up this week.",
      predictions: [],
    };
    expect(rd.analysis).toBeTruthy();
    expect(rd.predictions).toHaveLength(0);
  });
});

// ── Prediction ────────────────────────────────────────────────────────────────

describe("Prediction", () => {
  it("unchecked prediction has nulls for outcome fields", () => {
    const p: Prediction = {
      id: 1,
      signal_card_id: 5,
      report_id: null,
      ticker: "AAPL",
      price_at_report: 175.5,
      change_1w_at_report: 0.02,
      price_1w_later: null,
      actual_change_1w: null,
      checked_at: null,
      prediction_correct: null,
      ai_direction: "BULLISH",
      ai_predicted_change: "+5%",
      ai_reasoning: "Strong earnings expected",
      ai_risk: "Macro uncertainty",
    };
    expect(p.prediction_correct).toBeNull();
    expect(p.price_1w_later).toBeNull();
  });

  it("checked correct prediction", () => {
    const p: Prediction = {
      id: 2,
      signal_card_id: null,
      report_id: 3,
      ticker: "MSFT",
      price_at_report: 400.0,
      change_1w_at_report: 0.01,
      price_1w_later: 420.0,
      actual_change_1w: 0.05,
      checked_at: "2026-05-07T09:00:00Z",
      prediction_correct: true,
      ai_direction: "BULLISH",
      ai_predicted_change: "+3%",
      ai_reasoning: "Cloud growth",
      ai_risk: "Competition",
    };
    expect(p.prediction_correct).toBe(true);
    expect(p.price_1w_later).toBe(420.0);
  });
});

// ── AccuracyStats ─────────────────────────────────────────────────────────────

describe("AccuracyStats", () => {
  it("empty stats shape", () => {
    const stats: AccuracyStats = {
      total: 0,
      checked: 0,
      unchecked: 0,
      direction_correct: 0,
      direction_incorrect: 0,
      direction_accuracy_pct: 0.0,
      avg_absolute_error_pct: 0.0,
      by_signal_type: {},
    };
    expect(stats.total).toBe(0);
    expect(stats.by_signal_type).toEqual({});
  });

  it("per-signal-type breakdown", () => {
    const breakdown: SignalTypeBreakdown = {
      total: 10,
      correct: 7,
      accuracy_pct: 70.0,
    };
    const stats: AccuracyStats = {
      total: 10,
      checked: 10,
      unchecked: 0,
      direction_correct: 7,
      direction_incorrect: 3,
      direction_accuracy_pct: 70.0,
      avg_absolute_error_pct: 2.5,
      by_signal_type: { earnings: breakdown },
    };
    expect(stats.by_signal_type["earnings"].accuracy_pct).toBe(70.0);
  });
});

// ── UserDetail ────────────────────────────────────────────────────────────────

describe("UserDetail", () => {
  it("full profile shape", () => {
    const u: UserDetail = {
      id: 1,
      email: "alice@example.com",
      username: "Alice",
      saved_sectors: ["semiconductors", "ev_battery"],
      preferences: { email_digest: true, default_page_size: 20 },
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-04-30T00:00:00Z",
    };
    expect(u.email).toBe("alice@example.com");
    expect(u.saved_sectors).toHaveLength(2);
    expect(u.preferences["email_digest"]).toBe(true);
  });

  it("username and updated_at can be null", () => {
    const u: UserDetail = {
      id: 2,
      email: "bob@example.com",
      username: null,
      saved_sectors: [],
      preferences: {},
      created_at: "2026-01-01T00:00:00Z",
      updated_at: null,
    };
    expect(u.username).toBeNull();
    expect(u.updated_at).toBeNull();
  });
});

describe("UserUpdateRequest", () => {
  it("all fields optional", () => {
    const req: UserUpdateRequest = {};
    expect(req.username).toBeUndefined();
    expect(req.saved_sectors).toBeUndefined();
  });

  it("partial update with sectors only", () => {
    const req: UserUpdateRequest = { saved_sectors: ["fintech"] };
    expect(req.saved_sectors).toEqual(["fintech"]);
    expect(req.username).toBeUndefined();
  });
});
