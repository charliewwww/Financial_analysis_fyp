"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

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

function linkClass(active: boolean, mobile = false): string {
  const base = mobile
    ? "text-xs whitespace-nowrap rounded-full px-3 py-1 transition-colors"
    : "text-sm rounded-full px-3 py-1.5 transition-colors";
  return active
    ? `${base} bg-muted text-foreground shadow-sm`
    : `${base} text-muted-foreground hover:bg-muted/40 hover:text-foreground`;
}

export function AppNav({ mobile = false }: { mobile?: boolean }) {
  const pathname = usePathname();

  return (
    <>
      {NAV_LINKS.map(({ href, label }) => {
        const active = isActive(pathname, href);
        return (
          <Link
            key={href}
            href={href}
            aria-current={active ? "page" : undefined}
            className={linkClass(active, mobile)}
          >
            {label}
          </Link>
        );
      })}
    </>
  );
}