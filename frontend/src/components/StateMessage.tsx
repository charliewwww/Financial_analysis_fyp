"use client";

import * as React from "react";
import { AlertTriangle, Inbox, RotateCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

/**
 * Shared empty/error state primitives (Tier 4.1).
 *
 * Gives every data view a consistent look for "nothing here yet" and
 * "something broke", with an optional retry action and standard tokens
 * instead of ad-hoc `text-red-400`/`text-red-500` strings.
 */

export interface ErrorStateProps {
  /** Short, human title. */
  title?: string;
  /** Optional detail line (e.g. the error message). */
  detail?: string;
  /** When provided, renders a "Try again" button. */
  onRetry?: () => void;
  className?: string;
}

export function ErrorState({
  title = "Something went wrong",
  detail,
  onRetry,
  className,
}: ErrorStateProps) {
  return (
    <div
      role="alert"
      className={cn(
        "al-glass flex flex-col items-center gap-3 p-8 text-center",
        className,
      )}
    >
      <AlertTriangle className="size-6 text-destructive" aria-hidden />
      <div>
        <p className="text-sm font-semibold text-destructive">{title}</p>
        {detail ? (
          <p className="mt-1 text-xs" style={{ color: "var(--al-on-surface-muted)" }}>
            {detail}
          </p>
        ) : null}
      </div>
      {onRetry ? (
        <Button variant="outline" className="rounded-full" onClick={onRetry}>
          <RotateCw data-icon="inline-start" className="size-4" aria-hidden />
          Try again
        </Button>
      ) : null}
    </div>
  );
}

export interface EmptyStateProps {
  title: string;
  detail?: string;
  /** Optional call-to-action node (e.g. a Link/Button). */
  action?: React.ReactNode;
  className?: string;
}

export function EmptyState({ title, detail, action, className }: EmptyStateProps) {
  return (
    <div
      role="status"
      className={cn(
        "al-glass flex flex-col items-center gap-3 p-8 text-center",
        className,
      )}
    >
      <Inbox className="size-6" aria-hidden style={{ color: "var(--al-on-surface-muted)" }} />
      <div>
        <p className="text-sm font-semibold">{title}</p>
        {detail ? (
          <p className="mt-1 text-xs leading-5" style={{ color: "var(--al-on-surface-muted)" }}>
            {detail}
          </p>
        ) : null}
      </div>
      {action}
    </div>
  );
}
