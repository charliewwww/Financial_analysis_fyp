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
