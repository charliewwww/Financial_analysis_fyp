"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Menu, X } from "lucide-react";

const NAV_LINKS = [
  { href: "/", label: "Home" },
  { href: "/tickers", label: "Stocks" },
  { href: "/sectors", label: "Sectors" },
  { href: "/supply-chain", label: "Supply Chain" },
  { href: "/agents", label: "Analysts" },
  { href: "/accuracy", label: "Track Record" },
  { href: "/settings", label: "Settings" },
];

function isActive(pathname: string, href: string): boolean {
  if (href === "/") return pathname === "/";
  return pathname === href || pathname.startsWith(`${href}/`);
}

/**
 * MobileNav — hamburger button + slide-in drawer for narrow viewports.
 *
 * Replaces the previous horizontal-scrolling nav row. Closes on link tap,
 * outside click, route change, and Escape; locks body scroll while open.
 */
export function MobileNav() {
  const pathname = usePathname();
  const [open, setOpen] = React.useState(false);

  // Close whenever the route changes.
  React.useEffect(() => {
    setOpen(false);
  }, [pathname]);

  // Escape to close + lock body scroll while open.
  React.useEffect(() => {
    if (!open) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("keydown", onKey);
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = prevOverflow;
    };
  }, [open]);

  return (
    <div className="md:hidden">
      <button
        type="button"
        aria-label="Open navigation menu"
        aria-expanded={open}
        aria-controls="mobile-nav-drawer"
        onClick={() => setOpen(true)}
        className="inline-flex h-9 w-9 items-center justify-center rounded-full border border-border bg-background/60 hover:bg-muted/40 transition-colors"
      >
        <Menu className="size-5" aria-hidden />
      </button>

      {open && (
        <div className="fixed inset-0 z-50" role="dialog" aria-modal="true" aria-label="Navigation">
          {/* Backdrop */}
          <div
            className="absolute inset-0 bg-black/40 backdrop-blur-sm"
            onClick={() => setOpen(false)}
          />
          {/* Drawer */}
          <nav
            id="mobile-nav-drawer"
            className="absolute right-0 top-0 flex h-full w-72 max-w-[85vw] flex-col gap-1 border-l border-border bg-background p-4 shadow-xl"
          >
            <div className="mb-2 flex items-center justify-between">
              <span className="font-heading font-extrabold tracking-tight text-base">
                MarketPulse
              </span>
              <button
                type="button"
                aria-label="Close navigation menu"
                onClick={() => setOpen(false)}
                className="inline-flex h-9 w-9 items-center justify-center rounded-full border border-border hover:bg-muted/40 transition-colors"
              >
                <X className="size-5" aria-hidden />
              </button>
            </div>
            {NAV_LINKS.map(({ href, label }) => {
              const active = isActive(pathname, href);
              return (
                <Link
                  key={href}
                  href={href}
                  aria-current={active ? "page" : undefined}
                  onClick={() => setOpen(false)}
                  className={
                    active
                      ? "rounded-lg bg-muted px-3 py-2.5 text-sm font-semibold text-foreground"
                      : "rounded-lg px-3 py-2.5 text-sm text-muted-foreground hover:bg-muted/40 hover:text-foreground transition-colors"
                  }
                >
                  {label}
                </Link>
              );
            })}
          </nav>
        </div>
      )}
    </div>
  );
}
