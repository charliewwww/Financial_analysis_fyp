"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  ArrowRight,
  ArrowUpRight,
  BarChart3,
  CheckCircle2,
  Clock,
  Cpu,
  FileText,
  Network,
  Search,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  TrendingUp,
  Users,
} from "lucide-react";

import { fetchLatestSignal } from "@/lib/api";
import type { Signal, SignalCard } from "@/types/api";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  MetricChip,
  Pill,
  type PillVariant,
  Term,
} from "@/components/primitives";

// ── Constants ─────────────────────────────────────────────────────────────────

const LANDING_DEMO_TICKER = "NVDA";

// Covered names we steer beginners toward — deepest supply-chain + filings coverage.
const STARTER_TICKERS = ["NVDA", "TSM", "AMD", "AVGO", "MSFT"] as const;

const SIGNAL_VARIANT: Record<Signal, PillVariant> = {
  BULLISH: "green",
  BEARISH: "red",
  NEUTRAL: "gray",
};

// The six core features the product offers — each card is a doorway.
const FEATURES = [
  {
    icon: Sparkles,
    title: "Decision Desk",
    termKey: "Decision Desk",
    href: "/tickers",
    tag: "Transparent",
    description:
      "Pick a ticker and let multiple AI analysts debate. Get a Chief Verdict with conviction, catalyst, and risk — gated by evidence.",
    cta: "Analyze a stock",
  },
  {
    icon: Network,
    title: "Supply Chain Map",
    termKey: "Supply Chain Map",
    href: "/supply-chain",
    tag: "Our edge",
    description:
      "See how companies connect — who supplies whom — and trace second-order reasoning from upstream chips to downstream cloud.",
    cta: "Explore the map",
  },
  {
    icon: BarChart3,
    title: "Sectors",
    termKey: "sector",
    href: "/sectors",
    tag: "Big picture",
    description:
      "Browse sector health: breadth, top movers, and cap-weighted performance across AI, Space, and Optical networks.",
    cta: "View sectors",
  },
  {
    icon: Users,
    title: "Analysts",
    termKey: "analyst",
    href: "/agents",
    tag: "Model choice",
    description:
      "Meet the AI agents — each looks at a stock through a different lens: value, momentum, supply chain, or risk.",
    cta: "Browse agents",
  },
  {
    icon: CheckCircle2,
    title: "Track Record",
    termKey: "Track Record",
    href: "/accuracy",
    tag: "Verified",
    description:
      "Every signal is checked against the real price one week later. See verified hit rates by signal type.",
    cta: "See accuracy",
  },
  {
    icon: FileText,
    title: "Reports",
    termKey: "signal card",
    href: "/reports",
    tag: "Auditable",
    description:
      "Full archive of past analyses — each report includes news, filings, prices, technicals, and validation status.",
    cta: "Read reports",
  },
] as const;

// ── Helpers ───────────────────────────────────────────────────────────────────


function confidenceToTen(value: number | null | undefined): number | null {
  if (value == null || Number.isNaN(value)) return null;
  const normalized = value <= 1 ? value * 10 : value;
  return Math.max(0, Math.min(normalized, 10));
}

function confidenceToPct(value: number | null | undefined): number | null {
  const score = confidenceToTen(value);
  return score == null ? null : Math.round(score * 10);
}


// ── Feature Card ──────────────────────────────────────────────────────────────

function FeatureCard({
  icon: Icon,
  title,
  termKey,
  href,
  tag,
  description,
  cta,
}: {
  icon: React.ElementType;
  title: string;
  termKey: string;
  href: string;
  tag: string;
  description: string;
  cta: string;
}) {
  return (
    <Link
      href={href}
      className="al-glass group block p-5 transition-transform hover:-translate-y-0.5"
    >
      <div className="flex items-start justify-between gap-3">
        <Icon className="size-5 shrink-0" style={{ color: "var(--al-gold)" }} aria-hidden />
        <ArrowUpRight
          className="size-4 shrink-0 opacity-0 transition-opacity group-hover:opacity-100"
          style={{ color: "var(--al-on-surface-muted)" }}
          aria-hidden
        />
      </div>
      <div className="al-eyebrow mt-3">{tag}</div>
      <h3 className="mt-1 text-base">
        <Term name={termKey} noLink>{title}</Term>
      </h3>
      <p
        className="mt-2 text-sm leading-6"
        style={{ color: "var(--al-on-surface-muted)" }}
      >
        {description}
      </p>
      <span
        className="mt-3 inline-flex items-center gap-1 text-xs font-semibold"
        style={{ color: "var(--al-gold)" }}
      >
        {cta}
        <ArrowRight className="size-3" aria-hidden />
      </span>
    </Link>
  );
}

