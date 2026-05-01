import { describe, expect, it } from "vitest";

import { splitSections } from "@/lib/parse-analysis";

describe("splitSections", () => {
  it("returns a remainder-only result when there are no headings", () => {
    const out = splitSections("just some prose");
    expect(out.remainder).toBe("just some prose");
    expect(out.thesis).toBeUndefined();
  });

  it("extracts each canonical section", () => {
    const md = [
      "intro text",
      "## Thesis",
      "the core thesis",
      "",
      "## Evidence",
      "data point 1",
      "## Chain of Thought",
      "step a → step b",
      "## Risk Assessment",
      "downside scenario",
      "## Predictions",
      "NVDA: bullish",
    ].join("\n");

    const out = splitSections(md);
    expect(out.remainder).toBe("intro text");
    expect(out.thesis).toBe("the core thesis");
    expect(out.evidence).toBe("data point 1");
    expect(out.chainOfThought).toBe("step a → step b");
    expect(out.riskAssessment).toBe("downside scenario");
    expect(out.predictions).toBe("NVDA: bullish");
  });

  it("handles 'Price Predictions' alias", () => {
    const md = "## Price Predictions\nNVDA up 5%";
    expect(splitSections(md).predictions).toBe("NVDA up 5%");
  });

  it("handles dashed Chain-of-Thought variant", () => {
    const md = "## Chain-of-Thought\nreasoning here";
    expect(splitSections(md).chainOfThought).toBe("reasoning here");
  });

  it("ignores headings that aren't on their own line", () => {
    const md = "see ## Thesis above for details";
    expect(splitSections(md).thesis).toBeUndefined();
  });

  it("returns empty object-like result for empty input", () => {
    const out = splitSections("");
    expect(out).toEqual({ remainder: "" });
  });
});
