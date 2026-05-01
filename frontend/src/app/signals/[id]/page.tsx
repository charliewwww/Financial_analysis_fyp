"use client";

import { useQuery } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { fetchSignalCard, fetchSignalPredictions } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Separator } from "@/components/ui/separator";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

const SIGNAL_COLORS: Record<string, string> = {
  BULLISH: "bg-emerald-500/10 text-emerald-400 border-emerald-500/30",
  BEARISH: "bg-red-500/10 text-red-400 border-red-500/30",
  NEUTRAL: "bg-amber-500/10 text-amber-400 border-amber-500/30",
};

export default function SignalDetailPage() {
  const { id } = useParams<{ id: string }>();
  const cardId = Number(id);

  const { data: card, isLoading, isError } = useQuery({
    queryKey: ["signal", cardId],
    queryFn: () => fetchSignalCard(cardId),
    enabled: !isNaN(cardId),
  });

  const { data: predictions } = useQuery({
    queryKey: ["signal-predictions", cardId],
    queryFn: () => fetchSignalPredictions(cardId),
    enabled: !isNaN(cardId),
  });

  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-40" />
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-24 w-full" />
      </div>
    );
  }

  if (isError || !card) {
    return (
      <p className="text-sm text-red-400">Signal card not found.</p>
    );
  }

  const colorClass = SIGNAL_COLORS[card.signal] ?? SIGNAL_COLORS["NEUTRAL"];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <h1 className="text-3xl font-bold">{card.ticker}</h1>
        <Badge variant="outline" className={colorClass}>
          {card.signal}
        </Badge>
        {card.signal_type && (
          <span className="text-sm text-muted-foreground">{card.signal_type}</span>
        )}
      </div>

      {card.one_line && (
        <p className="text-base leading-relaxed">{card.one_line}</p>
      )}

      <div className="grid gap-4 sm:grid-cols-2">
        {card.key_catalyst && (
          <Card>
            <CardHeader className="pb-2"><CardTitle className="text-sm">Key Catalyst</CardTitle></CardHeader>
            <CardContent className="text-sm">{card.key_catalyst}</CardContent>
          </Card>
        )}
        {card.key_risk && (
          <Card>
            <CardHeader className="pb-2"><CardTitle className="text-sm">Key Risk</CardTitle></CardHeader>
            <CardContent className="text-sm">{card.key_risk}</CardContent>
          </Card>
        )}
      </div>

      {/* Metrics */}
      <div className="flex flex-wrap gap-6 text-sm">
        {card.conviction != null && (
          <div>
            <span className="text-muted-foreground">Conviction </span>
            <span className="font-semibold">{card.conviction}/5</span>
          </div>
        )}
        {card.confidence != null && (
          <div>
            <span className="text-muted-foreground">Confidence </span>
            <span className="font-semibold">{Math.round(card.confidence * 100)}%</span>
          </div>
        )}
        {card.validation_score && (
          <div>
            <span className="text-muted-foreground">Validation score </span>
            <span className="font-semibold">{card.validation_score}</span>
          </div>
        )}
      </div>

      <Separator />

      {/* Numerical claims */}
      {card.numerical_claims && card.numerical_claims.length > 0 && (
        <Card>
          <CardHeader><CardTitle className="text-sm">Numerical Claims</CardTitle></CardHeader>
          <CardContent>
            <ul className="space-y-2">
              {card.numerical_claims.map((c, i) => (
                <li key={i} className="flex items-start gap-2 text-sm">
                  <span className={c.verified ? "text-emerald-400" : "text-red-400"}>
                    {c.verified ? "✓" : "✗"}
                  </span>
                  <span>{c.claim}</span>
                  {c.source && <span className="text-muted-foreground">({c.source})</span>}
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      {/* Supply chain */}
      {card.supply_chain_impact && card.supply_chain_impact.length > 0 && (
        <Card>
          <CardHeader><CardTitle className="text-sm">Supply Chain Impact</CardTitle></CardHeader>
          <CardContent className="space-y-2">
            {card.supply_chain_impact.map((s) => (
              <div key={s.ticker} className="flex items-start gap-2 text-sm">
                <span className="font-semibold w-6 text-center">{s.direction}</span>
                <span className="font-medium w-16">{s.ticker}</span>
                <span className="text-muted-foreground">{s.reason}</span>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {/* Sources */}
      {card.sources && card.sources.length > 0 && (
        <Card>
          <CardHeader><CardTitle className="text-sm">Sources</CardTitle></CardHeader>
          <CardContent className="space-y-1">
            {card.sources.map((s, i) => (
              <div key={i} className="text-sm">
                <a
                  href={s.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-blue-400 hover:underline"
                >
                  {s.title || s.domain}
                </a>
                {s.domain && <span className="text-muted-foreground ml-2">({s.domain})</span>}
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {/* Predictions */}
      {predictions && predictions.length > 0 && (
        <Card>
          <CardHeader><CardTitle className="text-sm">Predictions</CardTitle></CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Ticker</TableHead>
                  <TableHead>Direction</TableHead>
                  <TableHead>Price at report</TableHead>
                  <TableHead>Price 1w later</TableHead>
                  <TableHead>Correct</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {predictions.map((p) => (
                  <TableRow key={p.id}>
                    <TableCell className="font-medium">{p.ticker}</TableCell>
                    <TableCell>{p.ai_direction ?? "—"}</TableCell>
                    <TableCell>{p.price_at_report?.toFixed(2) ?? "—"}</TableCell>
                    <TableCell>{p.price_1w_later?.toFixed(2) ?? "—"}</TableCell>
                    <TableCell>
                      {p.prediction_correct == null ? (
                        <span className="text-muted-foreground">pending</span>
                      ) : p.prediction_correct ? (
                        <span className="text-emerald-400">✓</span>
                      ) : (
                        <span className="text-red-400">✗</span>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
