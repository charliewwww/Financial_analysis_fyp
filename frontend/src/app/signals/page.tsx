"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { LayoutGrid, List, Minus, TrendingDown, TrendingUp } from "lucide-react";
import { fetchSignals } from "@/lib/api";
import type { Signal, SignalCard } from "@/types/api";
import { useMarket, MARKET_LABELS } from "@/lib/market-context";
import { SignalCardItem } from "@/components/SignalCard";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorState, EmptyState } from "@/components/StateMessage";
import { Pill, type PillVariant } from "@/components/primitives";
import { formatClock, formatDateTime } from "@/lib/format";
import { cn } from "@/lib/utils";

const SIGNALS: Signal[] = ["BULLISH", "BEARISH", "NEUTRAL"];
const VIEW_KEY = "marketpulse-signals-view";

type ViewMode = "cards" | "compact";

const SIGNAL_VARIANT: Record<string, PillVariant> = {
  BULLISH: "green",
  BEARISH: "red",
  NEUTRAL: "gray",
};
const SIGNAL_ICON: Record<string, typeof TrendingUp> = {
  BULLISH: TrendingUp,
  BEARISH: TrendingDown,
  NEUTRAL: Minus,
};

function CardSkeleton() {
  return (
    <div className="rounded-xl border border-border p-4 space-y-3">
      <Skeleton className="h-5 w-20" />
      <Skeleton className="h-4 w-full" />
      <Skeleton className="h-4 w-4/5" />
    </div>
  );
}

/** Dense one-line row so a screen of cards (e.g. 5 tickers × 4 analysts) stays scannable. */
function SignalRow({ card }: { card: SignalCard }) {
  const Icon = SIGNAL_ICON[card.signal] ?? Minus;
  return (
    <Link
      href={`/signals/${card.id}`}
      className="grid grid-cols-[88px_minmax(0,1fr)_auto] items-center gap-3 rounded-lg border px-3 py-2.5 transition hover:-translate-y-0.5"
      style={{ borderColor: "var(--al-outline)" }}
    >
      <div className="flex items-center gap-2">
        <span className="font-mono text-sm font-bold">{card.ticker}</span>
      </div>
      <div className="min-w-0">
        <p className="truncate text-sm leading-5">
          {card.one_line || <span style={{ color: "var(--al-on-surface-muted)" }}>No summary</span>}
        </p>
      </div>
      <div className="flex items-center gap-2">
        {card.confidence != null ? (
          <span className="hidden text-xs tabular-nums sm:inline" style={{ color: "var(--al-on-surface-muted)" }}>
            {Math.round(card.confidence * 100)}%
          </span>
        ) : null}
        <span className="hidden text-xs tabular-nums md:inline" style={{ color: "var(--al-on-surface-muted)" }}>
          {formatDateTime(card.created_at)}
        </span>
        <Pill variant={SIGNAL_VARIANT[card.signal] ?? "gray"}>
          <Icon className="size-3" aria-hidden />
          {card.signal.toLowerCase()}
        </Pill>
      </div>
    </Link>
  );
}

