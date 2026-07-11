"use client";

import Link from "next/link";
import type { FormEvent } from "react";
import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  AlertCircle,
  ArrowRight,
  BarChart3,
  CheckCircle2,
  Clock,
  Cpu,
  Database,
  ExternalLink,
  Gavel,
  Lock,
  Minus,
  Moon,
  Newspaper,
  Search,
  ShieldCheck,
  Square,
  Star,
  TrendingDown,
  TrendingUp,
  Unlock,
  Users,
} from "lucide-react";

import {
  fetchAgents,
  fetchMarkets,
  fetchMarketSectorCatalog,
  fetchModelCatalog,
  fetchRun,
  fetchRuns,
  fetchSignals,
  fetchChiefVerdict,
  fetchVectorDbStats,
  fetchWatchlist,
  addToWatchlist,
  removeFromWatchlist,
  triggerBoardRun,
  triggerSectorSynthesis,
  type MarketSectorCatalogItem,
} from "@/lib/api";
import { useOvernight, OVERNIGHT_DEFAULT_CYCLE_DELAY_MS } from "@/components/overnight/OvernightContext";
import { sortAgents } from "@/lib/agent-catalog";
import { useMarket, marketForTicker } from "@/lib/market-context";
import { SectorPulse } from "@/components/SectorPulse";
import {
  PIPELINE_STAGES,
  aggregatePipelineStageStates,
  classifyPipelineError,
  currentStageLabel,
  estimateRemainingSeconds,
  formatDuration,
  getPipelineStage,
  runProgressPct,
  runTimingLabel,
  type PipelineStageId,
} from "@/lib/pipeline-progress";
import { PipelineTopology, type TopologyNodeState } from "@/components/PipelineTopology";
import {
  buildTickerTrustSummary,
  consensusLabel,
  evaluateSignalCard,
  isMeaningfulText,
  normalizeConfidenceToPct,
  sourceIdentity,
  type CardTrustEvaluation,
  type ConsensusSignal,
  type EvidenceQuality,
  type TrustState,
} from "@/lib/trust";
import type { AgentSummary, ChiefVerdict, PipelineRun, RunFanoutResponse, RunStatus, RunSummary, Signal, SignalCard, SignalSource, SupplyChainImpact } from "@/types/api";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { MetricChip, Pill, type PillVariant } from "@/components/primitives";
import { cn } from "@/lib/utils";

const QUICK_TICKERS_FALLBACK: Record<"us" | "hk", string[]> = {
  us: ["NVDA", "AAPL", "MSFT", "AMZN", "GOOGL", "META", "TSLA", "AMD"],
  hk: ["0700.HK", "9988.HK", "3690.HK", "9618.HK", "1810.HK", "1398.HK"],
};
const DEFAULT_TICKER_BY_MARKET: Record<"us" | "hk", string> = {
  us: "NVDA",
  hk: "0700.HK",
};
const DEFAULT_SECTOR_ID = "us_technology";
const DISABLED_AGENTS_KEY = "marketpulse-disabled-agents";

const SIGNAL_VARIANT: Record<Signal, PillVariant> = {
  BULLISH: "green",
  BEARISH: "red",
  NEUTRAL: "gray",
};

const POSTURE_VARIANT: Record<ConsensusSignal, PillVariant> = {
  BULLISH: "green",
  BEARISH: "red",
  NEUTRAL: "gray",
  MIXED: "amber",
  NONE: "gray",
};

const TRUST_VARIANT: Record<TrustState, PillVariant> = {
  actionable: "green",
  watchlist: "amber",
  insufficient_evidence: "red",
  stale: "amber",
};

const EVIDENCE_VARIANT: Record<EvidenceQuality, PillVariant> = {
  strong: "green",
  medium: "amber",
  weak: "red",
};

const SIGNAL_ICON = {
  BULLISH: TrendingUp,
  BEARISH: TrendingDown,
  NEUTRAL: Minus,
};

type DecisionMode = "support" | "recommendation";

function normalizeTicker(value: string): string {
  return value.trim().toUpperCase().replace(/\s+/g, "");
}

function pickFocusTicker(sector: MarketSectorCatalogItem | undefined): string {
  if (!sector?.constituents?.length) return "NVDA";
  return normalizeTicker(sector.constituents[0]);
}

function latestCardsByAgent(cards: SignalCard[], agents: AgentSummary[]): Map<number, SignalCard> {
  const byAgent = new Map<number, SignalCard>();
  const knownAgents = new Set(agents.map((agent) => agent.id));

  for (const card of cards) {
    const agentId = card.agent_id;
    if (agentId == null || !knownAgents.has(agentId)) continue;
    if (byAgent.has(agentId)) continue;
    byAgent.set(agentId, card);
  }

  return byAgent;
}

function latestRunsByAgent(runs: RunSummary[], agents: AgentSummary[]): Map<number, RunSummary> {
  const byAgent = new Map<number, RunSummary>();
  const knownAgents = new Set(agents.map((agent) => agent.id));

  for (const run of runs) {
    const agentId = run.agent_id;
    if (agentId == null || !knownAgents.has(agentId) || byAgent.has(agentId)) continue;
    byAgent.set(agentId, run);
  }

  return byAgent;
}

function isRunNewerThanCard(run: RunSummary | undefined, card: SignalCard): boolean {
  if (!run) return false;
  const runTime = new Date(run.finished_at ?? run.created_at).getTime();
  const cardTime = new Date(card.created_at).getTime();
  if (Number.isNaN(runTime) || Number.isNaN(cardTime)) return false;
  return runTime > cardTime && run.run_id !== card.run_id;
}

function SignalGlyph({ signal, className }: { signal: Signal; className?: string }) {
  const Icon = SIGNAL_ICON[signal];
  return <Icon className={className} aria-hidden />;
}

function PostureGlyph({ signal, className }: { signal: ConsensusSignal; className?: string }) {
  if (signal === "MIXED" || signal === "NONE") {
    return <Activity className={className} aria-hidden />;
  }
  return <SignalGlyph signal={signal} className={className} />;
}

function formatAge(hours: number | null): string {
  if (hours == null) return "-";
  if (hours < 1) return "<1h";
  if (hours < 48) return `${Math.round(hours)}h`;
  return `${Math.round(hours / 24)}d`;
}

function formatDate(iso: string | null | undefined): string {
  if (!iso) return "-";
  return new Date(iso).toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function firstMeaningful(
  cards: SignalCard[],
  pick: (card: SignalCard) => string | null | undefined
): string | null {
  return cards.map(pick).find(isMeaningfulText) ?? null;
}

function sourceDomains(cards: SignalCard[]): string[] {
  const domains = new Set<string>();
  for (const card of cards) {
    for (const source of card.sources ?? []) {
      const label = sourceIdentity(source);
      if (label) domains.add(label);
    }
  }
  return Array.from(domains).slice(0, 4);
}

// ── Market & news snapshot helpers ────────────────────────────────
// These surface the price / technical / news that already ride along on
// each signal card so the user sees a broad picture on the Decision Desk
// without drilling into a signal sub-page.

function asText(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

function asNumber(value: unknown): number | null {
  if (value == null || value === "") return null;
  const n = typeof value === "number" ? value : Number(value);
  return Number.isFinite(n) ? n : null;
}

function fmtMoney(value: unknown): string {
  const n = asNumber(value);
  return n == null ? "-" : `$${n.toFixed(2)}`;
}

function fmtCompact(value: unknown): string {
  const n = asNumber(value);
  if (n == null) return "-";
  return new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 1 }).format(n);
}

/** Signed percent with a colour cue, so direction isn't conveyed by sign alone. */
function ChangePct({ value }: { value: unknown }) {
  const n = asNumber(value);
  if (n == null) return <span>-</span>;
  const tone = n > 0 ? "var(--al-bullish)" : n < 0 ? "var(--al-bearish)" : "var(--al-on-surface-muted)";
  const sign = n > 0 ? "+" : "";
  return (
    <span style={{ color: tone }} className="inline-flex items-center gap-1">
      {n > 0 ? <TrendingUp className="size-3" aria-hidden /> : n < 0 ? <TrendingDown className="size-3" aria-hidden /> : null}
      {sign}{n.toFixed(2)}%
    </span>
  );
}

function snapshotRowForTicker(
  cards: SignalCard[],
  pick: (card: SignalCard) => Array<Record<string, unknown>> | undefined,
  ticker: string
): Record<string, unknown> | null {
  const target = normalizeTicker(ticker);
  for (const card of cards) {
    const rows = pick(card) ?? [];
    const match = rows.find(
      (row) => normalizeTicker(asText(row.ticker) || asText(row.symbol)) === target
    );
    if (match) return match;
  }
  for (const card of cards) {
    const rows = pick(card) ?? [];
    if (rows.length) return rows[0];
  }
  return null;
}

function aggregateNews(cards: SignalCard[]): SignalSource[] {
  const seen = new Set<string>();
  const out: SignalSource[] = [];
  for (const card of cards) {
    for (const source of card.sources ?? []) {
      const key = (source.url || source.title || "").toLowerCase();
      if (!key || seen.has(key)) continue;
      seen.add(key);
      out.push(source);
    }
  }
  return out.slice(0, 6);
}

function MarketNewsPanel({ ticker, cards }: { ticker: string; cards: SignalCard[] }) {
  const price = snapshotRowForTicker(cards, (card) => card.price_snapshot, ticker);
  const technical = snapshotRowForTicker(cards, (card) => card.technical_snapshot, ticker);
  const news = aggregateNews(cards);

  const hasPrice = Boolean(price);
  const hasTechnical = Boolean(technical);
  const hasNews = news.length > 0;

  if (!hasPrice && !hasTechnical && !hasNews) return null;

  return (
    <section className="al-glass p-5 space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="al-eyebrow">Market &amp; news snapshot</div>
          <h2 className="mt-1 text-xl">Everything on {ticker}, at a glance</h2>
        </div>
        <Pill variant="gray">from latest analysis</Pill>
      </div>

      {hasPrice ? (
        <div className="space-y-2">
          <div className="al-eyebrow flex items-center gap-1.5">
            <TrendingUp className="size-3.5" aria-hidden /> Price action
          </div>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <MetricChip label="Price" value={fmtMoney(price?.price)} className="min-w-full" />
            <MetricChip label="1-day" value={<ChangePct value={price?.change_1d_pct} />} className="min-w-full" />
            <MetricChip label="1-week" value={<ChangePct value={price?.change_1w_pct} />} className="min-w-full" />
            <MetricChip label="Volume" value={fmtCompact(price?.volume)} sub={asNumber(price?.market_cap) != null ? `${fmtCompact(price?.market_cap)} mkt cap` : undefined} className="min-w-full" />
          </div>
        </div>
      ) : null}

      {hasTechnical ? (
        <div className="space-y-2">
          <div className="al-eyebrow flex items-center gap-1.5">
            <BarChart3 className="size-3.5" aria-hidden /> Technical setup
          </div>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <MetricChip label="Trend" value={asText(technical?.trend) || "-"} className="min-w-full" />
            <MetricChip label="RSI" value={asNumber(technical?.rsi) != null ? asNumber(technical?.rsi)!.toFixed(0) : "-"} sub="14-day" className="min-w-full" />
            <MetricChip label="MACD" value={asText(technical?.macd_signal) || "-"} className="min-w-full" />
            <MetricChip label="50-day SMA" value={fmtMoney(technical?.sma_50)} className="min-w-full" />
          </div>
        </div>
      ) : null}

      {hasNews ? (
        <div className="space-y-2">
          <div className="al-eyebrow flex items-center gap-1.5">
            <Newspaper className="size-3.5" aria-hidden /> Latest news
          </div>
          <ul className="divide-y" style={{ borderColor: "var(--al-outline)" }}>
            {news.map((source, index) => {
              const title = asText(source.title) || asText(source.domain) || `Source ${index + 1}`;
              const domain = asText(source.domain);
              const href = asText(source.url);
              return (
                <li key={`${title}-${index}`} className="py-2">
                  {href ? (
                    <a
                      href={href}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="group flex items-start justify-between gap-3 text-sm leading-6 hover:underline"
                    >
                      <span className="min-w-0">
                        <span className="line-clamp-2">{title}</span>
                        {domain ? (
                          <span className="mt-0.5 block text-xs" style={{ color: "var(--al-on-surface-muted)" }}>{domain}</span>
                        ) : null}
                      </span>
                      <ExternalLink className="mt-0.5 size-3.5 shrink-0" aria-hidden style={{ color: "var(--al-gold)" }} />
                    </a>
                  ) : (
                    <span className="block text-sm leading-6">
                      {title}
                      {domain ? <span className="mt-0.5 block text-xs" style={{ color: "var(--al-on-surface-muted)" }}>{domain}</span> : null}
                    </span>
                  )}
                </li>
              );
            })}
          </ul>
        </div>
      ) : null}
    </section>
  );
}

