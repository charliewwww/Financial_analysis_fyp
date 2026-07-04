/**
 * Component rendering tests.
 *
 * Strategy: render each component with minimal props, assert that key content
 * appears in the DOM.  Network calls are mocked via vi.mock so no real fetch
 * occurs.  TanStack Query is wrapped with a test-scoped QueryClient so cache
 * state does not leak between tests.
 */

import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { AccuracyStats, AgentSummary, ReportSummary, SignalCard } from "@/types/api";
import React from "react";
import { MarketProvider } from "@/lib/market-context";
import { OvernightProvider } from "@/components/overnight/OvernightContext";

vi.mock("@/lib/api", () => ({
  askSignalEvidence: vi.fn(),
  createAgentSkill: vi.fn(),
  fetchAgents: vi.fn(),
  fetchLatestSignal: vi.fn(),
  fetchChiefVerdict: vi.fn(),
  fetchChiefVerdictAccuracy: vi.fn(),
  fetchWatchlist: vi.fn(),
  addToWatchlist: vi.fn(),
  removeFromWatchlist: vi.fn(),
  fetchMarkets: vi.fn(),
  fetchMarketSectorCatalog: vi.fn(),
  fetchModelCatalog: vi.fn(),
  fetchVectorDbStats: vi.fn(),
  fetchSignalCard: vi.fn(),
  fetchRun: vi.fn(),
  fetchSectors: vi.fn(),
  fetchSignals: vi.fn(),
  fetchRuns: vi.fn(),
  triggerBoardRun: vi.fn(),
  triggerSectorBoardRun: vi.fn(),
  triggerSectorSynthesis: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  usePathname: () => "/",
}));

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

// ── Test helpers ──────────────────────────────────────────────────────────────

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return (
    <QueryClientProvider client={qc}>
      <MarketProvider>
        <OvernightProvider>{children}</OvernightProvider>
      </MarketProvider>
    </QueryClientProvider>
  );
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
    agent_id: 1,
    signal: "BULLISH",
    conviction: 4,
    one_line: "Strong earnings expected.",
    key_catalyst: "iPhone demand surge",
    key_risk: "Supply chain risk",
    confidence: 0.85,
    signal_type: "earnings",
    conviction_stated: true,
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

