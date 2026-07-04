"use client";

import Link from "next/link";
import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  ExternalLink,
  FileText,
  Network,
  Sparkles,
  TrendingDown,
  TrendingUp,
  Users,
} from "lucide-react";

import {
  fetchAccuracyStats,
  fetchLatestSignal,
  fetchMe,
  fetchReports,
  fetchRuns,
  fetchSignals,
} from "@/lib/api";
import type { ReportSummary, RunStatus, RunSummary, Signal, SignalCard } from "@/types/api";
// The landing hero showcases a real, recent signal for this ticker when one
// exists; otherwise it shows an explicit empty state (never fabricated data).
const LANDING_DEMO_TICKER = "NVDA";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  MetricChip,
  Pill,
  RingSVG,
  SectorDot,
  type PillVariant,
} from "@/components/primitives";
import { cn } from "@/lib/utils";
import { useMarket, marketForTicker } from "@/lib/market-context";

const SIGNAL_VARIANT: Record<Signal, PillVariant> = {
  BULLISH: "green",
  BEARISH: "red",
  NEUTRAL: "gray",
};

const SIGNAL_TYPE_LABELS: Record<string, string> = {
  FUNDAMENTAL_SHIFT: "Fundamental shift",
  MEDIA_NARRATIVE: "Media narrative",
  TECHNICAL_ONLY: "Technical only",
};

const RUN_VARIANT: Record<RunStatus | string, PillVariant> = {
  pending: "gray",
  running: "gold",
  completed: "green",
  failed: "red",
};

const SECTORS = [
  {
    id: "ai_semiconductors",
    name: "AI Infrastructure",
    kind: "ai" as const,
  },
  {
    id: "space_rockets",
    name: "Space Systems",
    kind: "space" as const,
  },
  {
    id: "optical_communications",
    name: "Optical Networks",
    kind: "optical" as const,
  },
];

function fmtPct(v: number | null | undefined, digits = 1): string {
  if (v == null || Number.isNaN(v)) return "-";
  return `${v.toFixed(digits)}%`;
}

function fmtDate(iso: string | null | undefined): string {
  if (!iso) return "-";
  return new Date(iso).toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function confidenceToTen(value: number | null | undefined): number | null {
  if (value == null || Number.isNaN(value)) return null;
  const normalized = value <= 1 ? value * 10 : value;
  return Math.max(0, Math.min(normalized, 10));
}

function confidenceToPct(value: number | null | undefined): number | null {
  const score = confidenceToTen(value);
  return score == null ? null : Math.round(score * 10);
}

function buildEvidenceSummary(
  reports: ReportSummary[],
  signals: SignalCard[]
): { score: number; count: number; label: string } {
  const reportScores = reports
    .map((r) => confidenceToTen(r.confidence_score))
    .filter((v): v is number => v != null);
  if (reportScores.length) {
    return {
      score: Math.round((reportScores.reduce((sum, v) => sum + v, 0) / reportScores.length) * 10) / 10,
      count: reportScores.length,
      label: reportScores.length === 1 ? "saved report" : "saved reports",
    };
  }

  const signalScores = signals
    .map((signal) => confidenceToTen(signal.confidence))
    .filter((v): v is number => v != null);
  if (!signalScores.length) return { score: 0, count: 0, label: "evidence items" };
  return {
    score: Math.round((signalScores.reduce((sum, v) => sum + v, 0) / signalScores.length) * 10) / 10,
    count: signalScores.length,
    label: signalScores.length === 1 ? "signal card" : "signal cards",
  };
}

function toneFromSignals(signals: SignalCard[]) {
  const bullish = signals.filter((s) => s.signal === "BULLISH").length;
  const bearish = signals.filter((s) => s.signal === "BEARISH").length;
  const neutral = signals.filter((s) => s.signal === "NEUTRAL").length;

  if (bullish > bearish) {
    return {
      label: "Constructive",
      variant: "green" as PillVariant,
      icon: TrendingUp,
      detail: `${bullish} bullish, ${bearish} bearish, ${neutral} neutral`,
    };
  }
  if (bearish > bullish) {
    return {
      label: "Defensive",
      variant: "red" as PillVariant,
      icon: TrendingDown,
      detail: `${bearish} bearish, ${bullish} bullish, ${neutral} neutral`,
    };
  }
  return {
    label: signals.length ? "Mixed" : "Waiting",
    variant: "gray" as PillVariant,
    icon: Activity,
    detail: signals.length
      ? `${bullish} bullish, ${bearish} bearish, ${neutral} neutral`
      : "No live signals yet",
  };
}

function DashboardSkeleton() {
  return (
    <div className="space-y-6">
      <Skeleton className="h-36 w-full rounded-2xl" />
      <div className="grid gap-4 md:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-28 rounded-2xl" />
        ))}
      </div>
      <div className="grid gap-4 lg:grid-cols-[1.45fr_0.9fr]">
        <Skeleton className="h-96 rounded-2xl" />
        <Skeleton className="h-96 rounded-2xl" />
      </div>
    </div>
  );
}