function FeatureGrid() {
  return (
    <section className="space-y-4">
      <div>
        <div className="al-eyebrow">What you can do here</div>
        <h2 className="text-xl mt-1">Six tools, one platform</h2>
      </div>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {FEATURES.map((feature) => (
          <FeatureCard key={feature.href} {...feature} />
        ))}
      </div>
    </section>
  );
}

// ── Live Data Cards ───────────────────────────────────────────────────────────

function LiveSignalCard({ card }: { card: SignalCard }) {
  const pct = confidenceToPct(card.confidence) ?? 0;
  return (
    <Link
      href={`/signals/${card.id}`}
      className="al-glass group block p-5 transition-transform hover:-translate-y-0.5"
    >
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="al-eyebrow">Latest signal</div>
          <h2 className="text-lg mt-1">
            <Term name={card.ticker} noLink>{card.ticker}</Term>
          </h2>
        </div>
        <div className="flex flex-wrap justify-end gap-1.5">
          <Pill variant="green">live</Pill>
          <Pill variant={SIGNAL_VARIANT[card.signal]}>
            {card.signal.toLowerCase()}
          </Pill>
        </div>
      </div>

      {card.one_line ? (
        <p className="mt-3 text-sm leading-6">{card.one_line}</p>
      ) : null}

      <div className="mt-4 grid gap-3 text-sm sm:grid-cols-2">
        {card.key_catalyst ? (
          <div>
            <div className="al-eyebrow">
              <Term name="catalyst" noLink>Catalyst</Term>
            </div>
            <p
              className="mt-1 line-clamp-2"
              style={{ color: "var(--al-on-surface-muted)" }}
            >
              {card.key_catalyst}
            </p>
          </div>
        ) : null}
        {card.key_risk ? (
          <div>
            <div className="al-eyebrow">
              <Term name="risk" noLink>Risk</Term>
            </div>
            <p
              className="mt-1 line-clamp-2"
              style={{ color: "var(--al-on-surface-muted)" }}
            >
              {card.key_risk}
            </p>
          </div>
        ) : null}
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        <MetricChip
          label="Conviction"
          hint="How strongly the analyst believes in the call, on a 1–5 scale."
          value={
            card.conviction_stated === false
              ? "not stated"
              : `${card.conviction ?? 3}/5`
          }
        />
        <MetricChip
          label="Evidence"
          hint="A 0–100% score showing how well the analyst's claims are backed by real data."
          value={`${pct}%`}
        />
        <MetricChip
          label="Validation"
          hint="Whether the AI's numerical claims were checked against real data sources."
          value={card.validation_score ?? "pending"}
        />
      </div>
    </Link>
  );
}

function LiveSignalEmpty() {
  return (
    <div className="al-glass p-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="al-eyebrow">Latest signal</div>
          <h2 className="text-lg mt-1">No live signal yet</h2>
        </div>
        <Pill variant="gray">empty</Pill>
      </div>
      <p
        className="mt-4 text-sm leading-6"
        style={{ color: "var(--al-on-surface-muted)" }}
      >
        This panel fills with a real{" "}
        <Term name="signal card">signal card</Term> the moment a ticker analysis
        completes. Nothing is shown until then — no sample data, no placeholders.
      </p>
      <Link
        href="/tickers"
        className="mt-4 inline-flex items-center gap-1 text-sm font-semibold"
        style={{ color: "var(--al-gold)" }}
      >
        Run your first analysis
        <ArrowRight className="size-4" aria-hidden />
      </Link>
    </div>
  );
}

// ── Try it in 3 steps (beginner tutorial) ──────────────────────────────────────

function StarterTickerChips() {
  return (
    <div className="mt-3 flex flex-wrap gap-2">
      {STARTER_TICKERS.map((symbol) => (
        <Link
          key={symbol}
          href={`/tickers?ticker=${symbol}`}
          className="rounded-full border px-3 py-1 font-mono text-xs font-semibold transition-colors hover:bg-muted/50"
          style={{ borderColor: "var(--al-outline)" }}
        >
          {symbol}
        </Link>
      ))}
    </div>
  );
}

