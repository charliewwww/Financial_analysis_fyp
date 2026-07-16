/**
 * Token usage + cost estimation for a pipeline run.
 *
 * The backend records the input (prompt) and output (completion) tokens a run
 * consumed, plus the model that did the bulk of the analysis. We turn that into
 * a rough dollar estimate so users can see what a run costs.
 *
 * Prices are published per-1M-token rates (USD) and change over time, so every
 * figure here is an ESTIMATE. Unknown / self-hosted models return null cost and
 * the UI shows tokens only.
 */

export interface ModelPrice {
  /** USD per 1M input (prompt) tokens. */
  inputPerM: number;
  /** USD per 1M output (completion) tokens. */
  outputPerM: number;
}

/**
 * Substring-keyed price table. The first key that appears in the (lower-cased)
 * model id wins, so order from most specific to least specific. Rates are
 * approximate public list prices as of 2026 and are clearly labelled as
 * estimates in the UI.
 */
const MODEL_PRICES: Array<[match: string, price: ModelPrice]> = [
  // Self-hosted / local — no marginal API cost.
  ["ollama", { inputPerM: 0, outputPerM: 0 }],
  ["llama3.1", { inputPerM: 0, outputPerM: 0 }],
  ["qwen2.5", { inputPerM: 0, outputPerM: 0 }],
  // DeepSeek (default production provider).
  ["deepseek-v4-pro", { inputPerM: 0.55, outputPerM: 2.19 }],
  ["deepseek-v4-flash", { inputPerM: 0.27, outputPerM: 1.1 }],
  ["deepseek-chat", { inputPerM: 0.27, outputPerM: 1.1 }],
  ["deepseek", { inputPerM: 0.27, outputPerM: 1.1 }],
  // OpenAI.
  ["gpt-4o-mini", { inputPerM: 0.15, outputPerM: 0.6 }],
  ["gpt-4o", { inputPerM: 2.5, outputPerM: 10 }],
  ["gpt-4.1-mini", { inputPerM: 0.4, outputPerM: 1.6 }],
  ["gpt-4.1", { inputPerM: 2, outputPerM: 8 }],
  // Anthropic.
  ["claude-3.5-haiku", { inputPerM: 0.8, outputPerM: 4 }],
  ["claude-3-5-haiku", { inputPerM: 0.8, outputPerM: 4 }],
  ["claude-3.5-sonnet", { inputPerM: 3, outputPerM: 15 }],
  ["claude", { inputPerM: 3, outputPerM: 15 }],
  // Google.
  ["gemini-2.0-flash", { inputPerM: 0.1, outputPerM: 0.4 }],
  ["gemini-1.5-flash", { inputPerM: 0.075, outputPerM: 0.3 }],
  ["gemini-1.5-pro", { inputPerM: 1.25, outputPerM: 5 }],
  ["gemini", { inputPerM: 0.1, outputPerM: 0.4 }],
  // Meta / Qwen via aggregators.
  ["llama-3.3-70b", { inputPerM: 0.12, outputPerM: 0.3 }],
  ["qwen-2.5-72b", { inputPerM: 0.35, outputPerM: 0.4 }],
];

/** Look up the price for a model id, or null when it is not in the table. */
export function priceForModel(model: string | null | undefined): ModelPrice | null {
  if (!model) return null;
  const id = model.toLowerCase();
  for (const [match, price] of MODEL_PRICES) {
    if (id.includes(match)) return price;
  }
  return null;
}

export interface TokenUsage {
  promptTokens: number;
  completionTokens: number;
  totalTokens: number;
  model: string;
  /** Estimated USD cost, or null when the model price is unknown. */
  estimatedCostUsd: number | null;
}

/** Build a TokenUsage summary from a signal card's fields. */
export function computeTokenUsage(input: {
  llm_prompt_tokens?: number | null;
  llm_completion_tokens?: number | null;
  llm_model?: string | null;
}): TokenUsage {
  const promptTokens = Math.max(0, Math.round(input.llm_prompt_tokens ?? 0));
  const completionTokens = Math.max(0, Math.round(input.llm_completion_tokens ?? 0));
  const model = (input.llm_model ?? "").trim();
  const price = priceForModel(model);
  const estimatedCostUsd = price
    ? (promptTokens / 1_000_000) * price.inputPerM +
      (completionTokens / 1_000_000) * price.outputPerM
    : null;
  return {
    promptTokens,
    completionTokens,
    totalTokens: promptTokens + completionTokens,
    model,
    estimatedCostUsd,
  };
}

/** True when a card carries any token accounting worth displaying. */
export function hasTokenUsage(usage: TokenUsage): boolean {
  return usage.totalTokens > 0;
}

/** Compact human token count, e.g. 12345 → "12,345", 1500000 → "1.5M". */
export function formatTokens(n: number): string {
  if (!Number.isFinite(n) || n <= 0) return "0";
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(2)}M`;
  return n.toLocaleString("en-US");
}

/** Format an estimated cost. Tiny non-zero costs show more precision. */
export function formatCostUsd(cost: number | null): string {
  if (cost == null) return "n/a";
  if (cost === 0) return "$0.00";
  if (cost < 0.01) return `$${cost.toFixed(4)}`;
  return `$${cost.toFixed(2)}`;
}