function LandingDemoCard({ card }: { card: SignalCard }) {
  const pct = confidenceToPct(card.confidence) ?? 0;
  return (
    <Link href={`/signals/${card.id}`}>
      <article className="al-glass p-5 space-y-4">
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="font-mono text-lg font-bold tracking-tight">{card.ticker}</div>
            <div className="mt-1 text-xs" style={{ color: "var(--al-on-surface-muted)" }}>
              {card.signal_type
                ? (SIGNAL_TYPE_LABELS[card.signal_type] ?? card.signal_type)
                : "Fundamental shift"}
            </div>
          </div>
          <div className="flex flex-wrap justify-end gap-1.5">
            <Pill variant="green">live</Pill>
            <Pill variant={SIGNAL_VARIANT[card.signal]}>{card.signal.toLowerCase()}</Pill>
          </div>
        </div>

        <p className="text-base leading-7">{card.one_line}</p>

        <div className="grid gap-3 text-sm sm:grid-cols-2">
          <div>
            <div className="al-eyebrow">Catalyst</div>
            <p className="mt-1" style={{ color: "var(--al-on-surface-muted)" }}>
              {card.key_catalyst}
            </p>
          </div>
          <div>
            <div className="al-eyebrow">Risk</div>
            <p className="mt-1" style={{ color: "var(--al-on-surface-muted)" }}>
              {card.key_risk}
            </p>
          </div>
        </div>

        <div className="flex flex-wrap gap-2">
          <MetricChip label="Conviction" value={card.conviction_stated === false ? "not stated" : `${card.conviction ?? 3}/5`} />
          <MetricChip label="Evidence score" value={`${pct}%`} />
          <MetricChip label="Validation" value={card.validation_score ?? "pending"} />
        </div>
      </article>
    </Link>
  );
}

function LandingEmptyCard() {
  return (
    <Link href="/tickers" className="al-glass block p-5 hover:-translate-y-0.5 transition-transform">
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="al-eyebrow">No live signal yet</div>
          <h3 className="mt-1 text-lg">Run your first board</h3>
        </div>
        <Pill variant="gray">empty</Pill>
      </div>
      <p className="mt-4 text-sm leading-7" style={{ color: "var(--al-on-surface-muted)" }}>
        This panel fills with a real signal card the moment a ticker board completes. Nothing is
        shown until then — no sample data, no placeholders that could be mistaken for a real call.
      </p>
      <span className="mt-4 inline-flex items-center gap-1 text-sm font-semibold" style={{ color: "var(--al-gold)" }}>
        Analyze a ticker <ArrowRight className="size-4" aria-hidden />
      </span>
    </Link>
  );
}

// Below this many verified outcomes, a hit-rate is statistical noise, not a track record.
const TRACK_RECORD_MIN_SAMPLE = 30;

