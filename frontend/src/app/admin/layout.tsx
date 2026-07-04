"use client";

import { RequireAdmin } from "@/components/RequireAdmin";

/**
 * /admin/* layout — gates every nested route through the operator allow-list.
 *
 * Nested pages may still be Server Components; Next.js permits Client
 * layouts to wrap Server children because `children` is passed as a prop.
 */
export default function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <RequireAdmin>{children}</RequireAdmin>;
}
