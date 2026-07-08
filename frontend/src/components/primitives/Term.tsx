"use client";

import * as React from "react";
import Link from "next/link";
import { ArrowUpRight } from "lucide-react";
import { cn } from "@/lib/utils";
import { lookupTerm, type TermDefinition } from "@/lib/terms";

export interface TermProps {
  /** The term key to look up in the terms dictionary (e.g. "VST", "signal"). */
  name: string;
  /** Override the display text (defaults to the term key itself). */
  children?: React.ReactNode;
  className?: string;
  /** Force tooltip-only mode (no link), even if the term has an href.
   *  Use this inside <Link> containers to avoid nested <a> tags. */
  noLink?: boolean;
}

/**
 * Term — an inline, hover-to-explain annotation for jargon and tickers.
 *
 * Unlike InfoHint (which adds a separate info icon), Term makes the word
 * itself interactive: a dotted underline signals "hover me," and a tooltip
 * with a plain-language definition appears on hover or keyboard focus.
 *
 * For ticker terms (kind: "ticker"), the tooltip also includes a link to
 * analyze that stock. For product terms with an href, the tooltip links to
 * the relevant page.
 *
 * Accessibility: the trigger is a real <button> (or <a> if it has an href),
 * so it works with keyboard, touch, and screen readers. The tooltip is
 * role="tooltip" and appears on focus as well as hover.
 */
export function Term({ name, children, className, noLink }: TermProps) {
  const term: TermDefinition | null = lookupTerm(name);
  const displayText = children ?? name;
  const kind = term?.kind;

  // If the term isn't in the dictionary, just render plain text — no annotation.
  if (!term) {
    return <span className={className}>{displayText}</span>;
  }

  const isTicker = kind === "ticker";
  const hasLink = Boolean(term.href) && !noLink;

  const triggerClass = cn(
    "al-term",
    isTicker && "al-term-ticker",
    className
  );

  const tooltip = (
    <span
      role="tooltip"
      className="pointer-events-none absolute bottom-full left-1/2 z-50 mb-2 w-64 -translate-x-1/2 rounded-lg border p-3 text-xs leading-5 opacity-0 shadow-lg transition-opacity duration-150 group-hover:opacity-100 group-focus-within:opacity-100"
      style={{
        background: "var(--al-surface-elevated, var(--popover, white))",
        borderColor: "var(--al-outline)",
        color: "var(--al-on-surface-muted)",
      }}
    >
      {term.definition}
      {hasLink && (
        <span className="mt-1.5 flex items-center gap-1 font-semibold" style={{ color: "var(--al-gold)" }}>
          <ArrowUpRight className="size-3" aria-hidden />
          Explore
        </span>
      )}
    </span>
  );

  // If the term has a link, wrap in an <a> so click navigates.
  if (hasLink && term.href) {
    return (
      <Link
        href={term.href}
        className={cn(triggerClass, "group relative inline-flex align-middle cursor-pointer")}
        aria-label={`${name}: ${term.definition}`}
      >
        {displayText}
        {tooltip}
      </Link>
    );
  }

  // No link — use a <button> so it's keyboard-accessible but doesn't navigate.
  return (
    <span className="group relative inline-flex align-middle">
      <button
        type="button"
        className={triggerClass}
        aria-label={`${name}: ${term.definition}`}
      >
        {displayText}
      </button>
      {tooltip}
    </span>
  );
}