function TryInThreeSteps() {
  const steps: Array<{
    icon: React.ElementType;
    title: string;
    body: React.ReactNode;
    extra?: React.ReactNode;
  }> = [
    {
      icon: Search,
      title: "1 · Pick a stock we cover",
      body: (
        <>
          MarketPulse goes deepest on AI &amp; semiconductor names, where the{" "}
          <Term name="supply chain impact">supply-chain</Term> mapping is richest.
          Tap one to open it:
        </>
      ),
      extra: <StarterTickerChips />,
    },
    {
      icon: Users,
      title: "2 · Let the analysts debate",
      body: (
        <>
          Four specialist AI <Term name="analyst">analysts</Term> — value, momentum,
          supply chain and risk — study the same stock and can disagree. You see every
          side, not one black-box answer.
        </>
      ),
    },
    {
      icon: ShieldCheck,
      title: "3 · Read the verdict, then check it",
      body: (
        <>
          Every claim shows its source and whether it was{" "}
          <Term name="validation">verified</Term> against real market data — so you trust
          the call because you can see the evidence.
        </>
      ),
    },
  ];

  return (
    <section className="al-glass p-6 md:p-8">
      <div className="al-eyebrow">New here? Start in 3 steps</div>
      <h2 className="mt-1 text-xl md:text-2xl">Try it yourself</h2>
      <div className="mt-5 grid gap-5 md:grid-cols-3">
        {steps.map((step) => {
          const Icon = step.icon;
          return (
            <div key={step.title} className="space-y-2">
              <Icon className="size-5" style={{ color: "var(--al-gold)" }} aria-hidden />
              <h3 className="text-sm font-semibold">{step.title}</h3>
              <p className="text-sm leading-6" style={{ color: "var(--al-on-surface-muted)" }}>
                {step.body}
              </p>
              {step.extra ?? null}
            </div>
          );
        })}
      </div>
      <div
        className="mt-6 flex flex-wrap items-center gap-2 rounded-xl border px-4 py-3 text-xs leading-5"
        style={{ borderColor: "var(--al-outline)", color: "var(--al-on-surface-muted)" }}
      >
        <Clock className="size-4 shrink-0" aria-hidden style={{ color: "var(--al-gold)" }} />
        <span>
          Ready-made analyses open instantly. Running a fresh board yourself takes about
          5 minutes — the analysts read live news, filings and prices before they answer.
        </span>
      </div>
    </section>
  );
}

// ── How to read a signal (annotates the live example) ───────────────────────────

