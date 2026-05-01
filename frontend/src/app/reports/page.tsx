"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchReports } from "@/lib/api";
import { ReportTable } from "@/components/ReportTable";
import { Skeleton } from "@/components/ui/skeleton";

export default function ReportsPage() {
  const [sectorId, setSectorId] = useState("");
  const [page, setPage] = useState(1);
  const PAGE_SIZE = 20;

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["reports", { sectorId, page }],
    queryFn: () =>
      fetchReports({
        sector_id: sectorId || undefined,
        page,
        page_size: PAGE_SIZE,
      }),
  });

  const totalPages = data ? Math.ceil(data.total / PAGE_SIZE) : 1;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Reports</h1>
        <p className="text-sm text-muted-foreground">
          Historical sector analysis reports
        </p>
      </div>

      <input
        value={sectorId}
        onChange={(e) => {
          setSectorId(e.target.value);
          setPage(1);
        }}
        placeholder="Filter by sector ID…"
        className="w-52 rounded-md border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
      />

      {isError && (
        <p className="text-sm text-red-400">Failed to load: {String(error)}</p>
      )}

      {isLoading ? (
        <div className="space-y-2">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-10 w-full" />
          ))}
        </div>
      ) : (
        <ReportTable reports={data?.items ?? []} />
      )}

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
