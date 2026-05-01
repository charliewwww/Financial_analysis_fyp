"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchSignals } from "@/lib/api";
import type { Signal } from "@/types/api";
import { SignalCardItem } from "@/components/SignalCard";
import { Skeleton } from "@/components/ui/skeleton";

const SIGNALS: Signal[] = ["BULLISH", "BEARISH", "NEUTRAL"];

function CardSkeleton() {
  return (
    <div className="rounded-xl border border-border p-4 space-y-3">
      <Skeleton className="h-5 w-20" />
      <Skeleton className="h-4 w-full" />
      <Skeleton className="h-4 w-4/5" />
    </div>
  );
}

export default function SignalsPage() {
  const [ticker, setTicker] = useState("");
  const [signal, setSignal] = useState<Signal | "">("");
  const [page, setPage] = useState(1);
  const PAGE_SIZE = 12;

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["signals", { ticker, signal, page }],
    queryFn: () =>
      fetchSignals({
        ticker: ticker || undefined,
        signal: (signal as Signal) || undefined,
        page,
        page_size: PAGE_SIZE,
      }),
  });

  const totalPages = data ? Math.ceil(data.total / PAGE_SIZE) : 1;

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-1">
        <h1 className="text-2xl font-bold">Morning Brief</h1>
        <p className="text-sm text-muted-foreground">
          Latest AI-generated signal cards
        </p>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3">
        <input
          value={ticker}
          onChange={(e) => {
            setTicker(e.target.value.toUpperCase());
            setPage(1);
          }}
          placeholder="Filter by ticker…"
          className="w-36 rounded-md border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring uppercase"
        />
        <select
          value={signal}
          onChange={(e) => {
            setSignal(e.target.value as Signal | "");
            setPage(1);
          }}
          className="rounded-md border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
        >
          <option value="">All signals</option>
          {SIGNALS.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
      </div>

      {/* Cards grid */}
      {isError && (
        <p className="text-sm text-red-400">
          Failed to load signals: {String(error)}
        </p>
      )}

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {isLoading
          ? Array.from({ length: 6 }).map((_, i) => (
              <CardSkeleton key={i} />
            ))
          : data?.items.map((card) => (
              <SignalCardItem key={card.id} card={card} />
            ))}
      </div>

      {!isLoading && data?.items.length === 0 && (
        <p className="text-sm text-muted-foreground text-center py-10">
          No signal cards found. Run the pipeline to generate signals.
        </p>
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
