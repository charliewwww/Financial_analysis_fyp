/**
 * Split a raw Markdown analysis into typed sections.
 *
 * The legacy Streamlit UI rendered each major heading in its own card; this
 * port matches that contract so the Next.js report page can do the same.
 *
 * Mirrors the Python original at ui/components.py `split_analysis_sections`.
 */

export type AnalysisSections = {
  thesis?: string;
  evidence?: string;
  chainOfThought?: string;
  riskAssessment?: string;
  predictions?: string;
  /** Everything before the first matched heading (or the whole text if no
   *  headings matched). Useful as a fallback when the LLM didn't follow the
   *  expected schema. */
  remainder: string;
};

export interface NamedSection {
  heading: string;
  content: string;
}

export interface ExtractedSignal {
  ticker: string;
  direction: "BULLISH" | "BEARISH" | "NEUTRAL";
  move: string;
  reasoning: string;
  risk: string;
}

const HEADINGS: Array<[keyof Omit<AnalysisSections, "remainder">, RegExp]> = [
  ["thesis", /^##\s*Thesis\s*$/im],
  ["evidence", /^##\s*Evidence\s*$/im],
  ["chainOfThought", /^##\s*Chain[\s-]+of[\s-]+Thought\s*$/im],
  ["riskAssessment", /^##\s*Risk\s+Assessment\s*$/im],
  ["predictions", /^##\s*(?:Price\s+)?Predictions?\s*$/im],
];

interface Hit {
  key: keyof Omit<AnalysisSections, "remainder">;
  start: number;
  headingEnd: number;
}

export function splitSections(md: string): AnalysisSections {
  if (!md) return { remainder: "" };

  // 1. Find every heading start
  const hits: Hit[] = [];
  for (const [key, re] of HEADINGS) {
    const m = md.match(re);
    if (m && m.index != null) {
      hits.push({ key, start: m.index, headingEnd: m.index + m[0].length });
    }
  }
  hits.sort((a, b) => a.start - b.start);

  if (hits.length === 0) return { remainder: md.trim() };

  // 2. Slice each section: from heading end → next heading start (or EOF)
  const out: AnalysisSections = { remainder: md.slice(0, hits[0].start).trim() };
  for (let i = 0; i < hits.length; i++) {
    const h = hits[i];
    const next = hits[i + 1];
    const body = md.slice(h.headingEnd, next ? next.start : md.length).trim();
    out[h.key] = body;
  }
  return out;
}

export function splitNamedSections(md: string): NamedSection[] {
  if (!md) return [];

  const parts = md.split(/\n(?=##\s+)/g);
  const sections: NamedSection[] = [];

  for (const part of parts) {
    const match = part.match(/^##\s*(.+?)\s*\n([\s\S]*)$/);
    if (!match) {
      const trimmed = part.trim();
      if (trimmed) sections.push({ heading: "Overview", content: trimmed });
      continue;
    }

    const heading = match[1].trim();
    const normalized = heading.replace(/\s*\(.*?\)\s*$/, "").toUpperCase();
    if (["THESIS", "PRICE PREDICTIONS", "CONFIDENCE SCORE"].includes(normalized)) {
      continue;
    }
    sections.push({ heading, content: match[2].trim() });
  }

  return sections;
}

export function extractThesis(md: string): string {
  if (!md) return "";
  const match = md.match(/##\s*THESIS\s*\n+([\s\S]+?)(?:\n\n|\n##|$)/i);
  if (!match) return "";
  return match[1].trim().split("\n")[0].replace(/^[-*•]\s*/, "").trim();
}

export function extractSignals(md: string): ExtractedSignal[] {
  if (!md) return [];
  const block = md.match(/##\s*PRICE PREDICTIONS[^\n]*\n([\s\S]*?)(?=\n##\s|$)/i)?.[1];
  if (!block) return [];

  const signals: ExtractedSignal[] = [];
  const tickerPattern = /\*{0,2}([A-Z0-9.]+)\*{0,2}\s*:\s*(BULLISH|BEARISH|NEUTRAL)\s*(?:\|\s*Expected\s+move\s*:\s*([^\n]*?))?(?:\n|$)/gi;
  let match: RegExpExecArray | null;
  while ((match = tickerPattern.exec(block))) {
    const remaining = block.slice(match.index + match[0].length, match.index + match[0].length + 700);
    let reasoning = "";
    let risk = "";
    for (const line of remaining.split("\n")) {
      const text = line.trim().replace(/^[-*•]\s*/, "");
      if (/^[A-Z0-9.]+\s*:/.test(text)) break;
      if (text.toLowerCase().startsWith("reasoning:")) reasoning = text.slice("reasoning:".length).trim();
      if (text.toLowerCase().startsWith("key risk:")) risk = text.slice("key risk:".length).trim();
    }
    signals.push({
      ticker: match[1].toUpperCase(),
      direction: match[2].toUpperCase() as ExtractedSignal["direction"],
      move: (match[3] ?? "").trim(),
      reasoning,
      risk,
    });
  }

  return signals;
}
