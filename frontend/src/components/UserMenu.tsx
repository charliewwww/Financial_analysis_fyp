"use client";

import * as React from "react";
import Link from "next/link";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchMe, logout } from "@/lib/api";
import { isAdminRole } from "@/lib/admin";
import { ThemeToggle } from "@/components/ThemeToggle";

/**
 * UserMenu — top-right cluster: theme toggle + identity dropdown.
 *
 * The dropdown collapses three things into one chip:
 *  • Profile link (always visible)
 *  • Admin Console link (only when allow-listed)
 *  • Sign-out hint (placeholder until NextAuth lands in Block E)
 *
 * If the `/users/me` call fails (dev without Cloudflare Access), we
 * still show the menu but in a "guest" shape so navigation works.
 */
export function UserMenu() {
  const [open, setOpen] = React.useState(false);
  const ref = React.useRef<HTMLDivElement>(null);
  const triggerRef = React.useRef<HTMLButtonElement>(null);

  const { data } = useQuery({
    queryKey: ["users", "me"],
    queryFn: fetchMe,
    retry: false,
    staleTime: 60_000,
  });

  const qc = useQueryClient();

  async function handleSignOut() {
    setOpen(false);
    try {
      await logout();
    } catch {
      // Clear local state and redirect regardless of the network result.
    }
    qc.clear();
    window.location.href = "/login";
  }

  // Close on outside click, and on Escape (restoring focus to the trigger).
  React.useEffect(() => {
    if (!open) return;
    function onDocClick(e: MouseEvent) {
      if (!ref.current?.contains(e.target as Node)) setOpen(false);
    }
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") {
        setOpen(false);
        triggerRef.current?.focus();
      }
    }
    document.addEventListener("mousedown", onDocClick);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onDocClick);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  const email = data?.email ?? null;
  const initial = (data?.username ?? email ?? "?").charAt(0).toUpperCase();
  const admin = isAdminRole(data?.role);

  return (
    <div className="flex items-center gap-2">
      <ThemeToggle />
      <div className="relative" ref={ref}>
        <button
          type="button"
          ref={triggerRef}
          aria-haspopup="menu"
          aria-expanded={open}
          onClick={() => setOpen((v) => !v)}
          className="flex items-center gap-2 rounded-full border border-border bg-background/60 hover:bg-muted/40 transition-colors px-2 py-1"
        >
          <span
            className="inline-flex h-6 w-6 items-center justify-center rounded-full text-xs font-bold text-white"
            style={{
              background:
                "linear-gradient(135deg, var(--al-gold) 0%, var(--al-gold-light) 100%)",
            }}
          >
            {initial}
          </span>
          <span className="text-xs hidden sm:inline" style={{ color: "var(--al-on-surface-muted)" }}>
            {email ?? "guest"}
          </span>
        </button>

        {open && (
          <div
            role="menu"
            className="al-glass absolute right-0 mt-2 w-56 p-1 text-sm z-50"
          >
            <Link
              href="/profile"
              role="menuitem"
              className="block rounded-md px-3 py-2 hover:bg-muted/40"
              onClick={() => setOpen(false)}
            >
              Profile
            </Link>
            {admin && (
              <Link
                href="/admin"
                role="menuitem"
                className="block rounded-md px-3 py-2 hover:bg-muted/40"
                onClick={() => setOpen(false)}
              >
                <span className="al-eyebrow mr-2">admin</span>
                Operator console
              </Link>
            )}
            <div
              className="my-1 border-t"
              style={{ borderColor: "var(--al-outline)" }}
            />
            <button
              type="button"
              role="menuitem"
              onClick={handleSignOut}
              className="block w-full text-left rounded-md px-3 py-2 hover:bg-muted/40"
            >
              Sign out
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