function formatReasonList(items: string[]): string {
  if (items.length <= 1) return items[0] ?? "";
  if (items.length === 2) return `${items[0]} and ${items[1]}`;
  return `${items.slice(0, -1).join(", ")}, and ${items[items.length - 1]}`;
}

function evidenceScoreLimiters(evaluation: CardTrustEvaluation): string[] {
  const reasons: string[] = [];
  if (!evaluation.hasCatalyst) reasons.push("missing catalyst");
  if (!evaluation.hasRisk) reasons.push("missing risk");
  if (evaluation.sourceCount === 0) reasons.push("no article evidence");
  else if (evaluation.sourceDomainCount <= 1 && evaluation.sourceCount > 1) reasons.push("one publisher/feed");
  if (evaluation.validation.failed) reasons.push("failed validation");
  else if (evaluation.validation.total === 0) reasons.push("missing claim checks");
  if (evaluation.stale) reasons.push("stale timestamp");
  return reasons.slice(0, 3);
}

function latestRunBatch(runs: RunSummary[], totalAgents: number): RunSummary[] {
  if (!runs.length) return [];
  const newest = new Date(runs[0].created_at).getTime();
  if (Number.isNaN(newest)) return runs.slice(0, Math.max(1, totalAgents));
  const windowMs = 10 * 60 * 1000;
  return runs
    .filter((run) => {
      const ts = new Date(run.created_at).getTime();
      return !Number.isNaN(ts) && newest - ts <= windowMs;
    })
    .slice(0, Math.max(1, totalAgents));
}

function recommendationLabel(signal: ConsensusSignal): string {
  if (signal === "BULLISH") return "Constructive bias";
  if (signal === "BEARISH") return "Defensive bias";
  if (signal === "NEUTRAL") return "Stand aside";
  return "No directional call";
}

function decisionStatusLabel(trust: ReturnType<typeof buildTickerTrustSummary>): string {
  if (trust.recommendationAllowed) return recommendationLabel(trust.posture);
  if (trust.posture === "MIXED") return "Research mode: analyst split";
  if (trust.posture === "NONE") return "Awaiting analyst board";
  if (trust.state === "stale") return "Refresh before relying";
  if (trust.state === "insufficient_evidence") return "Evidence not strong enough";
  return "Watchlist only";
}

function unlockActions(trust: ReturnType<typeof buildTickerTrustSummary>): string[] {
  const actions = trust.checks
    .filter((check) => !check.passed)
    .map((check) => {
      if (check.label === "Analyst agreement") return "Resolve the analyst split or wait for the required lane agreement threshold.";
      if (check.label === "Coverage") return "Run the full board until every specialist lane publishes a current card.";
      if (check.label === "Evidence completeness") return "Require each card to show a thesis, catalyst, risk, and source coverage.";
      if (check.label === "Freshness") return "Rerun the board so the decision is based on fresh market data.";
      if (check.label === "Validation") return "Attach numerical claim checks before treating the signal as decision-grade.";
      return check.detail;
    });

  return actions.length ? actions.slice(0, 3) : ["The evidence gate is open; review sources before acting."];
}

function EvidencePreview({ label, value, fallback }: { label: string; value: string | null; fallback: string }) {
  return (
    <div className="rounded-xl border p-4" style={{ borderColor: "var(--al-outline)" }}>
      <div className="al-eyebrow">{label}</div>
      <p className="mt-2 line-clamp-4 text-sm leading-6" style={{ color: value ? "var(--al-on-surface)" : "var(--al-on-surface-muted)" }}>
        {value ?? fallback}
      </p>
    </div>
  );
}

function DecisionDeskLoading() {
  return (
    <section className="al-glass p-5 md:p-6">
      <div className="grid gap-5 lg:grid-cols-[1.1fr_0.9fr]">
        <div className="space-y-4">
          <Skeleton className="h-5 w-32" />
          <Skeleton className="h-10 w-48" />
          <Skeleton className="h-20 w-full" />
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {Array.from({ length: 4 }).map((_, index) => <Skeleton key={index} className="h-20 rounded-xl" />)}
          </div>
        </div>
        <Skeleton className="h-64 rounded-xl" />
      </div>
    </section>
  );
}

