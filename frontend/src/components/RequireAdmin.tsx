"use client";

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { fetchMe } from "@/lib/api";
import { isAdminRole } from "@/lib/admin";
import { Skeleton } from "@/components/ui/skeleton";

/**
 * RequireAdmin — gate component for operator-only surfaces.
 *
 * Behaviour:
 *  • While the current user is being fetched, render a soft skeleton so
 *    we don't flash the protected UI nor a 403 wrongly.
 *  • If `/users/me` fails (e.g. unauthenticated), or the email is not in
 *    the allow-list, render a 403 panel with a back link.
 *  • Otherwise render `children`.
 *
 * This is a defence-in-depth measure: the backend is the real authority
 * and must reject non-admin requests on its own. The component just keeps
 * non-admin users from seeing buttons that wouldn't work anyway.
 */
export function RequireAdmin({ children }: { children: React.ReactNode }) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["users", "me"],
    queryFn: fetchMe,
    retry: false,
    staleTime: 60_000,
  });

  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-32 w-full" />
      </div>
    );
  }

  const role = !isError && data ? data.role : null;
  if (!isAdminRole(role)) {
    return (
      <div className="al-glass max-w-xl mx-auto mt-12 p-8 text-center space-y-3">
        <div className="al-eyebrow">403 — Operator only</div>
        <h1 className="text-2xl">Admin access required</h1>
        <p className="text-sm" style={{ color: "var(--al-on-surface-muted)" }}>
          This surface is reserved for system operators. If you think you
          should have access, contact the workspace administrator.
        </p>
        <div className="pt-2">
          <Link
            href="/"
            className="inline-flex items-center gap-2 al-gold-gradient px-4 py-2 rounded-full text-sm font-semibold"
          >
            ← Back to Today
          </Link>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
