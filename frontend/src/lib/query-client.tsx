"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ReactQueryDevtools } from "@tanstack/react-query-devtools";
import { useState } from "react";

import { ApiError } from "@/lib/api";

export function QueryProvider({ children }: { children: React.ReactNode }) {
  const showDevtools =
    process.env.NODE_ENV === "development" &&
    process.env.NEXT_PUBLIC_QUERY_DEVTOOLS === "true";

  // One QueryClient per browser session — useState prevents recreation on render
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 30_000, // 30 s
            // Don't hammer the server on "real" failures (404/401/422); those won't
            // fix themselves. Retry only transient network/timeout/5xx errors a couple
            // of times with a backoff so a brief hiccup recovers silently.
            retry: (failureCount, error) => {
              if (error instanceof ApiError) {
                const transient = error.status === 0 || error.status >= 500;
                return transient && failureCount < 2;
              }
              return failureCount < 1;
            },
            retryDelay: (attempt) => Math.min(1000 * 2 ** attempt, 8000),
          },
        },
      })
  );

  return (
    <QueryClientProvider client={client}>
      {children}
      {showDevtools ? <ReactQueryDevtools initialIsOpen={false} /> : null}
    </QueryClientProvider>
  );
}
