import { describe, expect, it } from "vitest";

import {
  computeTokenUsage,
  formatCostUsd,
  formatTokens,
  hasTokenUsage,
  priceForModel,
} from "@/lib/token-cost";

describe("priceForModel", () => {
  it("matches known models by substring", () => {
    expect(priceForModel("deepseek-v4-pro")).toEqual({ inputPerM: 0.55, outputPerM: 2.19 });
    expect(priceForModel("openai/gpt-4o-mini")).toEqual({ inputPerM: 0.15, outputPerM: 0.6 });
    expect(priceForModel("anthropic/claude-3.5-haiku")).toEqual({ inputPerM: 0.8, outputPerM: 4 });
  });

  it("treats self-hosted models as free", () => {
    expect(priceForModel("ollama/llama3.1")).toEqual({ inputPerM: 0, outputPerM: 0 });
  });

  it("returns null for unknown models", () => {
    expect(priceForModel("some-private-model-xyz")).toBeNull();
    expect(priceForModel("")).toBeNull();
    expect(priceForModel(null)).toBeNull();
  });
});

describe("computeTokenUsage", () => {
  it("sums tokens and estimates cost for a known model", () => {
    const usage = computeTokenUsage({
      llm_prompt_tokens: 1_000_000,
      llm_completion_tokens: 500_000,
      llm_model: "deepseek-v4-flash",
    });
    expect(usage.promptTokens).toBe(1_000_000);
    expect(usage.completionTokens).toBe(500_000);
    expect(usage.totalTokens).toBe(1_500_000);
    // 1M * 0.27 + 0.5M * 1.10 = 0.27 + 0.55 = 0.82
    expect(usage.estimatedCostUsd).toBeCloseTo(0.82, 5);
  });

  it("returns null cost for an unknown model but still counts tokens", () => {
    const usage = computeTokenUsage({
      llm_prompt_tokens: 1234,
      llm_completion_tokens: 567,
      llm_model: "mystery-model",
    });
    expect(usage.totalTokens).toBe(1801);
    expect(usage.estimatedCostUsd).toBeNull();
  });

  it("handles missing fields", () => {
    const usage = computeTokenUsage({});
    expect(usage.totalTokens).toBe(0);
    expect(hasTokenUsage(usage)).toBe(false);
  });
});

describe("formatTokens", () => {
  it("formats counts", () => {
    expect(formatTokens(0)).toBe("0");
    expect(formatTokens(12_345)).toBe("12,345");
    expect(formatTokens(1_500_000)).toBe("1.50M");
  });
});

describe("formatCostUsd", () => {
  it("formats costs at appropriate precision", () => {
    expect(formatCostUsd(null)).toBe("n/a");
    expect(formatCostUsd(0)).toBe("$0.00");
    expect(formatCostUsd(0.0032)).toBe("$0.0032");
    expect(formatCostUsd(1.239)).toBe("$1.24");
  });
});
