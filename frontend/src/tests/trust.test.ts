import { describe, expect, it } from "vitest";
import type { Signal, SignalCard } from "@/types/api";
import {
  analystAgreement,
  buildTickerTrustSummary,
  evaluateSignalCard,
  isMeaningfulText,
  sourceIdentity,
} from "@/lib/trust";

function makeCard(overrides: Partial<SignalCard> = {}): SignalCard {
  return {
    id: 1,
    ticker: "NVDA",
    run_id: "run-1",
    agent_id: 1,
    signal: "BULLISH",
    conviction: 4,
    one_line: "NVDA demand remains supported by verified data-center accelerator orders.",
    key_catalyst: "Hyperscaler demand and confirmed capacity expansion support the near-term revenue path.",
    key_risk: "Export controls or weaker cloud capex could invalidate the bullish thesis.",
    confidence: 0.82,
    signal_type: "FUNDAMENTAL_SHIFT",
    conviction_stated: true,
    validation_score: "2/2 claims verified",
    supply_chain_impact: [{ ticker: "TSM", direction: "▲", reason: "Packaging capacity demand" }],
    sources: [{ url: "https://example.com/nvda", title: "Source", domain: "example.com" }],
    numerical_claims: [
      { claim: "Revenue grew 20%", verified: true, source: "10-Q" },
      { claim: "Capacity expanded 15%", verified: true, source: "Supplier filing" },
    ],
    sector_context: null,
    created_at: "2026-05-21T09:00:00Z",
    status: "active",
    ...overrides,
  };
}

function cards(signals: Signal[]): SignalCard[] {
  return signals.map((signal, index) => makeCard({ id: index + 1, agent_id: index + 1, signal }));
}

describe("trust helpers", () => {
  it("rejects metadata as meaningful investor text", () => {
    expect(isMeaningfulText("**Date:** May 6, 2026")).toBe(false);
    expect(isMeaningfulText("**Analyst:** MarketPulse Risk Analyst")).toBe(false);
    expect(isMeaningfulText("Role:** Adversarial Risk Analyst — Downside paths")).toBe(false);
  });

  it("treats 2 of 4 as a mixed board, not consensus", () => {
    const agreement = analystAgreement(cards(["BULLISH", "BULLISH", "BEARISH", "BEARISH"]), 4);
    expect(agreement.signal).toBe("MIXED");
    expect(agreement.required).toBe(3);
  });

  it("unlocks recommendation only for fresh, complete, aligned evidence", () => {
    const summary = buildTickerTrustSummary(cards(["BULLISH", "BULLISH", "BULLISH", "NEUTRAL"]), 4, new Date("2026-05-21T10:00:00Z"));
    expect(summary.state).toBe("actionable");
    expect(summary.recommendationAllowed).toBe(true);
    expect(summary.posture).toBe("BULLISH");
  });

  it("keeps recommendation locked when claim checks are missing", () => {
    const unchecked = cards(["BULLISH", "BULLISH", "BULLISH", "NEUTRAL"]).map((card) => ({
      ...card,
      numerical_claims: [],
      validation_score: "PASSED",
    }));
    const summary = buildTickerTrustSummary(unchecked, 4, new Date("2026-05-21T10:00:00Z"));
    expect(summary.recommendationAllowed).toBe(false);
    expect(summary.reasons).toContain("No numerical claim checks are attached yet.");
  });

  it("keeps recommendation locked without complete analyst coverage", () => {
    const summary = buildTickerTrustSummary(cards(["BULLISH", "BULLISH", "BULLISH"]), 4, new Date("2026-05-21T10:00:00Z"));
    expect(summary.recommendationAllowed).toBe(false);
    expect(summary.reasons).toContain("Only 3/4 analyst lanes have cards.");
  });

  it("locks stale cards even when evidence is otherwise complete", () => {
    const summary = buildTickerTrustSummary(cards(["BULLISH", "BULLISH", "BULLISH", "NEUTRAL"]), 4, new Date("2026-05-25T10:00:00Z"));
    expect(summary.state).toBe("stale");
    expect(summary.recommendationAllowed).toBe(false);
  });

  it("flags incomplete cards as weak evidence", () => {
    const evaluation = evaluateSignalCard(makeCard({ key_catalyst: null, key_risk: null, sources: [] }), new Date("2026-05-21T10:00:00Z"));
    expect(evaluation.evidenceQuality).toBe("weak");
    expect(evaluation.reasons).toContain("catalyst missing");
    expect(evaluation.reasons).toContain("risk missing");
  });

  it("derives publisher identity from Google News-style titles", () => {
    expect(sourceIdentity({ url: "https://news.google.com/rss/articles/x", title: "NVDA rallies - CNBC", domain: "news.google.com" })).toBe("CNBC");
  });

  it("tracks publisher breadth separately from article count", () => {
    const evaluation = evaluateSignalCard(makeCard({
      sources: [
        { url: "https://news.google.com/rss/articles/a", title: "NVDA rallies - CNBC", domain: "news.google.com" },
        { url: "https://news.google.com/rss/articles/b", title: "NVDA slips - Reuters", domain: "news.google.com" },
      ],
    }), new Date("2026-05-21T10:00:00Z"));
    expect(evaluation.sourceCount).toBe(2);
    expect(evaluation.sourceDomainCount).toBe(2);
  });
});
