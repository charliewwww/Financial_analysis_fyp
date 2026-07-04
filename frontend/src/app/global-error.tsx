"use client";

import { useEffect } from "react";

/**
 * Last-resort error boundary for failures in the root layout itself.
 *
 * Next.js renders this *instead of* the root layout, so it must ship its own
 * <html>/<body>. Kept dependency-free and inline-styled on purpose — if the
 * layout crashed, we can't assume fonts, providers or CSS tokens loaded.
 */
export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("Global error boundary caught:", error);
  }, [error]);

  return (
    <html lang="en">
      <body
        style={{
          margin: 0,
          minHeight: "100vh",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontFamily:
            "ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif",
          background: "#0b0e14",
          color: "#e5e7eb",
          padding: "1.5rem",
        }}
      >
        <div style={{ maxWidth: 420, textAlign: "center" }}>
          <h1 style={{ fontSize: "1.25rem", margin: "0 0 0.5rem" }}>MarketPulse hit a snag</h1>
          <p style={{ fontSize: "0.875rem", lineHeight: 1.6, color: "#9ca3af", margin: "0 0 1.25rem" }}>
            Something failed while loading the app shell. Reloading usually fixes it.
          </p>
          <button
            onClick={() => reset()}
            style={{
              cursor: "pointer",
              borderRadius: 9999,
              border: "1px solid #b8860b",
              background: "#b8860b",
              color: "#0b0e14",
              fontWeight: 600,
              padding: "0.55rem 1.25rem",
              fontSize: "0.875rem",
            }}
          >
            Reload MarketPulse
          </button>
          {error.digest ? (
            <p style={{ fontSize: "0.65rem", color: "#6b7280", marginTop: "1rem" }}>
              Reference: {error.digest}
            </p>
          ) : null}
        </div>
      </body>
    </html>
  );
}
