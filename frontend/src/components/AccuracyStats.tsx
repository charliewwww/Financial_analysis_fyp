"use client";

import type { AccuracyStats } from "@/types/api";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

interface AccuracyStatsDisplayProps {
  stats: AccuracyStats;
}

function StatBlock({
  label,
  value,
  sub,
}: {
  label: string;
  value: string | number;
  sub?: string;
}) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-2xl font-bold tabular-nums">{value}</span>
      <span className="text-xs text-muted-foreground">{label}</span>
      {sub && <span className="text-xs text-muted-foreground">{sub}</span>}
    </div>
  );
}

export function AccuracyStatsDisplay({ stats }: AccuracyStatsDisplayProps) {
  const byType = Object.entries(stats.by_signal_type);

  return (
    <div className="space-y-6">
      {/* Top-level numbers */}
      <Card>
        <CardHeader>
          <CardTitle>Overall Accuracy</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 gap-6 sm:grid-cols-4">
            <StatBlock label="Total predictions" value={stats.total} />
            <StatBlock
              label="Direction accuracy"
              value={stats.direction_accuracy_pct != null ? `${stats.direction_accuracy_pct.toFixed(1)}%` : "—"}
              sub={`${stats.direction_correct}/${stats.checked} checked`}
            />
            <StatBlock
              label="Avg absolute error"
              value={stats.avg_absolute_error_pct != null ? `${stats.avg_absolute_error_pct.toFixed(2)}%` : "—"}
            />
            <StatBlock
              label="Unchecked"
              value={stats.unchecked}
              sub="awaiting price data"
            />
          </div>
        </CardContent>
      </Card>

      {/* Per signal type */}
      {byType.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>By Signal Type</CardTitle>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Signal type</TableHead>
                  <TableHead className="text-right">Total</TableHead>
                  <TableHead className="text-right">Correct</TableHead>
                  <TableHead className="text-right">Accuracy</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {byType.map(([type, breakdown]) => (
                  <TableRow key={type}>
                    <TableCell className="capitalize">{type}</TableCell>
                    <TableCell className="text-right">{breakdown.total}</TableCell>
                    <TableCell className="text-right">{breakdown.correct}</TableCell>
                    <TableCell className="text-right font-medium">
                      {breakdown.accuracy_pct.toFixed(1)}%
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
