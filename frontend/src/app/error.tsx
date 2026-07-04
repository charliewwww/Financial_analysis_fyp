"use client";

import { useEffect } from "react";
import Link from "next/link";
import { AlertTriangle, Home, RotateCw } from "lucide-react";
import { Button } from "@/components/ui/button";

/**
 * Route-segment error boundary.
 *
 * Catches render/runtime errors inside any page so a single broken component
 * never white-screens the whole app. The header, nav and footer from the root
 * layout stay in place — the user can recover with one click.
 */
export default function RouteError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // Surface to the console for debugging; wire to a real reporter (Sentry, etc.) later.
    console.error("Route error boundary caught:", error);
  }, [error]);

  return (
    <div className="flex min-h-[60vh] items-center justify-center">
      <div className="al-glass flex max-w-md flex-col items-center gap-4 p-8 text-center">
        <AlertTriangle className="size-7 text-destructive" aria-hidden />
        <div className="space-y-1.5">
          <h1 className="text-lg font-semibold">This view ran into a problem</h1>
          <p className="text-sm leading-6" style={{ color: "var(--al-on-surface-muted)" }}>
            The rest of the app is still fine. You can retry this screen, or head back to the
            dashboard.
          </p>
        </div>
        <div className="flex flex-wrap items-center justify-center gap-2">
          <Button className="al-gold-gradient rounded-full px-5" onClick={() => reset()}>
            <RotateCw data-icon="inline-start" className="size-4" aria-hidden />
            Try again
          </Button>
          <Link href="/">
            <Button variant="outline" className="rounded-full px-5">
              <Home data-icon="inline-start" className="size-4" aria-hidden />
              Go to dashboard
            </Button>
          </Link>
        </div>
        {error.digest ? (
          <p className="text-[0.65rem] tabular-nums" style={{ color: "var(--al-on-surface-muted)" }}>
            Reference: {error.digest}
          </p>
        ) : null}
      </div>
    </div>
  );
}
