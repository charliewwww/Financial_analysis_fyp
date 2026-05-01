import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import Link from "next/link";
import { QueryProvider } from "@/lib/query-client";
import { ThemeToggle } from "@/components/ThemeToggle";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "FYP — Market Intelligence",
  description: "AI-powered sector analysis and signal tracking",
};

const NAV_LINKS = [
  { href: "/", label: "Dashboard" },
  { href: "/signals", label: "Morning Brief" },
  { href: "/pipeline", label: "Pipeline" },
  { href: "/supply-chain", label: "Supply Chain" },
  { href: "/reports", label: "Reports" },
  { href: "/accuracy", label: "Accuracy" },
  { href: "/system", label: "System" },
  { href: "/profile", label: "Profile" },
];

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      suppressHydrationWarning
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <head>
        <script
          // Apply persisted theme before paint to avoid FOUC.
          dangerouslySetInnerHTML={{
            __html: `
              try {
                var t = localStorage.getItem('alpha-lens-theme');
                if (!t) t = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
                if (t === 'dark') document.documentElement.classList.add('dark');
              } catch (e) {}
            `,
          }}
        />
      </head>
      <body className="min-h-full flex flex-col bg-background text-foreground">
        <header className="sticky top-0 z-50 border-b border-border bg-background/80 backdrop-blur">
          <nav className="mx-auto flex max-w-7xl items-center gap-6 px-4 py-3">
            <span className="text-sm font-semibold tracking-tight mr-4">
              📈 Market Intelligence
            </span>
            {NAV_LINKS.map(({ href, label }) => (
              <Link
                key={href}
                href={href}
                className="text-sm text-muted-foreground hover:text-foreground transition-colors"
              >
                {label}
              </Link>
            ))}
            <div className="ml-auto">
              <ThemeToggle />
            </div>
          </nav>
        </header>
        <main className="flex-1 mx-auto w-full max-w-7xl px-4 py-6">
          <QueryProvider>{children}</QueryProvider>
        </main>
      </body>
    </html>
  );
}
