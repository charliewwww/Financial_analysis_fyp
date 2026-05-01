"use client";

import type { SignalCard } from "@/types/api";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import Link from "next/link";

const SIGNAL_COLORS: Record<string, string> = {
  BULLISH:
    "bg-emerald-500/10 text-emerald-400 border-emerald-500/30 hover:bg-emerald-500/20",
  BEARISH: "bg-red-500/10 text-red-400 border-red-500/30 hover:bg-red-500/20",
  NEUTRAL:
    "bg-amber-500/10 text-amber-400 border-amber-500/30 hover:bg-amber-500/20",
};

const CONVICTION_DOTS = (n: number | null) =>
  Array.from({ length: 5 }, (_, i) => (
    <span
      key={i}
      className={`inline-block h-2 w-2 rounded-full ${
        i < (n ?? 0) ? "bg-foreground" : "bg-muted"
      }`}
    />
  ));

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

interface SignalCardProps {
  card: SignalCard;
}

export function SignalCardItem({ card }: SignalCardProps) {
  const colorClass = SIGNAL_COLORS[card.signal] ?? SIGNAL_COLORS["NEUTRAL"];

  return (
    <Link href={`/signals/${card.id}`} className="block group">
      <Card className="h-full transition-colors hover:border-foreground/30">
        <CardHeader className="pb-2">
          <div className="flex items-start justify-between gap-2">
            <CardTitle className="text-lg font-bold">{card.ticker}</CardTitle>
            <Badge variant="outline" className={colorClass}>
              {card.signal}
            </Badge>
          </div>
          {card.signal_type && (
            <span className="text-xs text-muted-foreground">
              {card.signal_type}
            </span>
          )}
        </CardHeader>

        <CardContent className="space-y-3">
          {card.one_line && (
            <p className="text-sm leading-relaxed">{card.one_line}</p>
          )}

          <div className="grid grid-cols-2 gap-2 text-xs text-muted-foreground">
            {card.key_catalyst && (
              <div>
                <span className="font-medium text-foreground">Catalyst</span>
                <p className="mt-0.5 line-clamp-2">{card.key_catalyst}</p>
              </div>
            )}
            {card.key_risk && (
              <div>
                <span className="font-medium text-foreground">Risk</span>
                <p className="mt-0.5 line-clamp-2">{card.key_risk}</p>
              </div>
            )}
          </div>

          {card.supply_chain_impact && card.supply_chain_impact.length > 0 && (
            <div className="flex flex-wrap gap-1 pt-1">
              {card.supply_chain_impact.slice(0, 3).map((s) => (
                <Badge
                  key={s.ticker}
                  variant="outline"
                  className="text-xs font-normal"
                >
                  {s.direction} {s.ticker}
                </Badge>
              ))}
            </div>
          )}
        </CardContent>

        <CardFooter className="pt-0 flex items-center justify-between text-xs text-muted-foreground">
          <div className="flex items-center gap-1">
            {CONVICTION_DOTS(card.conviction)}
          </div>
          <div className="flex items-center gap-2">
            {card.confidence != null && (
              <span>{Math.round(card.confidence * 100)}% conf.</span>
            )}
            <span>{formatDate(card.created_at)}</span>
          </div>
        </CardFooter>
      </Card>
    </Link>
  );
}