function makeAgent(overrides: Partial<AgentSummary> = {}): AgentSummary {
  return {
    id: 1,
    name: "Supply Chain Analyst",
    description: "Supply chain lens",
    is_builtin: true,
    created_at: "2026-04-30T09:00:00Z",
    updated_at: null,
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

  it("renders evidence percentage", async () => {
    const { SignalCardItem } = await import("@/components/SignalCard");
    render(<SignalCardItem card={makeCard({ confidence: 0.85 })} />);
    expect(screen.getByText("85% evidence")).toBeInTheDocument();
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

  it("renders confidence score on the report scale", async () => {
    const { ReportTable } = await import("@/components/ReportTable");
    render(<ReportTable reports={[makeReportSummary({ confidence_score: 0.8 })]} />);
    // Rendered in both the desktop table and the mobile card stack.
    expect(screen.getAllByText("8.0/10").length).toBeGreaterThan(0);
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
    expect(screen.getAllByText("passed").length).toBeGreaterThan(0);
  });

  it("renders news_used count", async () => {
    const { ReportTable } = await import("@/components/ReportTable");
    render(<ReportTable reports={[makeReportSummary({ news_used: 12 })]} />);
    expect(screen.getAllByText("12").length).toBeGreaterThan(0);
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
    expect(screen.getAllByText("Technology").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Energy").length).toBeGreaterThan(0);
  });
});

// ── AccuracyStatsDisplay ──────────────────────────────────────────────────────

describe("SignalEvidenceChat", () => {
  it("posts a suggested evidence question and renders the answer", async () => {
    const api = await import("@/lib/api");
    vi.mocked(api.askSignalEvidence).mockResolvedValue({
      answer: "Demand rose according to the source pack.",
      citations: [
        {
          label: "source: reuters.com",
          source_type: "source",
          source: "reuters.com",
          url: "https://example.com",
          quote: "Demand rose.",
        },
      ],
      limitations: [],
      grounded: true,
      suggested_questions: ["What would invalidate this?"],
    });

    const { SignalEvidenceChat } = await import("@/components/SignalEvidenceChat");
    renderWithQuery(<SignalEvidenceChat cardId={7} ticker="NVDA" />);

    fireEvent.click(screen.getByRole("button", { name: "What changed?" }));

    await waitFor(() => {
      expect(api.askSignalEvidence).toHaveBeenCalledWith(7, expect.objectContaining({ question: "What changed?" }));
    });
    expect(await screen.findByText("Demand rose according to the source pack.")).toBeInTheDocument();
    expect(await screen.findByText("source: reuters.com")).toBeInTheDocument();
  });

  it("disables input when no card is selected", async () => {
    const { SignalEvidenceChat } = await import("@/components/SignalEvidenceChat");
    renderWithQuery(<SignalEvidenceChat cardId={null} />);
    expect(screen.getByLabelText("Evidence question")).toBeDisabled();
    expect(screen.getByText("A current signal card is needed before chat can answer from evidence.")).toBeInTheDocument();
  });
});

describe("FloatingEvidenceChat", () => {
  it("opens as a bottom-right chat dock and targets the latest ticker card", async () => {
    const api = await import("@/lib/api");
    vi.mocked(api.fetchLatestSignal).mockResolvedValue(makeCard({ id: 7, ticker: "NVDA" }));
    vi.mocked(api.askSignalEvidence).mockResolvedValue({
      answer: "The latest evidence is reviewable.",
      citations: [],
      limitations: [],
      grounded: true,
      suggested_questions: [],
    });

    const { FloatingEvidenceChat } = await import("@/components/FloatingEvidenceChat");
    renderWithQuery(<FloatingEvidenceChat />);

    fireEvent.click(screen.getByRole("button", { name: /open evidence chat/i }));
    expect(await screen.findByText("Latest NVDA card")).toBeInTheDocument();
    await waitFor(() => expect(api.fetchLatestSignal).toHaveBeenCalledWith("NVDA"));

    fireEvent.click(await screen.findByRole("button", { name: "What changed?" }));
    await waitFor(() => {
      expect(api.askSignalEvidence).toHaveBeenCalledWith(7, expect.objectContaining({ question: "What changed?" }));
    });
    expect(await screen.findByText("The latest evidence is reviewable.")).toBeInTheDocument();
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

// ── AgentGallery ─────────────────────────────────────────────────────────────

describe("AgentGallery", () => {
  it("creates a custom skill-backed agent", async () => {
    const api = await import("@/lib/api");
    vi.mocked(api.fetchAgents).mockResolvedValue([
      makeAgent({ id: 1, name: "Supply Chain Analyst" }),
    ]);
    vi.mocked(api.createAgentSkill).mockResolvedValue(
      makeAgent({ id: 5, name: "Options Flow Analyst", is_builtin: false })
    );

    const { AgentGallery } = await import("@/components/AgentGallery");
    renderWithQuery(<AgentGallery />);

    fireEvent.change(await screen.findByLabelText("Agent name"), {
      target: { value: "Options Flow Analyst" },
    });
    fireEvent.change(screen.getByLabelText("Description"), {
      target: { value: "Tracks volatility and dealer positioning." },
    });
    fireEvent.change(screen.getByLabelText("Skill instructions"), {
      target: {
        value: "Focus on options flow, implied volatility, dealer gamma, and positioning changes.",
      },
    });
    fireEvent.click(screen.getByRole("button", { name: /create skill/i }));

    await waitFor(() => expect(api.createAgentSkill).toHaveBeenCalledWith({
      name: "Options Flow Analyst",
      description: "Tracks volatility and dealer positioning.",
      skill_name: "Options Flow Analyst Skill",
      skill_type: "domain",
      skill_content: "Focus on options flow, implied volatility, dealer gamma, and positioning changes.",
    }));
    expect(await screen.findByText("Skill agent created. It will join the next board run.")).toBeInTheDocument();
  });
});

// ── TickerBoard ───────────────────────────────────────────────────────────────

describe("TickerBoard", () => {
  it("launches a board fanout for the current ticker", async () => {
    const api = await import("@/lib/api");
    vi.mocked(api.fetchAgents).mockResolvedValue([
      makeAgent({ id: 1, name: "Supply Chain Analyst" }),
      makeAgent({ id: 2, name: "Value Analyst", description: "Value lens" }),
    ]);
    vi.mocked(api.fetchSignals).mockResolvedValue({
      items: [],
      total: 0,
      page: 1,
      page_size: 50,
    });
    vi.mocked(api.fetchRuns).mockResolvedValue({
      items: [],
      total: 0,
      page: 1,
      page_size: 8,
    });
    vi.mocked(api.fetchSectors).mockResolvedValue([
      { id: "ai_semiconductors", name: "AI Infrastructure", tickers: ["NVDA", "AMD"] },
    ]);
    vi.mocked(api.fetchRun).mockImplementation(async (runId: string) => ({
      run_id: runId,
      ticker: "NVDA",
      sector_id: "ai_semiconductors",
      status: "pending",
      current_node: null,
      error: null,
      created_at: "2026-04-30T09:00:00Z",
      started_at: null,
      finished_at: null,
      signal_card_id: null,
      node_executions: [],
    }));
    vi.mocked(api.triggerBoardRun).mockResolvedValue({
      ticker: "NVDA",
      sector_id: "ai_semiconductors",
      dry_run: false,
      runs: [
        { run_id: "r-1", agent_id: 1, agent_name: "Supply Chain Analyst", status: "pending" },
        { run_id: "r-2", agent_id: 2, agent_name: "Value Analyst", status: "pending" },
      ],
    });

    const { TickerBoard } = await import("@/components/TickerBoard");
    renderWithQuery(<TickerBoard />);

    const button = await screen.findByRole("button", { name: /run board/i });
    await waitFor(() => expect(button).not.toBeDisabled());
    fireEvent.click(button);

    await waitFor(() => {
      expect(api.triggerBoardRun).toHaveBeenCalledWith({ ticker: "NVDA" });
    });
    expect(await screen.findByText("Launched 2 analyst runs for NVDA.")).toBeInTheDocument();
  });

  it("launches sector mode through one synthesis request", async () => {
    const api = await import("@/lib/api");
    vi.mocked(api.fetchAgents).mockResolvedValue([
      makeAgent({ id: 1, name: "Supply Chain Analyst" }),
      makeAgent({ id: 2, name: "Value Analyst", description: "Value lens" }),
    ]);
    vi.mocked(api.fetchSignals).mockResolvedValue({
      items: [],
      total: 0,
      page: 1,
      page_size: 50,
    });
    vi.mocked(api.fetchRuns).mockResolvedValue({
      items: [],
      total: 0,
      page: 1,
      page_size: 8,
    });
    vi.mocked(api.fetchSectors).mockResolvedValue([
      { id: "ai_semiconductors", name: "AI Infrastructure", tickers: ["NVDA", "AMD"] },
    ]);
    vi.mocked(api.fetchRun).mockImplementation(async (runId: string) => ({
      run_id: runId,
      ticker: runId.includes("amd") ? "AMD" : "NVDA",
      sector_id: "ai_semiconductors",
      status: "pending",
      current_node: null,
      error: null,
      created_at: "2026-04-30T09:00:00Z",
      started_at: null,
      finished_at: null,
      signal_card_id: null,
      node_executions: [],
    }));
    vi.mocked(api.triggerSectorSynthesis).mockResolvedValue({
      run_id: "sector-syn-1",
      sector_id: "ai_semiconductors",
      sector_label: "AI Infrastructure",
      status: "pending",
    });

    vi.mocked(api.fetchMarketSectorCatalog).mockResolvedValue({
      market: { id: "us", name: "United States", currency: "USD" },
      sectors: [
        {
          id: "ai_semiconductors",
          name: "AI Infrastructure",
          instrument: "SOXX",
          instrument_name: "Semiconductors",
          constituents: ["NVDA", "AMD"],
        },
      ],
    });

    const { TickerBoard } = await import("@/components/TickerBoard");
    renderWithQuery(<TickerBoard />);

    fireEvent.click(await screen.findByRole("button", { name: "Sector" }));
    const button = await screen.findByRole("button", { name: /run sector/i });
    await waitFor(() => expect(button).not.toBeDisabled());
    fireEvent.click(button);

    await waitFor(() => {
      expect(api.triggerSectorSynthesis).toHaveBeenCalledWith({
        sector_id: "ai_semiconductors",
        model: undefined,
      });
    });
    expect(api.triggerBoardRun).not.toHaveBeenCalled();
    expect(await screen.findByText(/Launched a sector synthesis for AI Infrastructure/i)).toBeInTheDocument();
  });

  it("shows active backend run progress after a refresh", async () => {
    const api = await import("@/lib/api");
    vi.mocked(api.fetchAgents).mockResolvedValue([
      makeAgent({ id: 1, name: "Supply Chain Analyst" }),
    ]);
    vi.mocked(api.fetchSignals).mockResolvedValue({
      items: [],
      total: 0,
      page: 1,
      page_size: 50,
    });
    vi.mocked(api.fetchRuns).mockResolvedValue({
      items: [
        {
          run_id: "active-run-1",
          ticker: "NVDA",
          sector_id: "ai_semiconductors",
          status: "running",
          created_at: "2026-05-25T09:00:00Z",
          finished_at: null,
          signal_card_id: null,
        },
      ],
      total: 1,
      page: 1,
      page_size: 8,
    });
    vi.mocked(api.fetchSectors).mockResolvedValue([
      { id: "ai_semiconductors", name: "AI Infrastructure", tickers: ["NVDA", "AMD"] },
    ]);
    vi.mocked(api.fetchRun).mockResolvedValue({
      run_id: "active-run-1",
      ticker: "NVDA",
      sector_id: "ai_semiconductors",
      status: "running",
      current_node: "analyze",
      error: null,
      created_at: "2026-05-25T09:00:00Z",
      started_at: "2026-05-25T09:01:00Z",
      finished_at: null,
      signal_card_id: null,
      node_executions: [],
    });

    const { TickerBoard } = await import("@/components/TickerBoard");
    renderWithQuery(<TickerBoard />);

    expect(await screen.findByText("Analysis progress")).toBeInTheDocument();
    expect(await screen.findByText("Pipeline blueprint")).toBeInTheDocument();
    await waitFor(() => expect(screen.getAllByText("Analyst reasoning").length).toBeGreaterThan(0));
  });

  it("explains provider quota failures in active run progress", async () => {
    const api = await import("@/lib/api");
    vi.mocked(api.fetchAgents).mockResolvedValue([
      makeAgent({ id: 1, name: "Supply Chain Analyst" }),
    ]);
    vi.mocked(api.fetchSignals).mockResolvedValue({
      items: [],
      total: 0,
      page: 1,
      page_size: 50,
    });
    vi.mocked(api.fetchRuns).mockResolvedValue({
      items: [],
      total: 0,
      page: 1,
      page_size: 8,
    });
    vi.mocked(api.fetchSectors).mockResolvedValue([
      { id: "ai_semiconductors", name: "AI Infrastructure", tickers: ["NVDA", "AMD"] },
    ]);
    vi.mocked(api.fetchRun).mockResolvedValue({
      run_id: "failed-run-1",
      ticker: "NVDA",
      sector_id: "ai_semiconductors",
      status: "failed",
      current_node: "summarize",
      error: "LLM call failed via openrouter: Error code: 403 - Key limit exceeded (total limit). Manage it using https://openrouter.ai/workspaces/default/keys/abc123",
      created_at: "2026-05-25T09:00:00Z",
      started_at: "2026-05-25T09:00:10Z",
      finished_at: "2026-05-25T09:01:00Z",
      signal_card_id: null,
      node_executions: [],
    });
    vi.mocked(api.triggerBoardRun).mockResolvedValue({
      ticker: "NVDA",
      sector_id: "ai_semiconductors",
      dry_run: false,
      runs: [
        { run_id: "failed-run-1", agent_id: 1, agent_name: "Supply Chain Analyst", status: "pending" },
      ],
    });

    const { TickerBoard } = await import("@/components/TickerBoard");
    renderWithQuery(<TickerBoard />);

    const button = await screen.findByRole("button", { name: /run board/i });
    await waitFor(() => expect(button).not.toBeDisabled());
    fireEvent.click(button);

    await waitFor(() => expect(screen.getAllByText(/LLM quota exceeded/i).length).toBeGreaterThan(0));
    expect(screen.getAllByText(/current API key is out of credits/i).length).toBeGreaterThan(0);
    expect(screen.queryByText(/openrouter\.ai\/workspaces/i)).not.toBeInTheDocument();
  });

  it("does not pin historical failed rows as active progress", async () => {
    const api = await import("@/lib/api");
    vi.mocked(api.fetchAgents).mockResolvedValue([
      makeAgent({ id: 1, name: "Supply Chain Analyst" }),
    ]);
    vi.mocked(api.fetchSignals).mockResolvedValue({
      items: [],
      total: 0,
      page: 1,
      page_size: 50,
    });
    vi.mocked(api.fetchRuns).mockResolvedValue({
      items: [
        {
          run_id: "old-failed-run",
          ticker: "NVDA",
          sector_id: "ai_semiconductors",
          status: "running",
          created_at: "2026-05-25T09:00:00Z",
          finished_at: "2026-05-25T09:01:00Z",
          error: "LLM provider quota exceeded",
          signal_card_id: null,
        },
      ],
      total: 1,
      page: 1,
      page_size: 8,
    });
    vi.mocked(api.fetchSectors).mockResolvedValue([
      { id: "ai_semiconductors", name: "AI Infrastructure", tickers: ["NVDA", "AMD"] },
    ]);

    const { TickerBoard } = await import("@/components/TickerBoard");
    renderWithQuery(<TickerBoard />);

    await waitFor(() => expect(api.fetchRuns).toHaveBeenCalled());
    expect(screen.queryByText("Analysis progress")).not.toBeInTheDocument();
    expect(api.fetchRun).not.toHaveBeenCalledWith("old-failed-run");
  });
});