export default function SignalsPage() {
  const { market } = useMarket();
  const [ticker, setTicker] = useState("");
  const [signal, setSignal] = useState<Signal | "">("");
  const [page, setPage] = useState(1);
  const [view, setView] = useState<ViewMode>("cards");
  const PAGE_SIZE = 12;

  useEffect(() => {
    const stored = window.localStorage.getItem(VIEW_KEY);
    if (stored === "cards" || stored === "compact") setView(stored);
  }, []);

  // Reset to the first page whenever the active market changes.
  useEffect(() => {
    setPage(1);
  }, [market]);

  const setViewMode = (next: ViewMode) => {
    setView(next);
    window.localStorage.setItem(VIEW_KEY, next);
  };

  const { data, isLoading, isError, error, refetch, dataUpdatedAt } = useQuery({
    queryKey: ["signals", { ticker, signal, page, market }],
    queryFn: () =>
      fetchSignals({
        ticker: ticker || undefined,
        signal: (signal as Signal) || undefined,
        market,
        page,
        page_size: PAGE_SIZE,
      }),
  });

  const totalPages = data ? Math.ceil(data.total / PAGE_SIZE) : 1;
  const activeFilter = [ticker || null, signal || null].filter(Boolean).join(" / ") || "All signals";

  return (
    <div className="space-y-6">
      <header className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
        <div>
          <div className="al-eyebrow">Evidence library</div>
          <h1 className="mt-1 text-3xl md:text-4xl">Signal Evidence Library</h1>
          <p className="mt-2 max-w-3xl text-sm leading-6" style={{ color: "var(--al-on-surface-muted)" }}>
            Every published signal card keeps the thesis, catalyst, risk, sources, and validation status visible so old calls can be challenged later.
          </p>
        </div>
        <Pill variant="gold">auditable cards</Pill>
      </header>

      {/* Compact toolbar: filters + counts on one slim row so cards stay above the fold */}
      <section className="al-glass flex flex-wrap items-center gap-3 p-3">
        <input
          value={ticker}
          onChange={(e) => {
            setTicker(e.target.value.toUpperCase());
            setPage(1);
          }}
          placeholder="Filter by ticker…"
          aria-label="Filter signals by ticker"
          className="w-36 rounded-md border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring uppercase"
        />
        <select
          value={signal}
          onChange={(e) => {
            setSignal(e.target.value as Signal | "");
            setPage(1);
          }}
          aria-label="Filter signals by direction"
          className="rounded-md border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
        >
          <option value="">All signals</option>
          {SIGNALS.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
        <span className="ml-auto text-xs tabular-nums" style={{ color: "var(--al-on-surface-muted)" }}>
          {MARKET_LABELS[market].short} · {data?.total ?? "—"} cards · {activeFilter} · page {page}/{totalPages}
          {dataUpdatedAt ? <span aria-live="polite"> · updated {formatClock(dataUpdatedAt)}</span> : null}
        </span>
        <div className="flex items-center gap-1 rounded-md border border-border p-0.5">
          <button
            type="button"
            onClick={() => setViewMode("cards")}
            aria-pressed={view === "cards"}
            title="Card view"
            className={cn(
              "inline-flex items-center gap-1 rounded px-2 py-1 text-xs transition",
              view === "cards" ? "bg-[var(--al-gold)] text-[var(--al-gold-on)]" : "text-muted-foreground hover:text-foreground"
            )}
          >
            <LayoutGrid className="size-3.5" aria-hidden /> Cards
          </button>
          <button
            type="button"
            onClick={() => setViewMode("compact")}
            aria-pressed={view === "compact"}
            title="Compact list"
            className={cn(
              "inline-flex items-center gap-1 rounded px-2 py-1 text-xs transition",
              view === "compact" ? "bg-[var(--al-gold)] text-[var(--al-gold-on)]" : "text-muted-foreground hover:text-foreground"
            )}
          >
            <List className="size-3.5" aria-hidden /> Compact
          </button>
        </div>
      </section>

      {/* Cards grid */}
      {isError && (
        <ErrorState
          title="Failed to load signals"
          detail={String(error)}
          onRetry={() => refetch()}
        />
      )}

      {view === "compact" ? (
        <div className="space-y-2">
          {isLoading
            ? Array.from({ length: 8 }).map((_, i) => <Skeleton key={i} className="h-12 w-full rounded-lg" />)
            : data?.items.map((card) => <SignalRow key={card.id} card={card} />)}
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {isLoading
            ? Array.from({ length: 6 }).map((_, i) => <CardSkeleton key={i} />)
            : data?.items.map((card) => <SignalCardItem key={card.id} card={card} />)}
        </div>
      )}

      {!isLoading && data?.items.length === 0 && (
        <EmptyState
          title="No signal cards match this filter"
          detail="Run the Decision Desk board or clear the filter to review previous evidence."
        />
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-4 pt-2">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
            className="text-sm text-muted-foreground hover:text-foreground disabled:opacity-40 transition-colors"
          >
            ← Previous
          </button>
          <span className="text-sm text-muted-foreground">
            Page {page} of {totalPages}
          </span>
          <button
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
            className="text-sm text-muted-foreground hover:text-foreground disabled:opacity-40 transition-colors"
          >
            Next →
          </button>
        </div>
      )}
    </div>
  );
}