function TrackRecordPreview({ accuracy }: { accuracy?: Awaited<ReturnType<typeof fetchAccuracyStats>> }) {
  // Data not loaded yet (loading, or the accuracy ledger is unreachable).
  // Never invent a number here — show an honest neutral state instead.
  if (!accuracy) {
    return (
      <Link href="/accuracy" className="al-glass block p-5 hover:-translate-y-0.5 transition-transform">
        <div className="flex items-center justify-between gap-3">
          <div>
            <div className="al-eyebrow">Track record</div>
            <h2 className="mt-1 text-lg">Verified outcomes</h2>
          </div>
          <Pill variant="gray">loading</Pill>
        </div>
        <p className="mt-6 text-sm leading-6" style={{ color: "var(--al-on-surface-muted)" }}>
          Connecting to the accuracy ledger…
        </p>
      </Link>
    );
  }

  const checked = accuracy.checked ?? 0;

  // No predictions have matured yet — be explicit rather than show placeholder bars.
  if (checked === 0) {
    return (
      <Link href="/accuracy" className="al-glass block p-5 hover:-translate-y-0.5 transition-transform">
        <div className="flex items-center justify-between gap-3">
          <div>
            <div className="al-eyebrow">Track record</div>
            <h2 className="mt-1 text-lg">Verified outcomes</h2>
          </div>
          <Pill variant="gray">no verified calls yet</Pill>
        </div>
        <p className="mt-6 text-sm leading-6" style={{ color: "var(--al-on-surface-muted)" }}>
          Accuracy appears only after a call matures. Every signal is scored against the real price
          path one week later — none have matured yet, so there is nothing verified to show.
        </p>
        <span
          className="mt-4 inline-flex items-center gap-1 text-sm font-semibold"
          style={{ color: "var(--al-gold)" }}
        >
          See how scoring works
          <ArrowRight className="size-4" aria-hidden />
        </span>
      </Link>
    );
  }

  // Real verified data only: keep signal types that actually have matured outcomes.
  const bars = Object.entries(accuracy.by_signal_type ?? {})
    .filter(([, item]) => (item.total ?? 0) > 0 && item.accuracy_pct != null)
    .slice(0, 4)
    .map(([type, item]) => ({
      label: type,
      value: Math.round(item.accuracy_pct as number),
    }));
  const direction = fmtPct(accuracy.direction_accuracy_pct, 1);
  const lowSample = checked < TRACK_RECORD_MIN_SAMPLE;

  return (
    <Link href="/accuracy" className="al-glass block p-5 hover:-translate-y-0.5 transition-transform">
      <div className="flex items-center justify-between gap-3">
        <div>
          <div className="al-eyebrow">Track record</div>
          <h2 className="mt-1 text-lg">Verified outcomes</h2>
        </div>
        <Pill variant={lowSample ? "amber" : "gold"}>{direction}</Pill>
      </div>
      {bars.length > 0 ? (
        <div className="mt-6 flex h-24 items-end gap-3">
          {bars.map((bar) => (
            <div key={bar.label} className="flex flex-1 flex-col items-center gap-2">
              <div className="bar-track h-20 w-full rotate-180">
                <div className="bar-fill" style={{ height: `${Math.max(10, bar.value)}%`, width: "100%" }} />
              </div>
              <span className="text-[0.65rem] tabular-nums" style={{ color: "var(--al-on-surface-muted)" }}>
                {bar.value}%
              </span>
            </div>
          ))}
        </div>
      ) : (
        <p className="mt-6 text-sm leading-6" style={{ color: "var(--al-on-surface-muted)" }}>
          {checked} verified {checked === 1 ? "call" : "calls"} scored so far. The per-signal-type
          breakdown appears once each lane has matured outcomes.
        </p>
      )}
      <p className="mt-4 text-xs leading-5" style={{ color: "var(--al-on-surface-muted)" }}>
        {lowSample
          ? `Based on ${checked} verified ${checked === 1 ? "call" : "calls"} — an early sample, not yet statistically significant. Past results don't guarantee future performance.`
          : `Based on ${checked} verified calls. Past results don't guarantee future performance.`}
      </p>
    </Link>
  );
}

