"use client";

import { createContext, useContext, useEffect, useState } from "react";

export type MarketId = "us" | "hk";

export const MARKET_LABELS: Record<MarketId, { short: string; name: string; currency: string }> = {
  us: { short: "US", name: "United States", currency: "USD" },
  hk: { short: "HK", name: "Hong Kong", currency: "HKD" },
};

const STORAGE_KEY = "marketpulse-market";

/**
 * Classify a ticker into its market. Mirrors the backend `classify_market`:
 * Hong Kong listings use a numeric symbol with a `.HK` suffix (e.g. `0700.HK`);
 * everything else is treated as US.
 */
export function marketForTicker(ticker: string | null | undefined): MarketId {
  return (ticker ?? "").trim().toUpperCase().endsWith(".HK") ? "hk" : "us";
}

interface MarketContextValue {
  market: MarketId;
  setMarket: (m: MarketId) => void;
}

const MarketContext = createContext<MarketContextValue | null>(null);

function readInitialMarket(): MarketId {
  if (typeof window === "undefined") return "us";
  const stored = localStorage.getItem(STORAGE_KEY);
  return stored === "hk" ? "hk" : "us";
}

export function MarketProvider({ children }: { children: React.ReactNode }) {
  const [market, setMarketState] = useState<MarketId>("us");

  // Hydrate from localStorage after mount to avoid SSR mismatch.
  useEffect(() => {
    setMarketState(readInitialMarket());
  }, []);

  const setMarket = (m: MarketId) => {
    setMarketState(m);
    try {
      localStorage.setItem(STORAGE_KEY, m);
    } catch {
      /* ignore persistence failures */
    }
  };

  return (
    <MarketContext.Provider value={{ market, setMarket }}>
      {children}
    </MarketContext.Provider>
  );
}

export function useMarket(): MarketContextValue {
  const ctx = useContext(MarketContext);
  if (!ctx) {
    throw new Error("useMarket must be used within a MarketProvider");
  }
  return ctx;
}