function TrustChecklist({
  checks,
}: {
  checks: Array<{ label: string; passed: boolean; detail: string }>;
}) {
  return (
    <section className="al-glass p-5">
      <div className="flex items-center justify-between gap-3">
        <div>
          <div className="al-eyebrow">Trust checklist</div>
          <h2 className="mt-1 text-lg">Decision quality</h2>
        </div>
        <ShieldCheck className="size-5" aria-hidden style={{ color: "var(--al-gold)" }} />
      </div>
      <div className="mt-4 space-y-3">
        {checks.map((check) => {
          const Icon = check.passed ? CheckCircle2 : AlertCircle;
          return (
            <div
              key={check.label}
              className="grid gap-2 rounded-xl border p-3 sm:grid-cols-[24px_150px_1fr] sm:items-start"
              style={{ borderColor: "var(--al-outline)" }}
            >
              <Icon className={cn("mt-0.5 size-4", check.passed ? "text-emerald-500" : "text-amber-500")} aria-hidden />
              <div className="text-sm font-semibold">{check.label}</div>
              <div className="text-sm leading-6" style={{ color: "var(--al-on-surface-muted)" }}>
                {check.detail}
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}

function LatestRunNotice({
  runs,
  totalAgents,
}: {
  runs: RunSummary[];
  totalAgents: number;
}) {
  const batch = latestRunBatch(runs, totalAgents);
  if (!batch.length) return null;

  const failed = batch.filter((run) => run.error || run.status === "failed");
  if (!failed.length) return null;

  const published = batch.filter((run) => Boolean(run.signal_card_id)).length;
  const primaryIssue = classifyPipelineError(failed[0]?.error);
  const firstRunAt = formatDate(batch[batch.length - 1]?.created_at);

  return (
    <section className="rounded-2xl border border-amber-200 bg-amber-50 p-4 text-amber-950 dark:border-amber-500/25 dark:bg-amber-500/10 dark:text-amber-50">
      <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
        <div>
          <div className="text-xs font-semibold uppercase tracking-wide text-amber-700 dark:text-amber-200">Latest board attempt</div>
          <h2 className="mt-1 text-base font-semibold">
            {published}/{batch.length} analyst cards published, {failed.length} failed
          </h2>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-amber-900 dark:text-amber-50/85">
            The cards below may include older published analysis for lanes that failed in the latest run. The run started around {firstRunAt}.
          </p>
        </div>
        <Pill variant="amber">not fully refreshed</Pill>
      </div>
      {primaryIssue ? (
        <div className="mt-3 rounded-xl border border-amber-300/70 bg-white/60 p-3 text-sm leading-6 dark:border-amber-400/20 dark:bg-black/10">
          <span className="font-semibold">{primaryIssue.title}: </span>{primaryIssue.detail}
        </div>
      ) : null}
    </section>
  );
}

function ModeSwitch({
  mode,
  setMode,
  recommendationAllowed,
}: {
  mode: DecisionMode;
  setMode: (mode: DecisionMode) => void;
  recommendationAllowed: boolean;
}) {
  return (
    <div className="inline-flex rounded-full border border-border p-1">
      <button
        type="button"
        onClick={() => setMode("support")}
        className={cn(
          "rounded-full px-3 py-1 text-xs font-semibold transition-colors",
          mode === "support" ? "bg-muted text-foreground" : "text-muted-foreground hover:text-foreground"
        )}
      >
        Decision support
      </button>
      <button
        type="button"
        onClick={() => recommendationAllowed && setMode("recommendation")}
        disabled={!recommendationAllowed}
        className={cn(
          "rounded-full px-3 py-1 text-xs font-semibold transition-colors",
          mode === "recommendation" ? "bg-muted text-foreground" : "text-muted-foreground hover:text-foreground",
          !recommendationAllowed && "cursor-not-allowed opacity-50"
        )}
      >
        Recommendation
      </button>
    </div>
  );
}

const VERDICT_ACTION_VARIANT: Record<string, PillVariant> = {
  BUY: "green",
  SELL: "red",
  HOLD: "amber",
};

const VERDICT_AGREEMENT_LABEL: Record<string, string> = {
  aligned: "analysts aligned",
  mixed: "mixed views",
  split: "analysts split",
};

function ChiefVerdictPanel({ ticker, totalAgents }: { ticker: string; totalAgents: number }) {
  const verdict = useMutation<ChiefVerdict, Error, void>({
    mutationFn: () => fetchChiefVerdict(ticker),
  });
  const data = verdict.data;
  const actionVariant = data ? VERDICT_ACTION_VARIANT[data.action] ?? "gray" : "gray";

  return (
    <section className="al-glass overflow-hidden p-5 md:p-6" style={{ borderColor: "var(--al-gold)" }}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <span
            className="grid size-10 shrink-0 place-items-center rounded-xl"
            style={{ background: "var(--al-gold-container)", color: "var(--al-gold-on)" }}
          >
            <Gavel className="size-5" aria-hidden />
          </span>
          <div>
            <div className="al-eyebrow">Chief Strategist</div>
            <h2 className="mt-0.5 text-xl">House verdict on {ticker}</h2>
            <p className="mt-1 max-w-2xl text-sm leading-6" style={{ color: "var(--al-on-surface-muted)" }}>
              One decisive call that weighs every analyst lens against the others.
            </p>
          </div>
        </div>
        <Button
          onClick={() => verdict.mutate()}
          disabled={verdict.isPending}
          className="shrink-0"
        >
          {verdict.isPending ? "Deliberating…" : data ? "Re-run verdict" : "Generate verdict"}
        </Button>
      </div>

      {verdict.isError ? (
        <div className="mt-4 rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm leading-6 text-amber-900 dark:border-amber-500/25 dark:bg-amber-500/10 dark:text-amber-100">
          {verdict.error.message || "Could not generate a verdict. Run the board first so the analysts have published cards."}
        </div>
      ) : null}

      {data ? (
        <div className="mt-5 space-y-4">
          <div className="flex flex-wrap items-center gap-2">
            <Pill variant={actionVariant} className="text-sm">{data.action}</Pill>
            <Pill variant="gray">conviction {data.conviction}/5</Pill>
            <Pill variant="gray">{VERDICT_AGREEMENT_LABEL[data.agreement] ?? data.agreement}</Pill>
            <Pill variant="gray">{data.analysts.length}/{totalAgents} analysts</Pill>
          </div>
          <p
            className="flex items-start gap-1.5 text-xs leading-5"
            style={{ color: "var(--al-on-surface-muted)" }}
          >
            <AlertCircle className="mt-0.5 size-3.5 shrink-0" aria-hidden />
            <span>
              Research signal, <span className="font-semibold">not financial advice</span>. This is an
              AI synthesis of public data and can be wrong. Do your own research before trading.
            </span>
          </p>
          {data.deciding_reason ? (
            <div className="rounded-xl border p-4" style={{ borderColor: "var(--al-outline)" }}>
              <div className="al-eyebrow">Deciding reason</div>
              <p className="mt-1 text-sm font-semibold leading-6">{data.deciding_reason}</p>
            </div>
          ) : null}
          {data.summary ? (
            <p className="text-sm leading-6" style={{ color: "var(--al-on-surface)" }}>{data.summary}</p>
          ) : null}
          {data.risk_assessment ? (
            <div className="rounded-xl border p-4" style={{ borderColor: "var(--al-outline)", background: "var(--al-surface-2)" }}>
              <div className="al-eyebrow">Probability-weighted risk</div>
              <p className="mt-1 text-sm leading-6" style={{ color: "var(--al-on-surface)" }}>{data.risk_assessment}</p>
            </div>
          ) : null}
          {data.dissent ? (
            <p className="text-sm leading-6" style={{ color: "var(--al-on-surface-muted)" }}>
              <span className="font-semibold text-foreground">Strongest dissent: </span>
              {data.dissent}
            </p>
          ) : null}
        </div>
      ) : !verdict.isError ? (
        <p className="mt-4 text-sm leading-6" style={{ color: "var(--al-on-surface-muted)" }}>
          Generate a single BUY / SELL / HOLD call with a conviction and the one factor that tipped the decision. Uses the
          latest published card from each analyst, so run the board first.
        </p>
      ) : null}
    </section>
  );
}

function VerdictPanel({
  ticker,
  mode,
  setMode,
  trust,
  liveCards,
  totalAgents,
}: {
  ticker: string;
  mode: DecisionMode;
  setMode: (mode: DecisionMode) => void;
  trust: ReturnType<typeof buildTickerTrustSummary>;
  liveCards: SignalCard[];
  totalAgents: number;
}) {
  const recommendationOpen = trust.recommendationAllowed;
  const summary = firstMeaningful(liveCards, (card) => card.one_line);
  const catalyst = firstMeaningful(liveCards, (card) => card.key_catalyst);
  const risk = firstMeaningful(liveCards, (card) => card.key_risk);
  const actions = unlockActions(trust);
  const decisionStatus = decisionStatusLabel(trust);

  return (
    <section className="al-glass overflow-hidden">
      <div className="grid gap-0 lg:grid-cols-[1.1fr_0.9fr]">
        <div className="space-y-5 p-5 md:p-6">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <div className="al-eyebrow">Decision read</div>
              <h1 className="mt-1 text-3xl md:text-4xl">{ticker}</h1>
              <p className="mt-2 max-w-2xl text-sm leading-6" style={{ color: "var(--al-on-surface-muted)" }}>
                {decisionStatus}. {trust.reasons[0]}
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Pill variant={TRUST_VARIANT[trust.state]}>{trust.stateLabel}</Pill>
              <Pill variant={POSTURE_VARIANT[trust.posture]}>
                <PostureGlyph signal={trust.posture} className="size-3" />
                {consensusLabel(trust.posture)}
              </Pill>
            </div>
          </div>

          <div className="grid gap-3 lg:grid-cols-3">
            <EvidencePreview label="What changed" value={summary} fallback="Run the board to create an investor-readable market read." />
            <EvidencePreview label="Key catalyst" value={catalyst} fallback="No catalyst is strong enough to use as decision evidence yet." />
            <EvidencePreview label="Invalidation risk" value={risk} fallback="No clear invalidation risk is attached yet." />
          </div>

          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <MetricChip label="Analyst agreement" value={`${trust.analystAgreement.agreeing}/${totalAgents}`} sub={trust.analystAgreement.detail} />
            <MetricChip label="Evidence quality" value={trust.evidenceQuality} sub={`${trust.evidenceScore}% trust score`} />
            <MetricChip label="Coverage" value={`${liveCards.length}/${totalAgents}`} sub="analyst lanes" />
            <MetricChip label="Freshness" value={formatAge(trust.latestAgeHours)} sub={trust.latestCard ? formatDate(trust.latestCard.created_at) : "No card yet"} />
          </div>
        </div>

        <div className="border-t p-5 md:p-6 lg:border-l lg:border-t-0" style={{ borderColor: "var(--al-outline)" }}>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <div className="al-eyebrow">Next action</div>
              <h2 className="mt-1 text-lg">{mode === "recommendation" && recommendationOpen ? "Recommendation" : decisionStatus}</h2>
            </div>
            <ModeSwitch mode={mode} setMode={setMode} recommendationAllowed={recommendationOpen} />
          </div>

          <div className="mt-5 rounded-xl border p-4" style={{ borderColor: "var(--al-outline)" }}>
            <div className="flex items-center gap-2 text-sm font-semibold">
              {recommendationOpen ? (
                <Unlock className="size-4 text-emerald-500" aria-hidden />
              ) : (
                <Lock className="size-4 text-amber-500" aria-hidden />
              )}
              {recommendationOpen ? "Recommendation unlocked" : "Recommendation locked"}
            </div>
            <p className="mt-2 text-sm leading-6" style={{ color: "var(--al-on-surface-muted)" }}>
              {recommendationOpen
                ? `Suggested posture: ${recommendationLabel(trust.posture)}. The decision remains evidence-led and should be reviewed when new data lands.`
                : "MarketPulse will keep this in decision-support mode until the board is aligned, fresh, sourced, complete, and claim-checked."}
            </p>
          </div>

          <div className="mt-4 space-y-2">
            <div className="al-eyebrow">Unlock path</div>
            {actions.map((action) => (
              <div key={action} className="flex gap-2 text-sm leading-6" style={{ color: "var(--al-on-surface-muted)" }}>
                <AlertCircle className="mt-1 size-3.5 shrink-0 text-amber-500" aria-hidden />
                <span>{action}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

function DecisionBrief({
  cards,
  mode,
  trust,
}: {
  cards: SignalCard[];
  mode: DecisionMode;
  trust: ReturnType<typeof buildTickerTrustSummary>;
}) {
  const latest = trust.latestCard;
  const catalyst = firstMeaningful(cards, (card) => card.key_catalyst);
  const risk = firstMeaningful(cards, (card) => card.key_risk);
  const summary = firstMeaningful(cards, (card) => card.one_line);
  const domains = sourceDomains(cards);
  const ripple = latest?.supply_chain_impact?.slice(0, 4) ?? [];
  const headline = mode === "recommendation" && trust.recommendationAllowed
    ? recommendationLabel(trust.posture)
    : trust.stateLabel;

  return (
    <section className="al-glass p-5 space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="al-eyebrow">Decision brief</div>
          <h2 className="mt-1 text-xl">{headline}</h2>
        </div>
        <Pill variant={mode === "recommendation" && trust.recommendationAllowed ? "green" : TRUST_VARIANT[trust.state]}>
          {mode === "recommendation" ? "recommendation mode" : "support mode"}
        </Pill>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <div className="rounded-xl border p-4" style={{ borderColor: "var(--al-outline)" }}>
          <div className="al-eyebrow">What changed</div>
          <p className="mt-2 text-sm leading-6">{summary ?? "No investor-readable thesis has been published yet."}</p>
        </div>
        <div className="rounded-xl border p-4" style={{ borderColor: "var(--al-outline)" }}>
          <div className="al-eyebrow">Primary catalyst</div>
          <p className="mt-2 text-sm leading-6">{catalyst ?? "Catalyst is not strong enough to present as evidence."}</p>
        </div>
        <div className="rounded-xl border p-4" style={{ borderColor: "var(--al-outline)" }}>
          <div className="al-eyebrow">Invalidation risk</div>
          <p className="mt-2 text-sm leading-6">{risk ?? "Risk is missing, so the signal should not be treated as actionable."}</p>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <div className="rounded-xl border p-4" style={{ borderColor: "var(--al-outline)" }}>
          <div className="al-eyebrow">Supply-chain ripple</div>
          {ripple.length ? (
            <div className="mt-3 flex flex-wrap gap-2">
              {ripple.map((impact) => (
                <Pill key={`${latest?.id ?? latest?.run_id}-${impact.ticker}-${impact.direction}`} variant="gray">
                  {impact.direction} {impact.ticker}
                </Pill>
              ))}
            </div>
          ) : (
            <p className="mt-2 text-sm leading-6" style={{ color: "var(--al-on-surface-muted)" }}>
              No verified ripple effect attached to the latest card.
            </p>
          )}
        </div>
        <div className="rounded-xl border p-4" style={{ borderColor: "var(--al-outline)" }}>
          <div className="al-eyebrow">Source coverage</div>
          {domains.length ? (
            <div className="mt-3 flex flex-wrap gap-2">
              {domains.map((domain) => <Pill key={domain} variant="gold">{domain}</Pill>)}
            </div>
          ) : (
            <p className="mt-2 text-sm leading-6" style={{ color: "var(--al-on-surface-muted)" }}>
              No source domains attached yet.
            </p>
          )}
        </div>
      </div>
    </section>
  );
}

function SecondOrderTakeaway({ impacts }: { impacts?: SupplyChainImpact[] | null }) {
  const items = (impacts ?? []).filter((i) => i?.ticker && isMeaningfulText(i?.reason)).slice(0, 2);
  if (!items.length) return null;
  return (
    <div className="mt-4 rounded-xl border p-3" style={{ borderColor: "var(--al-outline)" }}>
      <div className="al-eyebrow">Second-order read</div>
      <ul className="mt-2 space-y-1.5">
        {items.map((impact) => (
          <li key={`${impact.ticker}-${impact.direction}`} className="text-xs leading-5">
            <span className="font-semibold">{impact.direction} {impact.ticker}</span>
            <span style={{ color: "var(--al-on-surface-muted)" }}> — {impact.reason}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function AgentLane({
  agent,
  card,
  latestRun,
  ticker,
  loading,
  enabled,
  onToggleEnabled,
}: {
  agent: AgentSummary;
  card?: SignalCard;
  latestRun?: RunSummary;
  ticker: string;
  loading: boolean;
  enabled: boolean;
  onToggleEnabled: () => void;
}) {
  if (loading) return <Skeleton className="h-80 rounded-lg" />;

  const latestRunFailed = Boolean(latestRun?.error) || latestRun?.status === "failed";
  const latestRunPending = latestRun?.status === "pending" || latestRun?.status === "running";

  const toggle = (
    <button
      type="button"
      role="switch"
      aria-checked={enabled}
      aria-label={`${enabled ? "Disable" : "Enable"} ${agent.name} for the next board run`}
      title={enabled ? "Analyst on — click to skip on next run" : "Analyst off — click to include"}
      onClick={onToggleEnabled}
      className={cn(
        "relative inline-flex h-5 w-9 shrink-0 items-center rounded-full transition-colors",
        enabled ? "bg-[var(--al-gold)]" : "bg-muted"
      )}
    >
      <span
        className={cn(
          "inline-block size-4 transform rounded-full bg-white shadow transition-transform",
          enabled ? "translate-x-4" : "translate-x-0.5"
        )}
      />
    </button>
  );

  if (!card) {
    return (
      <article className={cn("al-glass flex min-h-[240px] flex-col p-5", !enabled && "opacity-55")}>
        <div className="flex items-start justify-between gap-3">
          <div>
            <div className="al-section-title text-base">{agent.name}</div>
            <p className="mt-1 text-xs leading-5" style={{ color: "var(--al-on-surface-muted)" }}>
              {agent.description ?? "Specialist MarketPulse analyst."}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Pill variant={latestRunFailed ? "red" : latestRunPending ? "gold" : "gray"}>
              {latestRunFailed ? "latest run failed" : latestRunPending ? "running" : "no card"}
            </Pill>
            {toggle}
          </div>
        </div>
        <div className="mt-5 flex flex-1 flex-col justify-between gap-5">
          <div className="space-y-2">
            <p className="text-sm leading-6" style={{ color: "var(--al-on-surface-muted)" }}>
              {latestRunFailed
                ? `${agent.name} tried to analyze ${ticker}, but the latest run did not publish a signal card.`
                : `${agent.name} has not published a current ${ticker} signal card.`}
            </p>
            {latestRun?.error ? (
              <div className="rounded-xl border border-red-200 bg-red-50 p-3 text-xs leading-5 text-red-800 dark:border-red-500/25 dark:bg-red-500/10 dark:text-red-100">
                {classifyPipelineError(latestRun.error)?.detail ?? latestRun.error}
              </div>
            ) : null}
          </div>
          <Link href="/agents" className="inline-flex items-center gap-1 text-sm font-semibold hover:underline" style={{ color: "var(--al-gold)" }}>
            View agent <ArrowRight className="size-4" aria-hidden />
          </Link>
        </div>
      </article>
    );
  }

  const evaluation = evaluateSignalCard(card);
  const evidenceLabel = evaluation.stale ? "stale" : `${evaluation.evidenceQuality} evidence`;
  const showingPreviousCard = latestRunFailed && isRunNewerThanCard(latestRun, card);
  const limiters = evidenceScoreLimiters(evaluation);

  return (
    <article className={cn("al-glass flex min-h-[260px] flex-col p-5", !enabled && "opacity-55")}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="al-section-title text-base">{agent.name}</div>
          <p className="mt-1 text-xs leading-5" style={{ color: "var(--al-on-surface-muted)" }}>
            {agent.description ?? "Specialist MarketPulse analyst."}
          </p>
        </div>
        <div className="flex flex-col items-end gap-1.5">
          <div className="flex flex-wrap justify-end gap-1.5">
            <Pill variant={SIGNAL_VARIANT[card.signal]}>
              <SignalGlyph signal={card.signal} className="size-3" />
              {card.signal.toLowerCase()}
            </Pill>
            {showingPreviousCard ? <Pill variant="red">older card shown</Pill> : null}
            <Pill variant={evaluation.stale ? "amber" : EVIDENCE_VARIANT[evaluation.evidenceQuality]}>{evidenceLabel}</Pill>
          </div>
          {toggle}
        </div>
      </div>

      {showingPreviousCard ? (
        <div className="mt-4 rounded-xl border border-amber-200 bg-amber-50 p-3 text-xs leading-5 text-amber-900 dark:border-amber-500/25 dark:bg-amber-500/10 dark:text-amber-100">
          Latest run failed, so this lane is showing the previous published card from {formatDate(card.created_at)}.
        </div>
      ) : null}

      <p className="mt-5 line-clamp-4 text-sm leading-6">
        {evaluation.hasSummary ? card.one_line : "This analyst did not produce an investor-readable signal summary."}
      </p>

      <SecondOrderTakeaway impacts={card.supply_chain_impact} />

      <div className="mt-5 flex flex-wrap gap-2">
        <Pill variant="gray">{evaluation.confidencePct == null ? "evidence score -" : `${evaluation.confidencePct}% evidence score`}</Pill>
        <Pill variant={evaluation.validation.failed ? "red" : "gray"}>{evaluation.validation.label}</Pill>
        <Pill variant={evaluation.sourceCount ? "gold" : "amber"}>{evaluation.sourceCount} articles</Pill>
        {evaluation.sourceCount > 0 ? (
          <Pill variant={evaluation.sourceDomainCount > 1 ? "gold" : "amber"}>{evaluation.sourceDomainCount} publishers</Pill>
        ) : null}
      </div>

      {limiters.length ? (
        <div className="mt-4 flex gap-2 rounded-xl border border-amber-200 bg-amber-50 p-3 text-xs leading-5 text-amber-900 dark:border-amber-500/25 dark:bg-amber-500/10 dark:text-amber-100">
          <AlertCircle className="mt-0.5 size-3.5 shrink-0" aria-hidden />
          <span>Evidence score limited by {formatReasonList(limiters)}.</span>
        </div>
      ) : null}

      <div className="mt-auto flex flex-wrap items-center justify-between gap-3 pt-5">
        <div className="flex items-center gap-2 text-xs" style={{ color: "var(--al-on-surface-muted)" }}>
          <Clock className="size-3.5" aria-hidden />
          {formatAge(evaluation.ageHours)} old
        </div>
      </div>
    </article>
  );
}

interface ActiveRunMeta {
  runId: string;
  agentId?: number | null;
  agentName: string;
  ticker: string;
}

function runStatusVariant(status: RunStatus | "syncing"): PillVariant {
  if (status === "completed") return "green";
  if (status === "failed") return "red";
  if (status === "running") return "gold";
  return "gray";
}

function ProgressPanel({
  runProgress,
  runs,
  activeRuns,
  isSyncing,
  justCompleted = false,
}: {
  runProgress: RunProgress;
  runs: PipelineRun[] | undefined;
  activeRuns: ActiveRunMeta[];
  isSyncing: boolean;
  justCompleted?: boolean;
}) {
  if (runProgress.total === 0) return null;
  const byRunId = new Map((runs ?? []).map((run) => [run.run_id, run] as const));
  const visibleRuns = activeRuns.slice(0, 6);
  const failedIssues = activeRuns
    .map((meta) => byRunId.get(meta.runId))
    .filter((run): run is PipelineRun => Boolean(run?.error))
    .map((run) => classifyPipelineError(run.error))
    .filter((issue): issue is NonNullable<typeof issue> => Boolean(issue));
  const primaryIssue = failedIssues[0];
  const issueCount = Math.max(runProgress.failed, failedIssues.length);

  return (
    <section className={cn("al-glass space-y-4 p-4 transition-shadow duration-500", justCompleted && "ring-2 ring-emerald-400/70")}>
      {justCompleted ? (
        <div className="flex items-center gap-2 rounded-xl border border-emerald-300 bg-emerald-50 px-3 py-2 text-sm font-semibold text-emerald-800 dark:border-emerald-500/30 dark:bg-emerald-500/10 dark:text-emerald-100">
          <span aria-hidden>✓</span> Analysis complete — results updated
        </div>
      ) : null}
      <div className="flex items-center justify-between gap-3">
        <div>
          <div className="al-eyebrow">Analysis progress</div>
          <p className="text-sm font-semibold">
            {runProgress.completed + runProgress.failed}/{runProgress.total} analyst runs finished
          </p>
        </div>
        <Pill variant={runProgress.failed > 0 ? "amber" : runProgress.progressPct === 100 ? "green" : "gold"}>
          <Activity className="size-3" aria-hidden />
          {runProgress.progressPct}%
        </Pill>
      </div>

      <div className="grid gap-3 md:grid-cols-4">
        <MetricChip label="Current node" value={runProgress.currentStageLabel} sub={runProgress.currentStageDetail} className="min-w-full" />
        <MetricChip label="ETA" value={runProgress.etaLabel} sub={runProgress.etaDetail} className="min-w-full" />
        <MetricChip label="Reports ready" value={`${runProgress.reportsReady}/${runProgress.total}`} sub="published signal cards" className="min-w-full" />
        <MetricChip label="Sync" value={isSyncing ? "Polling" : "Current"} sub="3s backend status refresh" className="min-w-full" />
      </div>

      <div className="h-2 overflow-hidden rounded-full bg-muted">
        <div className="h-full rounded-full bg-[var(--al-gold)] transition-all duration-500" style={{ width: `${runProgress.progressPct}%` }} />
      </div>

      {primaryIssue ? (
        <div className="flex items-start gap-3 rounded-xl border border-red-200 bg-red-50 p-3 text-sm dark:border-red-500/25 dark:bg-red-500/10">
          <AlertCircle className="mt-0.5 size-4 shrink-0 text-red-600 dark:text-red-300" aria-hidden />
          <div>
            <div className="font-semibold text-red-800 dark:text-red-100">
              {issueCount} analyst {issueCount === 1 ? "run" : "runs"} failed: {primaryIssue.title}
            </div>
            <p className="mt-1 text-xs leading-5 text-red-700 dark:text-red-100/80">{primaryIssue.detail}</p>
          </div>
        </div>
      ) : null}

      <div className="space-y-2">
        <div className="flex flex-wrap items-end justify-between gap-2">
          <div>
            <div className="al-eyebrow">Pipeline blueprint</div>
            <p className="text-sm font-semibold">Evidence intake to validated signal card</p>
          </div>
          <span className="text-xs" style={{ color: "var(--al-on-surface-muted)" }}>
            {runProgress.running} running, {runProgress.pending} pending, {runProgress.completed} completed, {runProgress.failed} failed
          </span>
        </div>
        <PipelineTopology states={runProgress.stageStates} compact />
      </div>

      <div className="grid gap-2 lg:grid-cols-2">
        {visibleRuns.map((meta) => {
          const run = byRunId.get(meta.runId);
          const status = run?.error ? "failed" : run?.status ?? "syncing";
          const stage = getPipelineStage(run?.current_node ?? null);
          const issue = classifyPipelineError(run?.error);
          const pct = run ? runProgressPct(run) : 0;
          return (
            <article key={meta.runId} className="rounded-xl border border-border bg-background/45 p-3">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="truncate text-sm font-semibold">{meta.agentName}</div>
                  <div className="mt-1 flex flex-wrap items-center gap-2 text-xs" style={{ color: "var(--al-on-surface-muted)" }}>
                    <span className="font-mono">{meta.ticker}</span>
                    <span>{run ? currentStageLabel(run) : "Syncing status"}</span>
                  </div>
                </div>
                <Pill variant={runStatusVariant(status)}>{status}</Pill>
              </div>
              <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-muted">
                <div className="h-full rounded-full bg-[var(--al-gold)] transition-all duration-500" style={{ width: `${pct}%` }} />
              </div>
              <div className="mt-2 flex flex-wrap items-center justify-between gap-2 text-xs" style={{ color: "var(--al-on-surface-muted)" }}>
                <span>{issue?.title ?? stage?.output ?? "Waiting for backend tracker"}</span>
                <span>{run ? runTimingLabel(run) : "Queued"}</span>
              </div>
            </article>
          );
        })}
      </div>

      {activeRuns.length > visibleRuns.length ? (
        <p className="text-xs" style={{ color: "var(--al-on-surface-muted)" }}>
          {activeRuns.length - visibleRuns.length} more analyst runs are tracked in the background.
        </p>
      ) : null}
    </section>
  );
}

interface RunProgress {
  total: number;
  completed: number;
  failed: number;
  running: number;
  pending: number;
  progressPct: number;
  reportsReady: number;
  etaLabel: string;
  etaDetail: string;
  currentStageLabel: string;
  currentStageDetail: string;
  stageStates: TopologyNodeState[];
}

function buildRunProgress(activeRuns: ActiveRunMeta[], runs: PipelineRun[] | undefined): RunProgress {
  if (!activeRuns.length) {
    return {
      total: 0,
      completed: 0,
      failed: 0,
      running: 0,
      pending: 0,
      progressPct: 0,
      reportsReady: 0,
      etaLabel: "-",
      etaDetail: "No active runs",
      currentStageLabel: "Idle",
      currentStageDetail: "No active runs",
      stageStates: PIPELINE_STAGES.map((stage) => ({ node: stage.id as PipelineStageId, status: "pending" })),
    };
  }

  const statusCounts: Record<RunStatus, number> = {
    pending: 0,
    running: 0,
    completed: 0,
    failed: 0,
  };
  const byRunId = new Map((runs ?? []).map((run) => [run.run_id, run] as const));
  const trackedRuns = activeRuns.map((meta) => byRunId.get(meta.runId)).filter((run): run is PipelineRun => Boolean(run));
  let progressTotal = 0;
  let reportsReady = 0;
  const remaining: number[] = [];

  for (const meta of activeRuns) {
    const run = byRunId.get(meta.runId);
    if (!run) {
      statusCounts.pending += 1;
      continue;
    }
    const status = run.error ? "failed" : run.status;
    statusCounts[status] += 1;
    progressTotal += runProgressPct(run);
    if (run.signal_card_id) reportsReady += 1;
    const eta = estimateRemainingSeconds(run);
    if (eta != null && status !== "completed" && status !== "failed") remaining.push(eta);
  }
  const total = activeRuns.length;
  const runningStages = trackedRuns
    .filter((run) => run.status === "running")
    .map((run) => getPipelineStage(run.current_node))
    .filter((stage): stage is NonNullable<typeof stage> => Boolean(stage));
  const activeStage = runningStages[0];
  const done = statusCounts.completed + statusCounts.failed;
  return {
    total,
    completed: statusCounts.completed,
    failed: statusCounts.failed,
    running: statusCounts.running,
    pending: statusCounts.pending,
    progressPct: Math.round(progressTotal / total),
    reportsReady,
    etaLabel: done === total
      ? statusCounts.failed > 0 ? "Stopped" : "Ready"
      : remaining.length
        ? `About ${formatDuration(Math.max(...remaining))}`
        : "Queueing",
    etaDetail: done === total
      ? statusCounts.failed > 0 ? `${statusCounts.failed} failed before publishing` : "all reports packaged"
      : "slowest active analyst",
    currentStageLabel: activeStage?.label ?? (done === total ? "Complete" : statusCounts.pending ? "Queued" : "Syncing"),
    currentStageDetail: activeStage?.description ?? (done === total ? "All analyst lanes finished" : "Waiting for backend node update"),
    stageStates: aggregatePipelineStageStates(trackedRuns),
  };
}

function BoardControlPanel({
  models,
  defaultModelLabel,
  selectedModel,
  onSelectModel,
  newsCount,
  totalDocs,
  enabledCount,
  totalAgents,
}: {
  models: { id: string; label: string; provider: string }[];
  defaultModelLabel: string | null;
  selectedModel: string;
  onSelectModel: (model: string) => void;
  newsCount: number | null;
  totalDocs: number | null;
  enabledCount: number;
  totalAgents: number;
}) {
  return (
    <div className="grid gap-4 rounded-xl border border-border bg-background/70 p-3 md:grid-cols-3">
      <div className="space-y-2 rounded-xl border-2 p-2" style={{ borderColor: "var(--al-gold)", background: "color-mix(in srgb, var(--al-gold) 6%, transparent)" }}>
        <div className="flex items-center gap-1.5 al-eyebrow" style={{ color: "var(--al-gold)" }}>
          <Cpu className="size-3.5" aria-hidden /> Model (next run)
        </div>
        <select
          value={selectedModel}
          onChange={(event) => onSelectModel(event.target.value)}
          className="h-10 w-full rounded-lg border-2 border-border bg-background px-2 text-sm font-semibold outline-none focus:ring-2 focus:ring-ring"
          aria-label="Model for next run"
        >
          <option value="">
            {defaultModelLabel ? `Default — ${defaultModelLabel}` : "Server default"}
          </option>
          {models.map((model) => (
            <option key={model.id} value={model.id}>
              {model.label}
            </option>
          ))}
        </select>
        <p className="text-[11px]" style={{ color: "var(--al-on-surface-muted)" }}>
          Applies to the next board run only.
        </p>
      </div>

      <div className="space-y-2">
        <div className="flex items-center gap-1.5 al-eyebrow">
          <Database className="size-3.5" aria-hidden /> Vector store
        </div>
        <div className="rounded-lg border border-border p-2.5">
          <div className="text-2xl font-semibold tabular-nums">
            {newsCount == null ? "—" : newsCount.toLocaleString()}
          </div>
          <div className="text-[11px]" style={{ color: "var(--al-on-surface-muted)" }}>
            news articles indexed
            {totalDocs != null ? ` · ${totalDocs.toLocaleString()} total docs` : ""}
          </div>
        </div>
      </div>

      <div className="space-y-2">
        <div className="flex items-center gap-1.5 al-eyebrow">
          <Users className="size-3.5" aria-hidden /> Analysts
        </div>
        <div className="rounded-lg border border-border p-2.5">
          <div className="text-2xl font-semibold tabular-nums">
            {enabledCount}<span className="text-base text-muted-foreground">/{totalAgents}</span>
          </div>
          <div className="text-[11px]" style={{ color: "var(--al-on-surface-muted)" }}>
            analysts enabled · toggle each on its card
          </div>
        </div>
      </div>
    </div>
  );
}

/**
 * First-run guide for the Decision Desk.
 *
 * Shown when a ticker has no published analysis and nothing is running, so the
 * board is never a dead "Awaiting…" screen for a first-time visitor. It explains
 * the product in plain language and offers a single one-click way to start.
 */
function FirstRunGuide({
  ticker,
  market,
  agentCount,
  onRun,
  isPending,
  disabled,
}: {
  ticker: string;
  market: "us" | "hk";
  agentCount: number;
  onRun: () => void;
  isPending: boolean;
  disabled: boolean;
}) {
  const steps = [
    {
      icon: Users,
      title: "The board runs",
      text: `${agentCount || "Several"} specialist analysts each study ${ticker || "your ticker"} through a different lens — value, momentum, supply chain and risk — using news, filings, prices, technicals and macro.`,
    },
    {
      icon: ShieldCheck,
      title: "Evidence gets graded",
      text: "Each analyst publishes a signal with its catalyst, risk and sources. Weak or unsourced claims are flagged as weak — never quietly hidden.",
    },
    {
      icon: Gavel,
      title: "A verdict is gated",
      text: "Only when the analysts agree, the data is fresh and claims check out does a soft BUY / SELL / HOLD read unlock. It's research, not advice.",
    },
  ];

  return (
    <section className="al-glass overflow-hidden p-6 md:p-8" style={{ borderColor: "var(--al-gold)" }}>
      <div className="max-w-2xl space-y-3">
        <div className="al-eyebrow">Start here</div>
        <h2 className="text-2xl md:text-3xl">No analysis on {ticker || "this ticker"} yet</h2>
        <p className="text-sm leading-6" style={{ color: "var(--al-on-surface-muted)" }}>
          The Decision Desk stays empty until you run the board. Launch the analysts on{" "}
          <span className="font-mono font-semibold text-foreground">{ticker || "a ticker"}</span> and watch them
          work in real time — a full board usually takes about 5 minutes.
        </p>
        <div className="flex flex-wrap items-center gap-2 pt-1">
          <Button onClick={onRun} disabled={disabled} className="al-gold-gradient rounded-full px-5">
            <Users data-icon="inline-start" className="size-4" aria-hidden />
            {isPending ? "Launching…" : `Run the board on ${ticker || "ticker"}`}
          </Button>
          <span className="text-xs" style={{ color: "var(--al-on-surface-muted)" }}>
            or pick another {market === "hk" ? "Hong Kong" : "US"} ticker above
          </span>
        </div>
      </div>
      <div className="mt-6 grid gap-3 md:grid-cols-3">
        {steps.map((step) => {
          const Icon = step.icon;
          return (
            <div
              key={step.title}
              className="rounded-xl border p-4"
              style={{ borderColor: "var(--al-outline)" }}
            >
              <Icon className="size-5" style={{ color: "var(--al-gold)" }} aria-hidden />
              <div className="mt-3 text-sm font-semibold">{step.title}</div>
              <p className="mt-1 text-xs leading-5" style={{ color: "var(--al-on-surface-muted)" }}>
                {step.text}
              </p>
            </div>
          );
        })}
      </div>
    </section>
  );
}

export function TickerBoard({ initialTicker }: { initialTicker?: string } = {}) {
  const queryClient = useQueryClient();
  const { market } = useMarket();
  const overnight = useOvernight();
  const [scope, setScope] = useState<"ticker" | "sector">("ticker");
  const [decisionMode, setDecisionMode] = useState<DecisionMode>("support");
  const seedTicker = initialTicker ? normalizeTicker(initialTicker) : "";
  const [draftTicker, setDraftTicker] = useState(seedTicker || "NVDA");
  const [ticker, setTicker] = useState(seedTicker || "NVDA");
  const [selectedSectorId, setSelectedSectorId] = useState(DEFAULT_SECTOR_ID);
  const [sectorFocusTicker, setSectorFocusTicker] = useState("NVDA");
  const [activeRuns, setActiveRuns] = useState<ActiveRunMeta[]>([]);
  const [selectedModel, setSelectedModel] = useState("");
  const [disabledAgentIds, setDisabledAgentIds] = useState<Set<number>>(() => new Set());

  // Persist the analyst on/off selection locally so it survives reloads.
  useEffect(() => {
    if (typeof window === "undefined") return;
    try {
      const raw = localStorage.getItem(DISABLED_AGENTS_KEY);
      if (raw) {
        const ids = JSON.parse(raw);
        if (Array.isArray(ids)) {
          setDisabledAgentIds(new Set(ids.filter((id) => typeof id === "number")));
        }
      }
    } catch {
      /* ignore malformed storage */
    }
  }, []);

  const toggleAgent = (agentId: number) => {
    setDisabledAgentIds((prev) => {
      const next = new Set(prev);
      if (next.has(agentId)) next.delete(agentId);
      else next.add(agentId);
      try {
        localStorage.setItem(DISABLED_AGENTS_KEY, JSON.stringify([...next]));
      } catch {
        /* ignore persistence failures */
      }
      return next;
    });
  };

  const agents = useQuery({
    queryKey: ["agents"],
    queryFn: fetchAgents,
    retry: false,
    staleTime: 60_000,
  });
  const modelCatalog = useQuery({
    queryKey: ["model-catalog"],
    queryFn: fetchModelCatalog,
    retry: false,
    staleTime: 5 * 60_000,
  });
  const vectorStats = useQuery({
    queryKey: ["vectordb-stats"],
    queryFn: fetchVectorDbStats,
    retry: false,
    staleTime: 30_000,
    refetchInterval: 60_000,
  });
  const sectorCatalog = useQuery({
    queryKey: ["sector-catalog", market],
    queryFn: () => fetchMarketSectorCatalog(market),
    retry: false,
    staleTime: 5 * 60_000,
  });
  const catalogSectors = useMemo(
    () => sectorCatalog.data?.sectors ?? [],
    [sectorCatalog.data]
  );

  // When the market switches (US ↔ HK), reset the active instrument so US
  // tickers never bleed into the HK view (and vice versa).
  const prevMarketRef = useRef(market);
  useEffect(() => {
    if (prevMarketRef.current === market) return;
    prevMarketRef.current = market;
    const next = DEFAULT_TICKER_BY_MARKET[market];
    setDraftTicker(next);
    setTicker(next);
    setSectorFocusTicker(next);
  }, [market]);

  // Keep the selected sector valid for the current market's catalog. If the
  // stored sector id isn't part of this market, fall back to its first sector.
  useEffect(() => {
    if (!catalogSectors.length) return;
    if (catalogSectors.some((item) => item.id === selectedSectorId)) return;
    const first = catalogSectors[0];
    setSelectedSectorId(first.id);
    setSectorFocusTicker(pickFocusTicker(first));
  }, [catalogSectors, selectedSectorId]);
  const markets = useQuery({
    queryKey: ["markets"],
    queryFn: fetchMarkets,
    retry: false,
    staleTime: 5 * 60_000,
  });
  const quickPicks = useMemo(() => {
    const fromApi = markets.data?.find((m) => m.id === market)?.quick_picks;
    return (fromApi && fromApi.length ? fromApi : QUICK_TICKERS_FALLBACK[market]).slice(0, 8);
  }, [markets.data, market]);
  const selectedSector = useMemo(
    () =>
      catalogSectors.find((item) => item.id === selectedSectorId) ?? catalogSectors[0],
    [catalogSectors, selectedSectorId]
  );
  const sectorTickerOptions = useMemo(
    () => selectedSector?.constituents.map(normalizeTicker) ?? [],
    [selectedSector]
  );
  const effectiveSectorFocusTicker = sectorTickerOptions.includes(normalizeTicker(sectorFocusTicker))
    ? normalizeTicker(sectorFocusTicker)
    : pickFocusTicker(selectedSector);
  const visibleTicker = scope === "ticker" ? ticker : effectiveSectorFocusTicker;

  // Curated coverage universe for the active market: the union of every
  // sector's constituents plus the market quick-picks. We use this to warn the
  // user — without blocking them — when they analyse a name that sits outside
  // the desk's curated universe, where filings depth, supply-chain mapping and
  // RAG history are typically much thinner.
  const coveredTickers = useMemo(() => {
    const set = new Set<string>();
    for (const sector of catalogSectors) {
      for (const constituent of sector.constituents) set.add(normalizeTicker(constituent));
    }
    for (const symbol of quickPicks) set.add(normalizeTicker(symbol));
    return set;
  }, [catalogSectors, quickPicks]);
  const activeTickerSymbol = normalizeTicker(visibleTicker);
  const coverageKnown = catalogSectors.length > 0;
  const isOutOfCoverage =
    scope === "ticker" &&
    coverageKnown &&
    activeTickerSymbol.length > 0 &&
    !coveredTickers.has(activeTickerSymbol);

  const signals = useQuery({
    queryKey: ["signals", "board", visibleTicker],
    queryFn: () => fetchSignals({ ticker: visibleTicker, page_size: 50 }),
    enabled: visibleTicker.length > 0,
    retry: false,
  });
  const runs = useQuery({
    queryKey: ["runs", "board", visibleTicker],
    queryFn: () => fetchRuns({ ticker: visibleTicker, page_size: 8 }),
    enabled: visibleTicker.length > 0,
    retry: false,
    refetchInterval: 15_000,
  });
  const recentRuns = useMemo(() => runs.data?.items ?? [], [runs.data?.items]);
  const recentActiveRuns = useMemo(
    () =>
      recentRuns
        .filter((run) => !run.error && (run.status === "pending" || run.status === "running"))
        .map((run) => ({
          runId: run.run_id,
          agentId: run.agent_id,
          agentName: run.agent_name ?? "Analyst run",
          ticker: run.ticker,
        })),
    [recentRuns]
  );
  const progressRuns = activeRuns.length ? activeRuns : recentActiveRuns;
  const activeRunIds = useMemo(() => progressRuns.map((run) => run.runId), [progressRuns]);
  const trackedRuns = useQuery({
    queryKey: ["runs", "tracked", activeRunIds],
    queryFn: () => Promise.all(activeRunIds.map((runId) => fetchRun(runId))),
    enabled: activeRunIds.length > 0,
    retry: false,
    refetchInterval: 3000,
  });
  const runProgress = useMemo(
    () => buildRunProgress(progressRuns, trackedRuns.data),
    [progressRuns, trackedRuns.data]
  );

  // Each ticker shows ONLY its own live progress: clear the tracked runs when
  // the visible ticker changes so a prior ticker's run never bleeds through.
  useEffect(() => {
    setActiveRuns([]);
  }, [visibleTicker]);

  // Auto-refresh cards + flash a completion effect the moment a board run
  // finishes. The signals query has no poll interval, so we invalidate it here
  // on the running → done transition instead of waiting for a manual reload.
  const [justCompleted, setJustCompleted] = useState(false);
  const prevActiveRunsRef = useRef(0);
  useEffect(() => {
    const activeNow = runProgress.running + runProgress.pending;
    if (prevActiveRunsRef.current > 0 && activeNow === 0 && runProgress.total > 0) {
      queryClient.invalidateQueries({ queryKey: ["signals"] });
      queryClient.invalidateQueries({ queryKey: ["runs"] });
      setJustCompleted(true);
    }
    prevActiveRunsRef.current = activeNow;
  }, [runProgress.running, runProgress.pending, runProgress.total, queryClient]);
  useEffect(() => {
    if (!justCompleted) return;
    const timer = setTimeout(() => setJustCompleted(false), 4500);
    return () => clearTimeout(timer);
  }, [justCompleted]);

  const boardRun = useMutation({
    onMutate: () => {
      setActiveRuns([]);
    },
    mutationFn: async () => {
      const model = selectedModel || undefined;

      if (scope === "ticker") {
        const enabledAgentIds = agentItems
          .filter((agent) => !disabledAgentIds.has(agent.id))
          .map((agent) => agent.id);
        if (!enabledAgentIds.length) throw new Error("Enable at least one analyst to run the board.");
        // Send agent_ids only when the user has narrowed the roster; omitting
        // it means "run every registered analyst" on the backend.
        const agentIds = disabledAgentIds.size ? enabledAgentIds : undefined;
        const targetTicker = normalizeTicker(draftTicker || ticker);
        if (!targetTicker) throw new Error("Ticker is required.");
        return [await triggerBoardRun({ ticker: targetTicker, agent_ids: agentIds, model })];
      }

      // Sector scope → ONE board-level synthesis (macro → trend →
      // second-order effects) instead of a per-ticker fanout.
      if (!selectedSector?.id) throw new Error("Select a sector first.");
      const synthesis = await triggerSectorSynthesis({
        sector_id: selectedSector.id,
        model,
      });
      const adapted: RunFanoutResponse = {
        ticker: synthesis.sector_label,
        sector_id: synthesis.sector_id,
        dry_run: false,
        runs: [
          {
            run_id: synthesis.run_id,
            agent_id: -1,
            agent_name: "Sector Strategist",
            status: "pending",
          },
        ],
      };
      return [adapted];
    },
    onSuccess: (data) => {
      const launchedRuns = data.flatMap((item) =>
        item.runs.map((run) => ({
          runId: run.run_id,
          agentId: run.agent_id,
          agentName: run.agent_name,
          ticker: item.ticker,
        }))
      );
      setActiveRuns(launchedRuns);
      queryClient.invalidateQueries({ queryKey: ["runs"] });
      queryClient.invalidateQueries({ queryKey: ["signals"] });
    },
    onError: () => {
      setActiveRuns([]);
    },
  });

  const agentItems = useMemo(
    () => sortAgents(agents.data ?? []),
    [agents.data]
  );
  const byAgent = useMemo(
    () => latestCardsByAgent(signals.data?.items ?? [], agentItems),
    [agentItems, signals.data]
  );
  const runsByAgent = useMemo(
    () => latestRunsByAgent(recentRuns, agentItems),
    [agentItems, recentRuns]
  );
  const liveCards = useMemo(() => Array.from(byAgent.values()), [byAgent]);
  const trust = useMemo(
    () => buildTickerTrustSummary(liveCards, agentItems.length),
    [agentItems.length, liveCards]
  );
  const activeRunCount = recentRuns.filter((run) => !run.error && (run.status === "pending" || run.status === "running")).length;
  const averageConfidence = liveCards.length
    ? Math.round(liveCards.reduce((sum, card) => sum + (normalizeConfidenceToPct(card.confidence) ?? 0), 0) / liveCards.length)
    : null;
  const boardLoading = agents.isLoading || signals.isLoading;

  // (First-run guide removed — empty decision panels now render greyed-out
  // in place instead of a separate onboarding screen.)

  // ── My Favourites (watchlist) ──────────────────────────────────
  const favourites = useQuery({
    queryKey: ["watchlist"],
    queryFn: fetchWatchlist,
    retry: false,
    staleTime: 30_000,
  });
  const favouriteTickers = useMemo(
    () => (favourites.data ?? []).map((item) => item.ticker),
    [favourites.data]
  );
  // Favourites shown / run on this page are scoped to the active market so a
  // HK session never surfaces US names (and vice-versa).
  const visibleFavouriteTickers = useMemo(
    () => favouriteTickers.filter((symbol) => marketForTicker(symbol) === market),
    [favouriteTickers, market]
  );
  const isFavourite = favouriteTickers.includes(normalizeTicker(visibleTicker));

  const toggleFavourite = useMutation({
    mutationFn: async () => {
      const symbol = normalizeTicker(visibleTicker);
      if (!symbol) throw new Error("Pick a ticker first.");
      if (favouriteTickers.includes(symbol)) {
        await removeFromWatchlist(symbol);
      } else {
        await addToWatchlist({ ticker: symbol });
      }
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["watchlist"] }),
  });

  const removeFavourite = useMutation({
    mutationFn: (symbol: string) => removeFromWatchlist(symbol),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["watchlist"] }),
  });

  const runFavourites = useMutation({
    onMutate: () => setActiveRuns([]),
    mutationFn: async () => {
      const tickers = visibleFavouriteTickers;
      if (!tickers.length) throw new Error("Add a ticker to My Favourites first.");
      const model = selectedModel || undefined;
      const enabledAgentIds = agentItems
        .filter((agent) => !disabledAgentIds.has(agent.id))
        .map((agent) => agent.id);
      if (!enabledAgentIds.length) throw new Error("Enable at least one analyst to run the board.");
      const agentIds = disabledAgentIds.size ? enabledAgentIds : undefined;
      const responses: RunFanoutResponse[] = [];
      for (const symbol of tickers) {
        responses.push(await triggerBoardRun({ ticker: symbol, agent_ids: agentIds, model }));
      }
      return responses;
    },
    onSuccess: (data) => {
      const launchedRuns = data.flatMap((item) =>
        item.runs.map((run) => ({
          runId: run.run_id,
          agentId: run.agent_id,
          agentName: run.agent_name,
          ticker: item.ticker,
        }))
      );
      setActiveRuns(launchedRuns);
      queryClient.invalidateQueries({ queryKey: ["runs"] });
      queryClient.invalidateQueries({ queryKey: ["signals"] });
    },
    onError: () => setActiveRuns([]),
  });

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (scope === "sector") {
      setSectorFocusTicker(effectiveSectorFocusTicker);
      return;
    }
    const next = normalizeTicker(draftTicker);
    if (!next) return;
    setScope("ticker");
    setDraftTicker(next);
    setTicker(next);
  }

  function runBoard() {
    if (scope === "ticker") {
      const next = normalizeTicker(draftTicker || ticker);
      if (!next) return;
      setDraftTicker(next);
      setTicker(next);
    }
    boardRun.mutate();
  }

  function startOvernight(mode: "loop" | "once", tickers: string[]) {
    const cleaned = tickers.map(normalizeTicker).filter(Boolean);
    if (!cleaned.length) return;
    const enabledAgentIds = agentItems
      .filter((agent) => !disabledAgentIds.has(agent.id))
      .map((agent) => agent.id);
    overnight.start({
      mode,
      tickers: cleaned,
      agentIds: disabledAgentIds.size ? enabledAgentIds : undefined,
      model: selectedModel || undefined,
      cycleDelayMs: OVERNIGHT_DEFAULT_CYCLE_DELAY_MS,
    });
  }

  return (
    <div className="space-y-6">
      <header className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
        <div>
          <div className="al-eyebrow">Evidence-gated stock view</div>
          <h1 className="text-3xl md:text-4xl">Stocks</h1>
          <p className="mt-2 max-w-2xl text-sm leading-6" style={{ color: "var(--al-on-surface-muted)" }}>
            Start with one ticker. MarketPulse shows the market read, the analyst split, and what evidence is still missing before a soft recommendation is allowed.
          </p>
        </div>

        <div className="flex w-full max-w-4xl flex-col gap-3 rounded-2xl border border-border bg-background/60 p-3">
          <div className="flex flex-wrap items-center gap-2">
            <div className="inline-flex rounded-full border-2 p-1" style={{ borderColor: "var(--al-gold)" }}>
              <button type="button" className={cn("rounded-full px-4 py-1.5 text-sm font-semibold transition-colors", scope === "ticker" ? "al-gold-gradient text-white" : "text-muted-foreground hover:text-foreground")} onClick={() => setScope("ticker")}>Ticker</button>
              <button type="button" className={cn("rounded-full px-4 py-1.5 text-sm font-semibold transition-colors", scope === "sector" ? "al-gold-gradient text-white" : "text-muted-foreground hover:text-foreground")} onClick={() => setScope("sector")}>Sector</button>
            </div>
            <ModeSwitch mode={decisionMode} setMode={setDecisionMode} recommendationAllowed={trust.recommendationAllowed} />
          </div>

          <BoardControlPanel
            models={modelCatalog.data?.options ?? []}
            defaultModelLabel={modelCatalog.data?.default ?? null}
            selectedModel={selectedModel}
            onSelectModel={setSelectedModel}
            newsCount={vectorStats.data?.news_articles ?? null}
            totalDocs={vectorStats.data?.total_docs ?? null}
            enabledCount={agentItems.filter((agent) => !disabledAgentIds.has(agent.id)).length}
            totalAgents={agentItems.length}
          />

          <div className="flex w-full flex-col gap-2 min-[560px]:flex-row min-[560px]:items-center">
            <form onSubmit={submit} className="flex min-w-0 flex-1 flex-col gap-2 min-[560px]:flex-row">
              {scope === "ticker" ? (
                <div className="relative min-w-0 flex-1">
                  <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2" style={{ color: "var(--al-gold)" }} aria-hidden />
                  <input
                    value={draftTicker}
                    onChange={(event) => setDraftTicker(event.target.value)}
                    className="h-11 w-full rounded-xl border-2 bg-background pl-9 pr-3 font-mono text-base font-semibold outline-none focus:ring-2 focus:ring-ring"
                    style={{ borderColor: "var(--al-gold)" }}
                    aria-label="Search any ticker"
                    placeholder="Search any ticker — e.g. NVDA"
                  />
                </div>
              ) : (
                <select
                  value={selectedSector?.id ?? ""}
                  onChange={(event) => {
                    const nextSectorId = event.target.value;
                    const nextSector = catalogSectors.find((item) => item.id === nextSectorId);
                    setSelectedSectorId(nextSectorId);
                    setSectorFocusTicker(pickFocusTicker(nextSector));
                  }}
                  className="h-11 min-w-0 flex-1 rounded-xl border-2 bg-background px-3 text-base font-semibold outline-none focus:ring-2 focus:ring-ring"
                  style={{ borderColor: "var(--al-gold)" }}
                  aria-label="Sector"
                >
                  {catalogSectors.map((sector) => <option key={sector.id} value={sector.id}>{sector.name}</option>)}
                </select>
              )}
              <Button type="submit" className="al-gold-gradient h-11 self-start rounded-full px-4 min-[560px]:self-auto">
                <Search data-icon="inline-start" className="size-4" aria-hidden />
                {scope === "ticker" ? "View" : "Focus"}
              </Button>
            </form>
            {scope === "ticker" ? (
              <Button
                type="button"
                variant="outline"
                aria-pressed={isFavourite}
                title={isFavourite ? "Remove from My Favourites" : "Add to My Favourites"}
                className="self-start rounded-full px-3 min-[560px]:self-auto"
                onClick={() => toggleFavourite.mutate()}
                disabled={toggleFavourite.isPending || !normalizeTicker(visibleTicker)}
              >
                <Star
                  data-icon="inline-start"
                  className={cn("size-4", isFavourite && "fill-[var(--al-gold)] text-[var(--al-gold)]")}
                  aria-hidden
                />
                {isFavourite ? "Saved" : "Save"}
              </Button>
            ) : null}
          </div>
        </div>
      </header>

      <Button
        type="button"
        onClick={runBoard}
        disabled={boardRun.isPending || agents.isLoading || !agentItems.length || (scope === "sector" && !selectedSector?.constituents?.length)}
        className="al-gold-gradient h-14 w-full rounded-2xl text-base font-semibold"
      >
        <Activity data-icon="inline-start" className="size-5" aria-hidden />
        {boardRun.isPending
          ? "Launching the analysis…"
          : scope === "ticker"
            ? `▶ Run board on ${normalizeTicker(visibleTicker) || "this ticker"}`
            : `▶ Run sector synthesis for ${selectedSector?.name ?? "the selected sector"}`}
      </Button>

      {isOutOfCoverage ? (
        <section
          className="al-glass flex items-start gap-3 p-3 text-xs leading-5"
          role="note"
          aria-label="Coverage notice"
        >
          <AlertCircle className="mt-0.5 size-4 shrink-0 text-amber-500" aria-hidden />
          <p style={{ color: "var(--al-on-surface-muted)" }}>
            <span className="font-semibold text-foreground">
              {activeTickerSymbol} is outside MarketPulse&apos;s curated coverage.
            </span>{" "}
            The desk is tuned for its tracked sectors (AI &amp; semiconductors, optical, space and
            their supply chains). You can still run a board on this name, but filings depth,
            supply-chain mapping and historical context are usually thinner here — treat the read
            with extra caution.
          </p>
        </section>
      ) : null}

      {scope === "ticker" && visibleFavouriteTickers.length ? (
        <section className="al-glass flex flex-wrap items-center gap-2 p-3">
          <div className="flex items-center gap-1.5 text-xs font-semibold" style={{ color: "var(--al-gold)" }}>
            <Star className="size-3.5 fill-[var(--al-gold)]" aria-hidden /> My Favourites
          </div>
          {visibleFavouriteTickers.map((symbol) => (
            <span
              key={symbol}
              className={cn(
                "inline-flex items-center gap-1 rounded-full border border-border py-1 pl-3 pr-1 text-xs font-semibold transition-colors",
                symbol === normalizeTicker(visibleTicker) && "bg-muted text-foreground"
              )}
            >
              <button
                type="button"
                onClick={() => {
                  setScope("ticker");
                  setDraftTicker(symbol);
                  setTicker(symbol);
                }}
                className="font-mono hover:underline"
              >
                {symbol}
              </button>
              <button
                type="button"
                aria-label={`Remove ${symbol} from favourites`}
                title={`Remove ${symbol}`}
                onClick={() => removeFavourite.mutate(symbol)}
                disabled={removeFavourite.isPending}
                className="grid size-4 place-items-center rounded-full text-muted-foreground hover:bg-muted hover:text-foreground"
              >
                <Minus className="size-3" aria-hidden />
              </button>
            </span>
          ))}
          <Button
            type="button"
            variant="outline"
            className="ml-auto rounded-full px-4"
            onClick={() => runFavourites.mutate()}
            disabled={runFavourites.isPending || boardRun.isPending || agents.isLoading || !agentItems.length}
          >
            <Users data-icon="inline-start" className="size-4" aria-hidden />
            {runFavourites.isPending ? "Launching…" : `Run all ${visibleFavouriteTickers.length}`}
          </Button>
          {runFavourites.isError ? (
            <span className="w-full text-xs text-amber-600 dark:text-amber-400">
              {runFavourites.error instanceof Error ? runFavourites.error.message : "Could not launch favourites."}
            </span>
          ) : null}
        </section>
      ) : null}

      {scope === "ticker" ? (
        <section className="al-glass flex flex-wrap items-center gap-3 p-3">
          <div className="flex items-center gap-1.5 text-xs font-semibold">
            <Moon className="size-3.5" style={{ color: "var(--al-gold)" }} aria-hidden /> Overnight runs
          </div>
          {overnight.status.running ? (
            <>
              <span className="text-xs" style={{ color: "var(--al-on-surface-muted)" }}>
                {overnight.status.mode === "loop" ? "Looping" : "Running"}{" "}
                {overnight.status.tickers.join(", ")} —{" "}
                {overnight.status.currentTicker
                  ? `now on ${overnight.status.currentTicker}`
                  : "preparing next"}{" "}
                · {overnight.status.completedRuns} done
              </span>
              <Button
                type="button"
                variant="outline"
                className="ml-auto rounded-full px-4 text-red-600 dark:text-red-400"
                onClick={overnight.stop}
              >
                <Square data-icon="inline-start" className="size-4" aria-hidden /> Stop
              </Button>
            </>
          ) : (
            <>
              <span className="text-xs" style={{ color: "var(--al-on-surface-muted)" }}>
                Leave the board analysing while you sleep. Loop repeats until you press Stop; once runs a single pass.
              </span>
              <div className="ml-auto flex flex-wrap items-center gap-2">
                {favouriteTickers.length ? (
                  <Button
                    type="button"
                    variant="outline"
                    className="rounded-full px-4"
                    onClick={() => startOvernight("loop", favouriteTickers)}
                    disabled={!agentItems.length}
                    title={`Loop ${favouriteTickers.length} favourites until Stop`}
                  >
                    <Moon data-icon="inline-start" className="size-4" aria-hidden />
                    Loop favourites
                  </Button>
                ) : null}
                <Button
                  type="button"
                  variant="outline"
                  className="rounded-full px-4"
                  onClick={() => startOvernight("loop", [normalizeTicker(visibleTicker)])}
                  disabled={!agentItems.length || !normalizeTicker(visibleTicker)}
                  title={`Loop ${normalizeTicker(visibleTicker)} until Stop`}
                >
                  <Moon data-icon="inline-start" className="size-4" aria-hidden />
                  Loop {normalizeTicker(visibleTicker) || "ticker"}
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  className="rounded-full px-4"
                  onClick={() =>
                    startOvernight(
                      "once",
                      favouriteTickers.length ? favouriteTickers : [normalizeTicker(visibleTicker)]
                    )
                  }
                  disabled={!agentItems.length || (!favouriteTickers.length && !normalizeTicker(visibleTicker))}
                  title="Run the chosen tickers once"
                >
                  Run once
                </Button>
              </div>
            </>
          )}
        </section>
      ) : null}

      {scope === "ticker" ? (
        <div className="flex flex-wrap gap-2">
          {quickPicks.map((item) => (
            <button
              key={item}
              type="button"
              onClick={() => {
                setDraftTicker(item);
                setTicker(item);
              }}
              className={cn("rounded-full border border-border px-3 py-1 text-xs font-semibold transition-colors hover:bg-muted/40", item === visibleTicker && "bg-muted text-foreground")}
            >
              {item}
            </button>
          ))}
          <span className="w-full text-xs leading-5" style={{ color: "var(--al-on-surface-muted)" }}>
            Search any {market === "hk" ? "Hong Kong" : "US"} ticker above — every symbol gets news, price, technical and macro analysis. Deep supply-chain mapping currently covers AI &amp; Semiconductor names; other tickers show lighter supply-chain context.
          </span>
        </div>
      ) : (
        <div className="al-glass p-4 text-sm" style={{ color: "var(--al-on-surface-muted)" }}>
          Sector mode runs ONE board-level synthesis for <span className="font-semibold text-foreground">{selectedSector?.name ?? "the selected sector"}</span> — it reads the macro backdrop and world events, names the dominant trend, and traces the second- and third-order effects across constituents. The result is a single sector strategist card (open it from the progress dock when ready).
        </div>
      )}

      {/* 1 — Posture / evidence / trust / run-queue: per-ticker, ticker mode only */}
      {scope === "ticker" ? (
        <section className={cn("grid gap-3 md:grid-cols-4", liveCards.length === 0 && "opacity-45 grayscale transition-opacity")}>
          <MetricChip label="Posture" value={consensusLabel(trust.posture)} sub={trust.analystAgreement.detail} className="min-w-full" hint="The board's overall lean — bullish, bearish or neutral — based on how the analysts line up. It is not a recommendation on its own." />
          <MetricChip label="Avg evidence score" value={averageConfidence == null ? "-" : `${averageConfidence}%`} sub="source/validation weighted" className="min-w-full" hint="Average strength of the analysts' evidence, weighted by how well claims were sourced and passed validation. Higher means better-backed, not 'more bullish'." />
          <MetricChip label="Trust score" value={`${trust.evidenceScore}%`} sub={trust.evidenceQuality} className="min-w-full" hint="How much weight to put on this read right now: a blend of analyst agreement, data freshness and how many claims checked out against real numbers." />
          <div className="al-glass flex items-center justify-between gap-3 p-4">
            <div>
              <div className="al-eyebrow">Run queue</div>
              <div className="mt-1 text-sm font-semibold">
                {runs.isError ? "Offline" : activeRunCount ? `${activeRunCount} active` : `${recentRuns.length} recent`}
              </div>
            </div>
            <Pill variant={runs.isError ? "amber" : activeRunCount ? "gold" : TRUST_VARIANT[trust.state]}>
              <Activity className="size-3" aria-hidden />
              {runs.isError ? "api issue" : activeRunCount ? "running" : trust.stateLabel}
            </Pill>
          </div>
        </section>
      ) : null}

      {/* 2 — Analysis progress (pinned on top). Analyst lanes show in ticker mode only. */}
      <section className="space-y-4">
        <ProgressPanel runProgress={runProgress} runs={trackedRuns.data} activeRuns={progressRuns} isSyncing={trackedRuns.isFetching} justCompleted={justCompleted} />

        <LatestRunNotice runs={recentRuns} totalAgents={agentItems.length} />

        {boardRun.isSuccess ? (
          <section className="al-glass flex flex-col gap-2 p-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <div className="al-eyebrow">Board run</div>
              <p className="text-sm font-semibold">
                {scope === "ticker"
                  ? `Launched ${boardRun.data.reduce((sum, item) => sum + item.runs.length, 0)} analyst runs for ${boardRun.data[0]?.ticker ?? visibleTicker}.`
                  : `Launched a sector synthesis for ${selectedSector?.name ?? "the selected sector"} — track it in the progress dock.`}
              </p>
            </div>
            <Pill variant="green">queued</Pill>
          </section>
        ) : null}

        {boardRun.isError ? (
          <section className="al-glass flex flex-col gap-2 p-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <div className="al-eyebrow">Board run</div>
              <p className="text-sm font-semibold">{boardRun.error instanceof Error ? boardRun.error.message : "Could not launch board run."}</p>
            </div>
            <Pill variant="amber">not launched</Pill>
          </section>
        ) : null}

        {scope === "ticker" ? (
          <>
            <div className="flex flex-wrap items-end justify-between gap-3">
              <div>
                <div className="al-eyebrow">Analyst lanes</div>
                <h2 className="mt-1 text-xl">{agentItems.length} specialist lenses</h2>
              </div>
              <Link href="/agents" className="inline-flex items-center gap-1 text-sm font-semibold hover:underline" style={{ color: "var(--al-gold)" }}>
                Manage agents <ArrowRight className="size-4" aria-hidden />
              </Link>
            </div>
            <div className="grid gap-4 lg:grid-cols-2">
              {agentItems.map((agent) => (
                <AgentLane
                  key={agent.id}
                  agent={agent}
                  card={byAgent.get(agent.id)}
                  latestRun={runsByAgent.get(agent.id)}
                  ticker={visibleTicker}
                  loading={agents.isLoading || signals.isLoading}
                  enabled={!disabledAgentIds.has(agent.id)}
                  onToggleEnabled={() => toggleAgent(agent.id)}
                />
              ))}
            </div>
          </>
        ) : null}
      </section>

      {/* Sector overview — sector mode only (the Sectors page, embedded here) */}
      {scope === "sector" ? (
        <section className="space-y-3">
          <div>
            <div className="al-eyebrow">Sector overview</div>
            <h2 className="mt-1 text-xl">Market structure · {selectedSector?.name ?? "sectors"}</h2>
            <p className="mt-1 max-w-3xl text-sm leading-6" style={{ color: "var(--al-on-surface-muted)" }}>
              Press <span className="font-semibold text-foreground">Run sector synthesis</span> above for a multi-agent read (macro → dominant trend → second- and third-order effects). Below is the live market-structure snapshot across sectors.
            </p>
          </div>
          <SectorPulse />
        </section>
      ) : null}

      {/* 3–6 — per-ticker decision panels: ticker mode only */}
      {scope === "ticker" ? (
        boardLoading ? (
          <DecisionDeskLoading />
        ) : (
          <>
            {/* 3 — Decision read */}
            <div className={cn(liveCards.length === 0 && "opacity-45 grayscale transition-opacity")}>
              <VerdictPanel ticker={visibleTicker} mode={decisionMode} setMode={setDecisionMode} trust={trust} liveCards={liveCards} totalAgents={agentItems.length} />
            </div>

            {/* 4 — Trust checklist (full width) */}
            <div className={cn(liveCards.length === 0 && "opacity-45 grayscale transition-opacity")}>
              <TrustChecklist checks={trust.checks} />
            </div>

            {/* 5 — Decision brief (full width) */}
            <div className={cn(liveCards.length === 0 && "opacity-45 grayscale transition-opacity")}>
              <DecisionBrief cards={liveCards} mode={decisionMode} trust={trust} />
            </div>

            <MarketNewsPanel ticker={visibleTicker} cards={liveCards} />

            {/* 6 — Chief Strategist (last) */}
            <div className={cn(liveCards.length === 0 && "opacity-45 grayscale transition-opacity")}>
              <ChiefVerdictPanel ticker={visibleTicker} totalAgents={agentItems.length} />
            </div>
          </>
        )
      ) : null}
    </div>
  );
}
