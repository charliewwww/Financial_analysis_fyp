/**
 * Inline citation helpers.
 *
 * Analyst prose carries `[SOURCE: ...]` markers. These utilities turn those
 * markers into clickable links that resolve to the real article URL when we can
 * match it in the card/report source pack, and otherwise fall back to the
 * on-page source-pack anchor so every citation is at least navigable.
 */

interface CitationEntry {
  title?: unknown;
  url?: unknown;
  link?: unknown;
  source?: unknown;
  domain?: unknown;
}

function asText(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

export function buildCitationResolver(
  entries: CitationEntry[],
  anchor = "#source-pack",
): (cite: string) => string {
  const index: Array<{ needle: string; url: string }> = [];
  const add = (value: unknown, url: string) => {
    const text = asText(value).toLowerCase();
    if (text && url) index.push({ needle: text, url });
  };
  for (const entry of entries ?? []) {
    const url = asText(entry.url) || asText(entry.link);
    if (!url) continue;
    add(entry.title, url);
    add(entry.source, url);
    add(entry.domain, url);
  }
  return (cite: string) => {
    const needle = cite.trim().toLowerCase();
    if (needle) {
      const hit = index.find((e) => needle.includes(e.needle) || e.needle.includes(needle));
      if (hit) return hit.url;
    }
    return anchor;
  };
}

/** Replace inline `[SOURCE: x]` markers with clickable markdown links. */
export function linkifyCitations(markdown: string, resolve: (cite: string) => string): string {
  if (!markdown) return markdown;
  return markdown.replace(/\[SOURCE:\s*([^\]]+)\]/gi, (_match, cite: string) => {
    const label = cite.trim().replace(/\s+/g, " ");
    return `[↗ ${label}](${resolve(cite)})`;
  });
}