function PublicLanding() {
  const demo = useQuery({
    queryKey: ["landing", "demo-signal", LANDING_DEMO_TICKER],
    queryFn: () => fetchLatestSignal(LANDING_DEMO_TICKER),
    retry: false,
    staleTime: 60_000,
  });
  const accuracy = useQuery({
    queryKey: ["landing", "accuracy"],
    queryFn: fetchAccuracyStats,
    retry: false,
    staleTime: 60_000,
  });

  const liveCard = demo.data ?? null;

  return (
    <div className="space-y-10">
      <section className="grid min-h-[68vh] items-center gap-8 lg:grid-cols-[1fr_0.88fr]">
        <div className="space-y-6">
          <div className="inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-semibold" style={{ borderColor: "var(--al-outline)", color: "var(--al-on-surface-muted)" }}>
            <Sparkles className="size-3" aria-hidden />
            MarketPulse
          </div>
          <div className="space-y-4">
            <h1 className="max-w-3xl text-4xl md:text-6xl">Ticker conviction, gated by evidence.</h1>
            <p className="max-w-2xl text-base leading-7 md:text-lg" style={{ color: "var(--al-on-surface-muted)" }}>
              Specialist analysts debate one ticker, expose the evidence quality, and only unlock a soft recommendation when the trust checks pass.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Link href="/tickers">
              <Button className="al-gold-gradient rounded-full px-5">
                <Sparkles data-icon="inline-start" className="size-4" aria-hidden />
                Analyze ticker
              </Button>
            </Link>
            <Link href="/agents">
              <Button variant="outline" className="rounded-full px-5">
                <Users data-icon="inline-start" className="size-4" aria-hidden />
                Browse agents
              </Button>
            </Link>
          </div>
        </div>
        <div className="space-y-4">
          {demo.isLoading ? (
            <Skeleton className="h-72 rounded-2xl" />
          ) : liveCard ? (
            <LandingDemoCard card={liveCard} />
          ) : (
            <LandingEmptyCard />
          )}
          <div className="grid gap-3 sm:grid-cols-3">
            <MetricChip label="Signal" value={liveCard ? liveCard.signal.toLowerCase() : "—"} />
            <MetricChip label="Evidence" value={liveCard?.validation_score ?? "—"} />
            <MetricChip label="Ticker" value={liveCard?.ticker ?? "—"} />
          </div>
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-3">
        {[
          { icon: FileText, title: "Read the tape", text: "News, filings, prices, technicals and macro context are pulled into one ticker packet." },
          { icon: Users, title: "Run the board", text: "Specialist analysts look at the same ticker through value, momentum, supply chain and risk lenses." },
          { icon: CheckCircle2, title: "Verify the claim", text: "Structured fields make weak evidence visible instead of burying it inside a long report." },
        ].map((step) => {
          const Icon = step.icon;
          return (
            <article key={step.title} className="al-glass p-5">
              <Icon className="size-5" style={{ color: "var(--al-gold)" }} aria-hidden />
              <h2 className="mt-4 text-base">{step.title}</h2>
              <p className="mt-2 text-sm leading-6" style={{ color: "var(--al-on-surface-muted)" }}>
                {step.text}
              </p>
            </article>
          );
        })}
      </section>

      <section className="grid gap-5 lg:grid-cols-[0.9fr_1.1fr]">
        <TrackRecordPreview accuracy={accuracy.data} />
        <div className="grid gap-4 md:grid-cols-3">
          {[
            { title: "Multi-agent board", text: "One ticker becomes a structured debate instead of a single generic opinion." },
            { title: "Custom skills", text: "Markdown skills let advanced users create analysts for specific sectors and markets." },
            { title: "Verified claims", text: "Signals carry catalysts, risks, sources and validation status in the UI." },
          ].map((feature) => (
            <article key={feature.title} className="al-glass p-5">
              <div className="al-section-title text-base">{feature.title}</div>
              <p className="mt-2 text-sm leading-6" style={{ color: "var(--al-on-surface-muted)" }}>
                {feature.text}
              </p>
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}

function WelcomePanel() {
  return (
    <section className="al-thesis-banner rounded-r-[var(--al-radius-card)]">
      <div className="al-thesis-banner-label">Today brief</div>
      <div className="al-thesis-banner-text">
        Waiting for the first fresh signal card.
      </div>
      <div
        className="mt-3 text-sm leading-6 max-w-3xl"
        style={{ color: "var(--al-on-surface-muted)" }}
      >
        New ticker runs and overnight scans will appear here as a compact market brief.
      </div>
    </section>
  );
}

function MarketPulse({ signals }: { signals: SignalCard[] }) {
  const tone = toneFromSignals(signals);
  const ToneIcon = tone.icon;
  const latest = signals[0];
  const topRisks = signals.filter((s) => s.key_risk).slice(0, 2);

  return (
    <section className="al-glass p-5 space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="al-eyebrow">Market pulse</div>
          <h2 className="text-xl mt-1">Today&apos;s read</h2>
        </div>
        <Pill variant={tone.variant} className="capitalize">
          <ToneIcon className="size-3" aria-hidden />
          {tone.label}
        </Pill>
      </div>

      <div className="flex flex-wrap gap-2">
        <MetricChip label="Signal mix" value={tone.detail} />
        <MetricChip label="Last scan" value={fmtDate(latest?.created_at)} />
        <MetricChip
          label="Covered tickers"
          value={signals.length ? new Set(signals.map((s) => s.ticker)).size : 0}
        />
      </div>

      {topRisks.length > 0 ? (
        <div className="space-y-2">
          {topRisks.map((signal) => (
            <div
              key={`${signal.id}-${signal.ticker}`}
              className="flex gap-2 rounded-xl border p-3 text-sm"
              style={{ borderColor: "var(--al-outline)" }}
            >
              <AlertTriangle className="mt-0.5 size-4 shrink-0 text-amber-500" aria-hidden />
              <div>
                <span className="font-semibold">{signal.ticker}</span>
                <span style={{ color: "var(--al-on-surface-muted)" }}> - {signal.key_risk}</span>
              </div>
            </div>
          ))}
        </div>
      ) : null}
    </section>
  );
}

function WhatChanged({ signals }: { signals: SignalCard[] }) {
  const items = signals.slice(0, 3);
  return (
    <section className="al-glass p-5 space-y-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <div className="al-eyebrow">What changed</div>
          <h2 className="text-xl mt-1">Catalysts worth reading first</h2>
        </div>
      </div>
      {items.length ? (
        <div className="grid gap-3 md:grid-cols-3">
          {items.map((item) => (
            <article key={`${item.id}-${item.ticker}-${item.created_at}`} className="rounded-xl border p-4" style={{ borderColor: "var(--al-outline)" }}>
              <div className="flex items-center justify-between gap-3">
                <span className="font-mono text-sm font-bold">{item.ticker}</span>
                <Pill variant={SIGNAL_VARIANT[item.signal]}>{item.signal.toLowerCase()}</Pill>
              </div>
              <p className="mt-3 text-sm leading-6">{item.key_catalyst}</p>
              <p className="mt-2 line-clamp-2 text-xs" style={{ color: "var(--al-on-surface-muted)" }}>
                {item.one_line}
              </p>
            </article>
          ))}
        </div>
      ) : (
        <div className="rounded-xl border p-4 text-sm" style={{ borderColor: "var(--al-outline)", color: "var(--al-on-surface-muted)" }}>
          No live catalysts yet. Run a ticker analysis or overnight batch to populate today&apos;s briefing.
        </div>
      )}
    </section>
  );
}

function TickerStrip({ signals }: { signals: SignalCard[] }) {
  const items = signals.slice(0, 8);
  if (!items.length) return null;
  return (
    <section className="al-glass p-3">
      <div className="flex gap-2 overflow-x-auto pb-1">
        {items.map((item) => {
          const pct = confidenceToPct(item.confidence);
          return (
            <div
              key={`${item.id}-${item.ticker}-${item.signal}`}
              className="flex min-w-[150px] items-center justify-between gap-3 rounded-xl border px-3 py-2 text-xs"
              style={{ borderColor: "var(--al-outline)" }}
            >
              <div>
                <div className="font-mono font-bold">{item.ticker}</div>
                <div style={{ color: "var(--al-on-surface-muted)" }}>
                  {pct == null ? "evidence pending" : `${pct}% evidence`}
                </div>
              </div>
              <Pill variant={SIGNAL_VARIANT[item.signal]}>{item.signal.toLowerCase()}</Pill>
            </div>
          );
        })}
      </div>
    </section>
  );
}

function SignalTile({ card }: { card: SignalCard }) {
  const pct = confidenceToPct(card.confidence);
  return (
    <Link
      href={`/signals/${card.id}`}
      className="al-glass group block p-4 transition-transform hover:-translate-y-0.5"
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="font-mono text-sm font-bold tracking-tight">{card.ticker}</div>
          {card.signal_type ? (
            <div className="text-xs mt-0.5" style={{ color: "var(--al-on-surface-muted)" }}>
              {card.signal_type}
            </div>
          ) : null}
        </div>
        <Pill variant={SIGNAL_VARIANT[card.signal]}>{card.signal.toLowerCase()}</Pill>
      </div>

      {card.one_line ? (
        <p className="mt-3 line-clamp-3 text-sm leading-6">{card.one_line}</p>
      ) : null}

      <div className="mt-4 grid gap-3 text-xs md:grid-cols-2">
        {card.key_catalyst ? (
          <div>
            <div className="al-eyebrow">Catalyst</div>
            <p className="mt-1 line-clamp-2" style={{ color: "var(--al-on-surface-muted)" }}>
              {card.key_catalyst}
            </p>
          </div>
        ) : null}
        {card.key_risk ? (
          <div>
            <div className="al-eyebrow">Risk</div>
            <p className="mt-1 line-clamp-2" style={{ color: "var(--al-on-surface-muted)" }}>
              {card.key_risk}
            </p>
          </div>
        ) : null}
      </div>

      {card.supply_chain_impact?.length ? (
        <div className="mt-4 flex flex-wrap gap-1.5">
          {card.supply_chain_impact.slice(0, 3).map((impact) => (
            <Pill key={`${card.id}-${impact.ticker}`} variant="gray">
              {impact.direction} {impact.ticker}
            </Pill>
          ))}
        </div>
      ) : null}

      <div className="mt-4 flex items-center justify-between gap-3 text-xs">
        <div className="min-w-0 flex-1">
          <div className="bar-track">
            <div
              className={cn(
                "bar-fill",
                card.signal === "BULLISH" && "bar-bullish",
                card.signal === "BEARISH" && "bar-bearish"
              )}
              style={{ width: `${pct ?? 0}%` }}
            />
          </div>
        </div>
        <span className="tabular-nums" style={{ color: "var(--al-on-surface-muted)" }}>
          {pct == null ? "-" : `${pct}%`}
        </span>
      </div>
    </Link>
  );
}

function SectorHealth({ reports }: { reports: ReportSummary[] }) {
  const latestBySector = useMemo(() => {
    const map = new Map<string, ReportSummary>();
    for (const report of reports) {
      if (!map.has(report.sector_id)) map.set(report.sector_id, report);
    }
    return map;
  }, [reports]);

  return (
    <section className="al-glass p-5 space-y-5">
      <div>
        <div className="al-eyebrow">Asset health</div>
        <h2 className="text-lg mt-1">Sector evidence</h2>
      </div>

      <div className="space-y-4">
        {SECTORS.map((sector) => {
          const report = latestBySector.get(sector.id);
          const pct = confidenceToPct(report?.confidence_score) ?? 0;
          return (
            <div key={sector.id} className="space-y-2">
              <div className="flex items-center justify-between gap-3">
                <div className="flex items-center gap-2">
                  <SectorDot kind={sector.kind} />
                  <span className="text-sm font-semibold">{sector.name}</span>
                </div>
                <span className="text-xs tabular-nums" style={{ color: "var(--al-on-surface-muted)" }}>
                  {pct}%
                </span>
              </div>
              <div className="bar-track">
                <div className={cn("bar-fill", `bar-${sector.kind}`)} style={{ width: `${pct}%` }} />
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}

function EvidencePanel({
  score,
  count,
  sourceLabel,
}: {
  score: number;
  count: number;
  sourceLabel: string;
}) {
  const variant: PillVariant = score >= 7 ? "green" : score >= 4 ? "amber" : "gray";
  const pillLabel = score >= 7 ? "Strong evidence" : score >= 4 ? "Needs review" : "No evidence yet";
  return (
    <section className="al-glass p-5 space-y-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="al-eyebrow">Evidence score</div>
          <h2 className="text-lg mt-1">Validation quality</h2>
        </div>
        <Pill variant={variant}>{pillLabel}</Pill>
      </div>
      <div className="flex flex-col items-center gap-3 sm:flex-row sm:items-center">
        <RingSVG score={score} max={10} size={132} />
        <p className="text-sm leading-6" style={{ color: "var(--al-on-surface-muted)" }}>
          Average validation from {count} {sourceLabel}. Weak evidence remains visible until a stronger card replaces it.
        </p>
      </div>
    </section>
  );
}

function RecentRuns({ runs }: { runs: RunSummary[] }) {
  return (
    <section className="al-glass p-5 space-y-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <div className="al-eyebrow">Analysis queue</div>
          <h2 className="text-lg mt-1">Recent analyses</h2>
        </div>
      </div>

      {runs.length ? (
        <div className="divide-y" style={{ borderColor: "var(--al-outline)" }}>
          {runs.slice(0, 5).map((run) => (
            <div key={run.run_id} className="grid grid-cols-[1fr_auto] gap-3 py-3 text-sm">
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <span className="font-mono font-bold">{run.ticker}</span>
                  <Pill variant={RUN_VARIANT[run.status] ?? "gray"}>{run.status}</Pill>
                </div>
                <div className="mt-1 truncate text-xs" style={{ color: "var(--al-on-surface-muted)" }}>
                  {run.sector_id} - {fmtDate(run.created_at)}
                </div>
              </div>
              {run.signal_card_id ? (
                <Link
                  href={`/signals/${run.signal_card_id}`}
                  className="self-center text-xs hover:underline"
                  style={{ color: "var(--al-gold)" }}
                >
                  Signal #{run.signal_card_id}
                </Link>
              ) : (
                <span className="self-center text-xs" style={{ color: "var(--al-on-surface-muted)" }}>
                  {run.status === "failed" ? "No card" : run.status === "completed" ? "No card" : "Pending"}
                </span>
              )}
            </div>
          ))}
        </div>
      ) : (
        <p className="text-sm" style={{ color: "var(--al-on-surface-muted)" }}>
          No analyses recorded yet.
        </p>
      )}
    </section>
  );
}

function TodayDashboard() {
  const { market } = useMarket();
  const accuracy = useQuery({
    queryKey: ["accuracy"],
    queryFn: fetchAccuracyStats,
    staleTime: 60_000,
  });
  const signals = useQuery({
    queryKey: ["signals", { page_size: 6, market }],
    queryFn: () => fetchSignals({ page_size: 6, market }),
  });
  const reports = useQuery({
    queryKey: ["reports", { page_size: 50, market }],
    queryFn: () => fetchReports({ page_size: 50, market }),
  });
  const runs = useQuery({
    queryKey: ["runs", { page_size: 5 }],
    queryFn: () => fetchRuns({ page_size: 5 }),
  });

  const isLoading = accuracy.isLoading || signals.isLoading || reports.isLoading || runs.isLoading;
  const signalItems = signals.data?.items ?? [];
  const reportItems = reports.data?.items ?? [];
  const runItems = (runs.data?.items ?? []).filter((run) => marketForTicker(run.ticker) === market);
  const evidence = buildEvidenceSummary(reportItems, signalItems);
  const activeRunItems = runItems.filter((run) => !run.error && (run.status === "pending" || run.status === "running"));
  const usefulSectorReports = reportItems.filter((report) => (confidenceToPct(report.confidence_score) ?? 0) > 0);

  if (isLoading) return <DashboardSkeleton />;

  return (
    <div className="space-y-6">
      <header className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div>
          <div className="al-eyebrow">Today brief</div>
          <h1 className="text-3xl md:text-4xl">Signals that changed today</h1>
          <p className="mt-2 max-w-2xl text-sm md:text-base" style={{ color: "var(--al-on-surface-muted)" }}>
            A compact triage view for fresh signal cards, open analyst work, and verified track record.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link href="/tickers">
            <Button className="al-gold-gradient rounded-full px-4">
              <Sparkles data-icon="inline-start" className="size-4" aria-hidden />
              Decision Desk
            </Button>
          </Link>
          <Link href="/supply-chain">
            <Button variant="outline" className="rounded-full px-4">
              <Network data-icon="inline-start" className="size-4" aria-hidden />
              Supply Map
            </Button>
          </Link>
          <Link href="/reports">
            <Button variant="outline" className="rounded-full px-4">
              <FileText data-icon="inline-start" className="size-4" aria-hidden />
              Reports
            </Button>
          </Link>
        </div>
      </header>

      <section className="grid grid-cols-2 gap-2 md:grid-cols-3">
        <MetricChip label="Fresh signals" value={signalItems.length} sub={`${signalItems.filter((s) => s.signal === "BULLISH").length} bullish, ${signalItems.filter((s) => s.signal === "BEARISH").length} bearish`} className="min-w-0" />
        <MetricChip label="Open queue" value={activeRunItems.length} sub={runItems.length ? `${runItems.length} latest runs tracked` : "No current board work"} className="min-w-0" />
        <MetricChip
          label="Direction accuracy"
          value={accuracy.data ? fmtPct(accuracy.data.direction_accuracy_pct, 1) : "-"}
          sub={accuracy.data ? `${accuracy.data.direction_correct}/${accuracy.data.checked} checked` : "Awaiting checks"}
          className="col-span-2 min-w-0 md:col-span-1"
        />
      </section>

      <div className="grid gap-5 lg:grid-cols-[1.45fr_0.9fr]">
        <section className="space-y-4">
          {signalItems.length ? <MarketPulse signals={signalItems} /> : <WelcomePanel />}
          <WhatChanged signals={signalItems} />

          <div className="flex items-center justify-between gap-3">
            <div>
              <div className="al-eyebrow">Intelligence feed</div>
              <h2 className="text-xl mt-1">Latest signals</h2>
            </div>
            <Link
              href="/signals"
              className="inline-flex items-center gap-1 text-sm hover:underline"
              style={{ color: "var(--al-gold)" }}
            >
              View all <ArrowRight className="size-4" aria-hidden />
            </Link>
          </div>

          {signalItems.length ? (
            <div className="grid gap-3 md:grid-cols-2">
              {signalItems.map((card) => (
                <SignalTile key={card.id} card={card} />
              ))}
            </div>
          ) : (
            <div className="space-y-3">
              <div className="flex items-center gap-2 text-sm" style={{ color: "var(--al-on-surface-muted)" }}>
                <ExternalLink className="size-4" aria-hidden />
                No live signal cards yet. Run a ticker analysis or overnight batch to start the intelligence feed.
              </div>
            </div>
          )}
        </section>

        <aside className="space-y-5">
          <RecentRuns runs={activeRunItems.length ? activeRunItems : runItems.slice(0, 3)} />
          {evidence.count ? <EvidencePanel score={evidence.score} count={evidence.count} sourceLabel={evidence.label} /> : null}
          {usefulSectorReports.length ? <SectorHealth reports={usefulSectorReports} /> : null}
        </aside>
      </div>

      <TickerStrip signals={signalItems} />
    </div>
  );
}

export default function HomePage() {
  const me = useQuery({
    queryKey: ["users", "me"],
    queryFn: fetchMe,
    retry: false,
    staleTime: 60_000,
  });

  if (me.isLoading) return <DashboardSkeleton />;
  if (me.isError || !me.data) return <PublicLanding />;
  return <TodayDashboard />;
}
