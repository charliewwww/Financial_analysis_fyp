"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { AppNav } from "@/components/AppNav";
import { MobileNav } from "@/components/MobileNav";
import { MarketToggle } from "@/components/MarketToggle";
import { FloatingEvidenceChat } from "@/components/FloatingEvidenceChat";
import { UserMenu } from "@/components/UserMenu";
import { BrandMark } from "@/components/BrandMark";
import { RunProgressDock } from "@/components/RunProgressDock";
import { OvernightDock } from "@/components/overnight/OvernightDock";
import { AuthGate } from "@/components/AuthGate";

/**
 * Routes that render WITHOUT the app chrome (nav, user menu, docks, footer).
 * The login screen must look signed-out — no header showing an account and no
 * floating run docks bleeding through.
 */
const BARE_ROUTES = ["/login"];

function isBareRoute(pathname: string | null): boolean {
  if (!pathname) return false;
  return BARE_ROUTES.some((p) => pathname === p || pathname.startsWith(`${p}/`));
}

/**
 * AppChrome — the persistent shell around every page.
 *
 * On normal routes it renders the header, navigation, footer disclaimer, and
 * the floating docks, and gates the content behind AuthGate. On bare routes
 * (e.g. /login) it renders the page on its own so a signed-out user never sees
 * account chrome or active-run docks.
 */
export function AppChrome({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  if (isBareRoute(pathname)) {
    return <div className="flex min-h-full flex-col">{children}</div>;
  }

  return (
    <div className="flex min-h-full flex-col">
      <header className="sticky top-0 z-40 border-b border-border bg-background/80 backdrop-blur">
        <nav className="mx-auto flex max-w-7xl items-center gap-6 px-4 py-3">
          <Link
            href="/"
            className="flex items-center gap-2 mr-4"
            aria-label="MarketPulse — Today"
          >
            <BrandMark size={24} aria-hidden />
            <span className="font-heading font-extrabold tracking-tight text-base">
              MarketPulse
            </span>
          </Link>

          <div className="hidden md:flex items-center gap-1">
            <AppNav />
          </div>

          <div className="ml-auto flex items-center gap-2">
            <MarketToggle />
            <UserMenu />
            <MobileNav />
          </div>
        </nav>
      </header>
      <main className="flex-1 mx-auto w-full max-w-7xl px-4 py-6">
        <AuthGate>{children}</AuthGate>
      </main>
      <footer className="border-t border-border">
        <div
          className="mx-auto w-full max-w-7xl px-4 py-5 text-xs leading-5"
          style={{ color: "var(--al-on-surface-muted)" }}
        >
          <p>
            <strong>Not financial advice.</strong> MarketPulse is a research and
            educational tool. Signals are AI-generated from public data and may be
            incomplete, delayed, or wrong. Nothing here is a recommendation to buy or
            sell any security. Always do your own research and consult a licensed
            financial advisor before making investment decisions.
          </p>
        </div>
      </footer>
      <FloatingEvidenceChat />
      <RunProgressDock />
      <OvernightDock />
    </div>
  );
}
