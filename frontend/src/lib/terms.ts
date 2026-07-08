/**
 * MarketPulse term definitions.
 *
 * Every short-form, ticker, or jargon word that a general-public user might
 * not understand has a plain-language entry here. The <Term> component looks
 * up these entries by key and renders an inline, hover-to-explain annotation
 * — no separate glossary page needed.
 *
 * Keep definitions to ONE sentence. The goal is "oh, I get it" in 2 seconds.
 */

export interface TermDefinition {
  /** The plain-language explanation shown on hover/focus. */
  definition: string;
  /** Optional category for styling (tickers get monospace styling). */
  kind?: "ticker" | "concept" | "product";
  /** Optional link to a relevant page for deeper exploration. */
  href?: string;
}

export const TERMS: Record<string, TermDefinition> = {
  // ── Tickers — AI & Semiconductors ──────────────────────────────────────────
  NVDA: {
    definition: "Nvidia — designs the GPUs that power most AI training and inference.",
    kind: "ticker",
    href: "/tickers",
  },
  AMD: {
    definition: "Advanced Micro Devices — designs CPUs and GPUs for servers and AI.",
    kind: "ticker",
    href: "/tickers",
  },
  TSM: {
    definition: "TSMC (Taiwan Semiconductor) — the world's largest chip manufacturer; makes chips for Nvidia, AMD, and others.",
    kind: "ticker",
    href: "/tickers",
  },
  AVGO: {
    definition: "Broadcom — makes networking chips and custom AI accelerators for Google and Meta.",
    kind: "ticker",
    href: "/tickers",
  },
  SMCI: {
    definition: "Super Micro Computer — assembles the physical servers that house AI chips.",
    kind: "ticker",
    href: "/tickers",
  },
  CEG: {
    definition: "Constellation Energy — provides nuclear power to data centers run by Microsoft and Amazon.",
    kind: "ticker",
    href: "/tickers",
  },
  VST: {
    definition: "Vistra Corp — a large US electricity and power generation company.",
    kind: "ticker",
    href: "/tickers",
  },
  MSFT: {
    definition: "Microsoft — runs Azure cloud and partners with OpenAI; a major buyer of AI chips.",
    kind: "ticker",
    href: "/tickers",
  },
  GOOGL: {
    definition: "Alphabet (Google) — runs GCP cloud and builds Gemini AI models.",
    kind: "ticker",
    href: "/tickers",
  },
  META: {
    definition: "Meta (Facebook) — builds Llama AI models and runs massive ad infrastructure.",
    kind: "ticker",
    href: "/tickers",
  },
  AMZN: {
    definition: "Amazon — runs AWS cloud and designs its own AI chips (Trainium).",
    kind: "ticker",
    href: "/tickers",
  },

  // ── Tickers — Space & Rockets ──────────────────────────────────────────────
  RKLB: {
    definition: "Rocket Lab — launches small satellites with its Electron rocket; developing the larger Neutron rocket.",
    kind: "ticker",
    href: "/tickers",
  },
  BA: {
    definition: "Boeing — builds launch vehicles (SLS, Starliner) and defense systems.",
    kind: "ticker",
    href: "/tickers",
  },
  LMT: {
    definition: "Lockheed Martin — defense and space systems (GPS satellites, Orion spacecraft).",
    kind: "ticker",
    href: "/tickers",
  },
  NOC: {
    definition: "Northrop Grumman — makes solid rocket boosters and space systems.",
    kind: "ticker",
    href: "/tickers",
  },
  SPCE: {
    definition: "Virgin Galactic — offers suborbital space tourism flights.",
    kind: "ticker",
    href: "/tickers",
  },
  ASTS: {
    definition: "AST SpaceMobile — building a satellite network to provide cellular broadband from space.",
    kind: "ticker",
    href: "/tickers",
  },
  GSAT: {
    definition: "Globalstar — a satellite communications company that holds valuable radio spectrum.",
    kind: "ticker",
    href: "/tickers",
  },

  // ── Tickers — Optical Communications ───────────────────────────────────────
  LITE: {
    definition: "Lumentum — makes lasers and optical transceivers used in fiber-optic networks.",
    kind: "ticker",
    href: "/tickers",
  },
  COHR: {
    definition: "Coherent Corp — makes optical components (lasers, transceivers) for data center networks.",
    kind: "ticker",
    href: "/tickers",
  },
  CIEN: {
    definition: "Ciena — builds optical networking platforms that carry data over fiber.",
    kind: "ticker",
    href: "/tickers",
  },
  ANET: {
    definition: "Arista Networks — makes high-speed network switches for data centers (used by Microsoft, Meta, Google).",
    kind: "ticker",
    href: "/tickers",
  },
  KEYS: {
    definition: "Keysight — makes test and measurement equipment for optical and electronic systems.",
    kind: "ticker",
    href: "/tickers",
  },
  VIAV: {
    definition: "Viavi Solutions — makes network testing and monitoring tools for fiber-optic networks.",
    kind: "ticker",
    href: "/tickers",
  },

  // ── Finance concepts ───────────────────────────────────────────────────────
  ticker: {
    definition: "A short abbreviation for a stock. Example: NVDA stands for Nvidia.",
    kind: "concept",
  },
  signal: {
    definition: "A directional call on a stock — bullish (up), bearish (down), or neutral — backed by evidence.",
    kind: "concept",
  },
  BULLISH: {
    definition: "Expecting the stock price to go up.",
    kind: "concept",
  },
  BEARISH: {
    definition: "Expecting the stock price to go down.",
    kind: "concept",
  },
  NEUTRAL: {
    definition: "No clear directional view — the evidence doesn't lean strongly up or down.",
    kind: "concept",
  },
  conviction: {
    definition: "How strongly the analyst believes in the call, on a 1–5 scale (5 = highest confidence).",
    kind: "concept",
  },
  "evidence score": {
    definition: "A 0–100% score showing how well the analyst's claims are backed by real, verified data.",
    kind: "concept",
  },
  validation: {
    definition: "Whether the AI's numerical claims (prices, percentages) were checked against real data sources.",
    kind: "concept",
  },
  "supply chain impact": {
    definition: "How a change in one company (e.g. a chip shortage at TSMC) ripples through to others (e.g. higher costs for Nvidia).",
    kind: "concept",
  },
  catalyst: {
    definition: "A specific event or reason that could move the stock price (e.g. an earnings beat, a new product launch).",
    kind: "concept",
  },
  risk: {
    definition: "A specific factor that could invalidate the thesis (e.g. regulatory action, competition).",
    kind: "concept",
  },
  "second-order reasoning": {
    definition: "Tracing cause-and-effect through the supply chain. Example: AI boom → more data centers → more energy demand → benefits power companies.",
    kind: "concept",
  },
  sector: {
    definition: "A group of related companies. Example: 'AI & Semiconductors' includes chip designers, manufacturers, and cloud providers.",
    kind: "concept",
  },

  // ── Product terms ──────────────────────────────────────────────────────────
  "Decision Desk": {
    definition: "The page where you pick a stock and run a multi-analyst debate to get an evidence-gated recommendation.",
    kind: "product",
    href: "/tickers",
  },
  "Supply Chain Map": {
    definition: "A visual map showing how companies in a sector connect — who supplies whom, and how revenue flows.",
    kind: "product",
    href: "/supply-chain",
  },
  "Track Record": {
    definition: "Historical accuracy of past predictions. Each call is checked against the real stock price one week later.",
    kind: "product",
    href: "/accuracy",
  },
  agent: {
    definition: "An AI analyst that looks at a stock through a specific lens — value, momentum, supply chain, or risk.",
    kind: "product",
    href: "/agents",
  },
  analyst: {
    definition: "An AI analyst that looks at a stock through a specific lens — value, momentum, supply chain, or risk.",
    kind: "product",
    href: "/agents",
  },
  "Chief Verdict": {
    definition: "A final recommendation (BUY/SELL/HOLD) synthesized from all analysts' views, with dissenting opinions noted.",
    kind: "product",
  },
  "pipeline run": {
    definition: "A single analysis pass on one stock — fetching news, prices, and filings, then having analysts debate.",
    kind: "product",
  },
  "signal card": {
    definition: "A structured summary of one analyst's view: direction, conviction, catalyst, risk, and evidence quality.",
    kind: "product",
  },
  "evidence chat": {
    definition: "A chat panel on each signal card where you can ask follow-up questions and get answers grounded in the evidence.",
    kind: "product",
  },
};

/**
 * Look up a term definition by key.
 * Returns null if the term isn't in the dictionary.
 */
export function lookupTerm(key: string): TermDefinition | null {
  return TERMS[key] ?? null;
}
