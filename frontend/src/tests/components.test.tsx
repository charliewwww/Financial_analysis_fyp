/**
 * Component rendering tests.
 *
 * Strategy: render each component with minimal props, assert that key content
 * appears in the DOM.  Network calls are mocked via vi.mock so no real fetch
 * occurs.  TanStack Query is wrapped with a test-scoped QueryClient so cache
 * state does not leak between tests.
 */

import { cleanup, render, screen, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { AccuracyStats, ReportSummary, SignalCard } from "@/types/api";
import React from "react";

afterEach(() => {
  cleanup();
});

// ── Test helpers ──────────────────────────────────────────────────────────────

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

function renderWithQuery(ui: React.ReactElement) {
  return render(ui, { wrapper });
}

// ── Fixtures ──────────────────────────────────────────────────────────────────

function makeCard(overrides: Partial<SignalCard> = {}): SignalCard {
  return {
    id: 1,
    ticker: "AAPL",
    run_id: null,
    signal: "BULLISH",
    conviction: 4,
    one_line: "Strong earnings expected.",
    key_catalyst: "iPhone demand surge",
    key_risk: "Supply chain risk",
    confidence: 0.85,
    signal_type: "earnings",
    validation_score: "8/10",
    supply_chain_impact: [{ ticker: "TSM", direction: "▲", reason: "Chip demand" }],
    sources: [{ url: "https://example.com", title: "Reuters article", domain: "reuters.com" }],
    numerical_claims: [{ claim: "Revenue +12%", verified: true, source: "10-K" }],
    sector_context: null,
    created_at: "2026-04-30T09:00:00Z",
    status: "active",
    ...overrides,
  };
}

function makeReportSummary(overrides: Partial<ReportSummary> = {}): ReportSummary {
  return {
    id: 10,
    sector_id: "technology",
    sector_name: "Technology",
    created_at: "2026-04-30T00:00:00Z",
    status: "active",
    confidence_score: 0.8,
    validation_status: "passed",
    news_used: 12,
    ...overrides,
  };
}

function makeAccuracyStats(overrides: Partial<AccuracyStats> = {}): AccuracyStats {
  return {
    total: 20,
    checked: 15,
    unchecked: 5,
    direction_correct: 10,
    direction_incorrect: 5,
    direction_accuracy_pct: 66.7,
    avg_absolute_error_pct: 3.2,
    by_signal_type: {
      earnings: { total: 10, correct: 7, accuracy_pct: 70.0 },
      macro: { total: 5, correct: 3, accuracy_pct: 60.0 },
    },
    ...overrides,
  };
}

// ── SignalCardItem ────────────────────────────────────────────────────────────

describe("SignalCardItem", () => {
  // Dynamic import to avoid RSC issues in Vitest
  it("renders ticker and signal badge", async () => {
    const { SignalCardItem } = await import("@/components/SignalCard");
    render(<SignalCardItem card={makeCard()} />);
    expect(screen.getByText("AAPL")).toBeInTheDocument();
    expect(screen.getByText("BULLISH")).toBeInTheDocument();
  });

  it("renders one_line summary", async () => {
    const { SignalCardItem } = await import("@/components/SignalCard");
    render(<SignalCardItem card={makeCard()} />);
    expect(screen.getByText("Strong earnings expected.")).toBeInTheDocument();
  });

  it("renders key catalyst and risk", async () => {
    const { SignalCardItem } = await import("@/components/SignalCard");
    render(<SignalCardItem card={makeCard()} />);
    expect(screen.getByText("iPhone demand surge")).toBeInTheDocument();
    expect(screen.getByText("Supply chain risk")).toBeInTheDocument();
  });

  it("renders supply chain badge with direction", async () => {
    const { SignalCardItem } = await import("@/components/SignalCard");
    render(<SignalCardItem card={makeCard()} />);
    expect(screen.getByText("▲ TSM")).toBeInTheDocument();
  });

  it("shows BEARISH badge in red variant", async () => {
    const { SignalCardItem } = await import("@/components/SignalCard");
    render(<SignalCardItem card={makeCard({ signal: "BEARISH" })} />);
    const badge = screen.getByText("BEARISH");
    expect(badge.className).toContain("red");
  });

  it("shows NEUTRAL badge in amber variant", async () => {
    const { SignalCardItem } = await import("@/components/SignalCard");
    render(<SignalCardItem card={makeCard({ signal: "NEUTRAL" })} />);
    const badge = screen.getByText("NEUTRAL");
    expect(badge.className).toContain("amber");
  });

  it("renders confidence percentage", async () => {
    const { SignalCardItem } = await import("@/components/SignalCard");
    render(<SignalCardItem card={makeCard({ confidence: 0.85 })} />);
    expect(screen.getByText("85% conf.")).toBeInTheDocument();
  });

  it("links to the signal detail page", async () => {
    const { SignalCardItem } = await import("@/components/SignalCard");
    render(<SignalCardItem card={makeCard({ id: 42 })} />);
    const link = screen.getByRole("link");
    expect(link).toHaveAttribute("href", "/signals/42");
  });

  it("renders without optional fields (all null)", async () => {
    const { SignalCardItem } = await import("@/components/SignalCard");
    const minCard = makeCard({
      one_line: null,
      key_catalyst: null,
      key_risk: null,
      confidence: null,
      supply_chain_impact: null,
    });
    render(<SignalCardItem card={minCard} />);
    // At minimum ticker and signal must appear
    expect(screen.getByText("AAPL")).toBeInTheDocument();
    expect(screen.getByText("BULLISH")).toBeInTheDocument();
  });
});

// ── ReportTable ───────────────────────────────────────────────────────────────

describe("ReportTable", () => {
  it("renders 'No reports found' when list is empty", async () => {
    const { ReportTable } = await import("@/components/ReportTable");
    render(<ReportTable reports={[]} />);
    expect(screen.getByText("No reports found.")).toBeInTheDocument();
  });

  it("renders sector name as link to report detail", async () => {
    const { ReportTable } = await import("@/components/ReportTable");
    render(<ReportTable reports={[makeReportSummary()]} />);
    const link = screen.getByRole("link", { name: "Technology" });
    expect(link).toHaveAttribute("href", "/reports/10");
  });

  it("renders confidence score as percentage", async () => {
    const { ReportTable } = await import("@/components/ReportTable");
    render(<ReportTable reports={[makeReportSummary({ confidence_score: 0.8 })]} />);
    expect(screen.getByText("80%")).toBeInTheDocument();
  });

  it("shows dash for null confidence_score", async () => {
    const { ReportTable } = await import("@/components/ReportTable");
    render(<ReportTable reports={[makeReportSummary({ confidence_score: null })]} />);
    // Multiple dashes may exist — assert at least one
    expect(screen.getAllByText("—").length).toBeGreaterThan(0);
  });

  it("renders validation_status badge", async () => {
    const { ReportTable } = await import("@/components/ReportTable");
    render(<ReportTable reports={[makeReportSummary({ validation_status: "passed" })]} />);
    expect(screen.getByText("passed")).toBeInTheDocument();
  });

  it("renders news_used count", async () => {
    const { ReportTable } = await import("@/components/ReportTable");
    render(<ReportTable reports={[makeReportSummary({ news_used: 12 })]} />);
    expect(screen.getByText("12")).toBeInTheDocument();
  });

  it("renders multiple rows", async () => {
    const { ReportTable } = await import("@/components/ReportTable");
    render(
      <ReportTable
        reports={[
          makeReportSummary({ id: 1, sector_name: "Technology" }),
          makeReportSummary({ id: 2, sector_name: "Energy" }),
        ]}
      />
    );
    expect(screen.getByText("Technology")).toBeInTheDocument();
    expect(screen.getByText("Energy")).toBeInTheDocument();
  });
});

// ── AccuracyStatsDisplay ──────────────────────────────────────────────────────

describe("AccuracyStatsDisplay", () => {
  it("renders total predictions count", async () => {
    const { AccuracyStatsDisplay } = await import("@/components/AccuracyStats");
    render(<AccuracyStatsDisplay stats={makeAccuracyStats()} />);
    expect(screen.getByText("20")).toBeInTheDocument();
  });

  it("renders direction accuracy percentage", async () => {
    const { AccuracyStatsDisplay } = await import("@/components/AccuracyStats");
    render(<AccuracyStatsDisplay stats={makeAccuracyStats()} />);
    expect(screen.getByText("66.7%")).toBeInTheDocument();
  });

  it("renders checked / total sub-label", async () => {
    const { AccuracyStatsDisplay } = await import("@/components/AccuracyStats");
    render(<AccuracyStatsDisplay stats={makeAccuracyStats()} />);
    expect(screen.getByText("10/15 checked")).toBeInTheDocument();
  });

  it("renders avg absolute error", async () => {
    const { AccuracyStatsDisplay } = await import("@/components/AccuracyStats");
    render(<AccuracyStatsDisplay stats={makeAccuracyStats()} />);
    expect(screen.getByText("3.20%")).toBeInTheDocument();
  });

  it("renders unchecked count with label", async () => {
    const { AccuracyStatsDisplay } = await import("@/components/AccuracyStats");
    render(<AccuracyStatsDisplay stats={makeAccuracyStats()} />);
    expect(screen.getByText("awaiting price data")).toBeInTheDocument();
  });

  it("renders per-signal-type breakdown table", async () => {
    const { AccuracyStatsDisplay } = await import("@/components/AccuracyStats");
    render(<AccuracyStatsDisplay stats={makeAccuracyStats()} />);
    expect(screen.getByText("earnings")).toBeInTheDocument();
    expect(screen.getByText("macro")).toBeInTheDocument();
    expect(screen.getByText("70.0%")).toBeInTheDocument();
    expect(screen.getByText("60.0%")).toBeInTheDocument();
  });

  it("hides breakdown table when by_signal_type is empty", async () => {
    const { AccuracyStatsDisplay } = await import("@/components/AccuracyStats");
    render(
      <AccuracyStatsDisplay
        stats={makeAccuracyStats({ by_signal_type: {} })}
      />
    );
    expect(screen.queryByText("By Signal Type")).not.toBeInTheDocument();
  });

  it("shows zero-state correctly", async () => {
    const { AccuracyStatsDisplay } = await import("@/components/AccuracyStats");
    const empty: AccuracyStats = {
      total: 0,
      checked: 0,
      unchecked: 0,
      direction_correct: 0,
      direction_incorrect: 0,
      direction_accuracy_pct: 0.0,
      avg_absolute_error_pct: 0.0,
      by_signal_type: {},
    };
    render(<AccuracyStatsDisplay stats={empty} />);
    expect(screen.getByText("0.0%")).toBeInTheDocument();
    expect(screen.getByText("0/0 checked")).toBeInTheDocument();
  });
});