function HowToReadCard() {
  const rows: Array<{ icon: React.ElementType; label: string; text: React.ReactNode }> = [
    {
      icon: Activity,
      label: "Direction & conviction",
      text: (
        <>
          <Term name="BULLISH">Bullish</Term>, <Term name="BEARISH">bearish</Term> or{" "}
          <Term name="NEUTRAL">neutral</Term>, plus a 1–5{" "}
          <Term name="conviction">conviction</Term> score for how strongly the analyst holds it.
        </>
      ),
    },
    {
      icon: TrendingUp,
      label: "Catalyst",
      text: (
        <>
          The specific <Term name="catalyst">catalyst</Term> that could move the price.
        </>
      ),
    },
    {
      icon: ShieldAlert,
      label: "Risk",
      text: (
        <>
          The <Term name="risk">risk</Term> that would prove the call wrong.
        </>
      ),
    },
    {
      icon: CheckCircle2,
      label: "Validation",
      text: (
        <>
          Whether each number was <Term name="validation">checked</Term> against real market
          data. Weak or unverified claims are flagged — never hidden.
        </>
      ),
    },
  ];

  return (
    <div className="al-glass p-5">
      <div className="al-eyebrow">How to read it</div>
      <h2 className="mt-1 text-lg">What the example shows</h2>
      <ul className="mt-4 space-y-3">
        {rows.map((row) => {
          const Icon = row.icon;
          return (
            <li key={row.label} className="flex gap-3">
              <Icon
                className="mt-0.5 size-4 shrink-0"
                style={{ color: "var(--al-gold)" }}
                aria-hidden
              />
              <div className="text-sm leading-6">
                <span className="font-semibold">{row.label}. </span>
                <span style={{ color: "var(--al-on-surface-muted)" }}>{row.text}</span>
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

// ── Hero ──────────────────────────────────────────────────────────────────────

function WhyTrust() {
  const pillars: Array<{ icon: React.ElementType; title: string; body: string }> = [
    {
      icon: Users,
      title: "Four analysts, not one black box",
      body: "See each specialist's take — value, momentum, supply chain and risk — and exactly where they disagree.",
    },
    {
      icon: ShieldCheck,
      title: "Every number is checked",
      body: "Claims are verified against real market data before you see them. Weak or unverified ones are flagged, never hidden.",
    },
    {
      icon: Network,
      title: "It follows the ripple effects",
      body: "Second-order reasoning traces how one company's news moves its suppliers and its customers.",
    },
    {
      icon: Cpu,
      title: "Runs on any model",
      body: "Choose the AI per run — including a free, local one — so you're never locked in or forced to pay.",
    },
    {
      icon: CheckCircle2,
      title: "Scored against reality",
      body: "Every call is checked against the real price a week later, so the track record is earned, not claimed.",
    },
  ];

  return (
    <section className="al-glass p-6 md:p-8">
      <div className="al-eyebrow">Why you can trust it</div>
      <h2 className="mt-1 text-xl md:text-2xl">Built to be checked, not just believed</h2>
      <div className="mt-5 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
        {pillars.map((pillar) => {
          const Icon = pillar.icon;
          return (
            <div key={pillar.title} className="flex gap-3">
              <Icon
                className="mt-0.5 size-5 shrink-0"
                style={{ color: "var(--al-gold)" }}
                aria-hidden
              />
              <div>
                <h3 className="text-sm font-semibold">{pillar.title}</h3>
                <p className="mt-1 text-sm leading-6" style={{ color: "var(--al-on-surface-muted)" }}>
                  {pillar.body}
                </p>
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}

function Hero() {
  return (
    <section className="space-y-6">
      <div className="inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-semibold" style={{ borderColor: "var(--al-outline)", color: "var(--al-on-surface-muted)" }}>
        <Sparkles className="size-3" aria-hidden />
        Welcome to MarketPulse
      </div>
      <div className="space-y-4">
        <h1 className="max-w-3xl text-3xl md:text-5xl">
          Understand any stock — and check the AI&apos;s reasoning yourself.
        </h1>
        <p
          className="max-w-2xl text-base leading-7 md:text-lg"
          style={{ color: "var(--al-on-surface-muted)" }}
        >
          MarketPulse puts a board of specialist AI{" "}
          <Term name="analyst">analysts</Term> on a single stock, then shows the
          evidence behind every call — so you can trust it, not just take its word.
        </p>
      </div>
      <div className="flex flex-wrap gap-2">
        <Link href={`/tickers?ticker=${LANDING_DEMO_TICKER}`}>
          <Button className="al-gold-gradient rounded-full px-5">
            <Sparkles data-icon="inline-start" className="size-4" aria-hidden />
            See a ready example
          </Button>
        </Link>
        <Link href="/supply-chain">
          <Button variant="outline" className="rounded-full px-5">
            <Network data-icon="inline-start" className="size-4" aria-hidden />
            Explore the supply chain
          </Button>
        </Link>
      </div>
    </section>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function HomePage() {
  // One live example so the landing page shows real substance, not placeholders.
  const demo = useQuery({
    queryKey: ["landing", "demo-signal", LANDING_DEMO_TICKER],
    queryFn: () => fetchLatestSignal(LANDING_DEMO_TICKER),
    retry: false,
    staleTime: 60_000,
  });

  const liveCard = demo.data ?? null;

  return (
    <div className="space-y-8">
      {/* Plain-language welcome + primary action */}
      <Hero />

      {/* Strengths up front — the reasons this can be trusted (kept concise) */}
      <WhyTrust />

      {/* Beginner tutorial: guided path with scope-steering + run-time expectations */}
      <TryInThreeSteps />

      {/* One real example, annotated so first-timers learn to read a signal */}
      <section className="grid gap-4 lg:grid-cols-2">
        {liveCard ? (
          <LiveSignalCard card={liveCard} />
        ) : demo.isLoading ? (
          <Skeleton className="h-64 rounded-2xl" />
        ) : (
          <LiveSignalEmpty />
        )}
        <HowToReadCard />
      </section>

      {/* Explore the rest of the platform, one calm click away */}
      <FeatureGrid />
    </div>
  );
}