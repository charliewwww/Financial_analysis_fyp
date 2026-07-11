"use client";

import * as React from "react";
import { usePathname, useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";

import { ApiError, fetchMe } from "@/lib/api";
import { Skeleton } from "@/components/ui/skeleton";

/** Route prefixes that never require authentication. */
const PUBLIC_PREFIXES = ["/login", "/signup"];

function isPublicPath(pathname: string | null): boolean {
  if (!pathname) return false;
  return PUBLIC_PREFIXES.some(
    (p) => pathname === p || pathname.startsWith(`${p}/`)
  );
}

function Centered({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-[40vh] items-center justify-center">
      <div className="text-sm" style={{ color: "var(--al-on-surface-muted)" }}>
        {children}
      </div>
    </div>
  );
}

/**
 * A generic page skeleton shown while we verify the session (and on first
 * paint before data arrives). It mimics the common page shape—eyebrow +
 * title + subtitle, a row of metric tiles, and a large content block—so a
 * cold load reads as "content is coming" rather than a blank "Loading…".
 */
function AppSkeleton() {
  return (
    <div className="space-y-6" aria-busy="true" aria-label="Loading…">
      <div className="space-y-3">
        <Skeleton className="h-3.5 w-32" />
        <Skeleton className="h-9 w-2/3 max-w-md" />
        <Skeleton className="h-4 w-full max-w-xl" />
      </div>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Skeleton className="h-20 rounded-2xl" />
        <Skeleton className="h-20 rounded-2xl" />
        <Skeleton className="h-20 rounded-2xl" />
        <Skeleton className="h-20 rounded-2xl" />
      </div>
      <Skeleton className="h-80 w-full rounded-2xl" />
    </div>
  );
}

/**
 * AuthGate — keeps signed-out users out of the app.
 *
 * It reads the current user from `/users/me`. If the server says we're not
 * authenticated (401/403), it sends the browser to `/login`. Public routes
 * (the login page itself) render straight through, so there's no redirect loop.
 *
 * In local development the backend returns a dev identity, so this never blocks
 * you while building.
 */
export function AuthGate({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const isPublic = isPublicPath(pathname);

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["users", "me"],
    queryFn: fetchMe,
    retry: false,
    staleTime: 60_000,
    enabled: !isPublic,
  });

  const unauthenticated =
    isError &&
    error instanceof ApiError &&
    (error.status === 401 || error.status === 403);

  React.useEffect(() => {
    if (!isPublic && unauthenticated) {
      router.replace("/login");
    }
  }, [isPublic, unauthenticated, router]);

  if (isPublic) return <>{children}</>;
  if (isLoading) return <AppSkeleton />;
  if (unauthenticated) return <Centered>Redirecting to sign in…</Centered>;
  if (isError) {
    return (
      <Centered>
        Couldn&apos;t verify your session. Refresh the page to try again.
      </Centered>
    );
  }
  if (!data) return <AppSkeleton />;
  return <>{children}</>;
}
