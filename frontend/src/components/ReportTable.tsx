"use client";

import type { ReportSummary } from "@/types/api";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import Link from "next/link";

interface ReportTableProps {
  reports: ReportSummary[];
}

export function ReportTable({ reports }: ReportTableProps) {
  if (reports.length === 0) {
    return (
      <p className="text-sm text-muted-foreground text-center py-10">
        No reports found.
      </p>
    );
  }

  const formatDate = (iso: string) =>
    new Date(iso).toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  const formatConfidence = (score: number) =>
    `${(score <= 1 ? score * 10 : score).toFixed(1)}/10`;

  return (
    <>
      {/* Mobile: stacked cards so the 5 columns never overflow a phone. */}
      <ul className="space-y-3 md:hidden">
        {reports.map((r) => (
          <li key={r.id}>
            <Link
              href={`/reports/${r.id}`}
              className="block rounded-xl border p-4 hover:bg-muted/40"
              style={{ borderColor: "var(--al-outline)" }}
            >
              <div className="flex items-start justify-between gap-3">
                <span className="font-medium">{r.sector_name}</span>
                <span className="text-muted-foreground text-xs whitespace-nowrap">
                  {formatDate(r.created_at)}
                </span>
              </div>
              <dl className="mt-3 grid grid-cols-3 gap-2 text-sm">
                <div>
                  <dt className="text-muted-foreground text-xs">Confidence</dt>
                  <dd>{r.confidence_score != null ? formatConfidence(r.confidence_score) : "—"}</dd>
                </div>
                <div>
                  <dt className="text-muted-foreground text-xs">Validation</dt>
                  <dd>
                    {r.validation_status ? (
                      <Badge variant="outline" className="text-xs capitalize">
                        {r.validation_status}
                      </Badge>
                    ) : (
                      "—"
                    )}
                  </dd>
                </div>
                <div className="text-right">
                  <dt className="text-muted-foreground text-xs">News used</dt>
                  <dd>{r.news_used}</dd>
                </div>
              </dl>
            </Link>
          </li>
        ))}
      </ul>

      {/* Desktop: full table. */}
      <div className="hidden md:block">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Sector</TableHead>
              <TableHead>Date</TableHead>
              <TableHead>Confidence</TableHead>
              <TableHead>Validation</TableHead>
              <TableHead className="text-right">News used</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {reports.map((r) => (
              <TableRow key={r.id} className="cursor-pointer hover:bg-muted/40">
                <TableCell>
                  <Link
                    href={`/reports/${r.id}`}
                    className="font-medium hover:underline"
                  >
                    {r.sector_name}
                  </Link>
                </TableCell>
                <TableCell className="text-muted-foreground text-sm">
                  {formatDate(r.created_at)}
                </TableCell>
                <TableCell>
                  {r.confidence_score != null ? (
                    <span className="text-sm">{formatConfidence(r.confidence_score)}</span>
                  ) : (
                    <span className="text-muted-foreground text-sm">—</span>
                  )}
                </TableCell>
                <TableCell>
                  {r.validation_status ? (
                    <Badge variant="outline" className="text-xs capitalize">
                      {r.validation_status}
                    </Badge>
                  ) : (
                    <span className="text-muted-foreground text-sm">—</span>
                  )}
                </TableCell>
                <TableCell className="text-right text-sm">{r.news_used}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </>
  );
}
