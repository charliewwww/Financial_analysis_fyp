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

  return (
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
              {new Date(r.created_at).toLocaleDateString("en-US", {
                month: "short",
                day: "numeric",
                year: "numeric",
              })}
            </TableCell>
            <TableCell>
              {r.confidence_score != null ? (
                <span className="text-sm">
                  {Math.round(r.confidence_score * 100)}%
                </span>
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
  );
}
