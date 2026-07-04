"use client";

import type { FormEvent } from "react";
import { useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Maximize2, MessageSquareText, Minimize2, Minus, Search, X } from "lucide-react";
import { usePathname } from "next/navigation";

import { fetchLatestSignal, fetchSignalCard } from "@/lib/api";
import { SignalEvidenceChat } from "@/components/SignalEvidenceChat";
import { Button } from "@/components/ui/button";
import { Pill } from "@/components/primitives";
import { cn } from "@/lib/utils";

function normalizeTicker(value: string): string {
  return value.trim().toUpperCase().replace(/\s+/g, "");
}

function signalIdFromPath(pathname: string): number | null {
  const match = pathname.match(/^\/signals\/(\d+)/);
  if (!match) return null;
  const id = Number(match[1]);
  return Number.isFinite(id) ? id : null;
}

export function FloatingEvidenceChat() {
  const pathname = usePathname();
  const routeCardId = signalIdFromPath(pathname);
  const [open, setOpen] = useState(false);
  const [minimized, setMinimized] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const [draftTicker, setDraftTicker] = useState("NVDA");
  const [ticker, setTicker] = useState("NVDA");

  const triggerRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLElement>(null);
  const wasOpen = useRef(false);

  // Move focus into the panel when it opens; restore focus to the trigger when
  // it closes (but not on the initial mount).
  useEffect(() => {
    if (open) {
      panelRef.current?.focus();
    } else if (wasOpen.current) {
      triggerRef.current?.focus();
    }
    wasOpen.current = open;
  }, [open]);

  // Escape closes the panel.
  useEffect(() => {
    if (!open) return;
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [open]);

  const detailCard = useQuery({
    queryKey: ["signal", "floating-chat", routeCardId],
    queryFn: () => fetchSignalCard(routeCardId!),
    enabled: open && routeCardId != null,
    retry: false,
  });

  const latestCard = useQuery({
    queryKey: ["signal", "floating-chat", "latest", ticker],
    queryFn: () => fetchLatestSignal(ticker),
    enabled: open && routeCardId == null && ticker.length > 0,
    retry: false,
  });

  const card = routeCardId != null ? detailCard.data : latestCard.data;
  const isLoading = routeCardId != null ? detailCard.isLoading : latestCard.isLoading;
  const isError = routeCardId != null ? detailCard.isError : latestCard.isError;
  const displayTicker = card?.ticker ?? (routeCardId != null ? "signal card" : ticker);
  const title = useMemo(
    () => routeCardId != null ? `Signal #${routeCardId}` : `Latest ${displayTicker} card`,
    [displayTicker, routeCardId]
  );

  function submitTicker(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const next = normalizeTicker(draftTicker);
    if (!next) return;
    setTicker(next);
  }

  if (!open) {
    return (
      <button
        type="button"
        ref={triggerRef}
        onClick={() => {
          setOpen(true);
          setMinimized(false);
        }}
        className="fixed bottom-5 right-5 z-50 inline-flex items-center gap-2 rounded-full border border-border bg-background px-4 py-3 text-sm font-semibold shadow-2xl transition hover:-translate-y-0.5 hover:bg-muted"
        aria-label="Open evidence chat"
      >
        <MessageSquareText className="size-4" aria-hidden />
        Chat
      </button>
    );
  }

  return (
    <aside
      ref={panelRef}
      role="dialog"
      aria-label="MarketPulse evidence chat"
      tabIndex={-1}
      className="fixed bottom-4 right-3 z-50 max-w-[calc(100vw-1.5rem)] overflow-hidden rounded-xl border border-border bg-background shadow-2xl outline-none sm:right-5"
      style={{ width: expanded ? "min(640px, calc(100vw - 1.5rem))" : "min(380px, calc(100vw - 1.5rem))" }}
    >
      <div className="flex h-10 items-center justify-between gap-3 bg-zinc-950 px-3 text-white dark:bg-zinc-900">
        <button
          type="button"
          onClick={() => minimized && setMinimized(false)}
          className="flex min-w-0 flex-1 items-center gap-2 text-left text-sm font-semibold"
          aria-label={minimized ? "Expand evidence chat" : "Minimize evidence chat"}
        >
          <MessageSquareText className="size-4 shrink-0" aria-hidden />
          <span className="truncate">MarketPulse Chat</span>
        </button>
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={() => setMinimized((value) => !value)}
            className="rounded-md p-1 text-white/75 hover:bg-white/10 hover:text-white"
            aria-label={minimized ? "Expand evidence chat" : "Minimize evidence chat"}
          >
            {minimized ? <Maximize2 className="size-4" aria-hidden /> : <Minus className="size-4" aria-hidden />}
          </button>
          <button
            type="button"
            onClick={() => {
              setExpanded((value) => !value);
              setMinimized(false);
            }}
            className="rounded-md p-1 text-white/75 hover:bg-white/10 hover:text-white"
            aria-label={expanded ? "Shrink evidence chat" : "Expand evidence chat"}
          >
            {expanded ? <Minimize2 className="size-4" aria-hidden /> : <Maximize2 className="size-4" aria-hidden />}
          </button>
          <button
            type="button"
            onClick={() => setOpen(false)}
            className="rounded-md p-1 text-white/75 hover:bg-white/10 hover:text-white"
            aria-label="Close evidence chat"
          >
            <X className="size-4" aria-hidden />
          </button>
        </div>
      </div>

      <div
        className={cn(
          "max-h-[calc(100dvh-7rem)] overflow-y-auto border-t border-border bg-background",
          expanded && "max-h-[calc(100dvh-5rem)]",
          minimized && "hidden"
        )}
      >
        <div className="space-y-3 border-b border-border p-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="min-w-0">
              <div className="al-eyebrow">Evidence target</div>
              <div className="mt-1 truncate text-sm font-semibold">{title}</div>
            </div>
            <Pill variant={card ? (card.status === "needs_review" ? "amber" : "gold") : "gray"}>
              {card?.status === "needs_review" ? "needs review" : card ? "evidence ready" : "no card"}
            </Pill>
          </div>

          {routeCardId == null ? (
            <form onSubmit={submitTicker} className="flex gap-2">
              <input
                value={draftTicker}
                onChange={(event) => setDraftTicker(event.target.value)}
                className="h-9 min-w-0 flex-1 rounded-lg border border-border bg-background px-3 font-mono text-sm outline-none focus:ring-2 focus:ring-ring"
                aria-label="Chat ticker"
                placeholder="NVDA"
              />
              <Button type="submit" variant="outline" className="rounded-full">
                <Search data-icon="inline-start" className="size-4" aria-hidden />
                Load
              </Button>
            </form>
          ) : null}

          {isLoading ? (
            <p className="text-xs" aria-live="polite" style={{ color: "var(--al-on-surface-muted)" }}>Loading evidence...</p>
          ) : null}
          {isError ? (
            <p className="text-xs text-amber-600 dark:text-amber-300" role="status">
              No signal card found for this target yet. Run the analyst board, then ask from the published evidence.
            </p>
          ) : null}
        </div>

        <SignalEvidenceChat
          cardId={card?.id}
          ticker={displayTicker}
          compact={!expanded}
          showHeader={false}
          className="rounded-none border-0 bg-transparent p-3 shadow-none"
        />
      </div>
    </aside>
  );
}