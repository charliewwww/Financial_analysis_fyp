import type { Metadata } from "next";
import { Manrope, Inter } from "next/font/google";
import { QueryProvider } from "@/lib/query-client";
import { MarketProvider } from "@/lib/market-context";
import { OvernightProvider } from "@/components/overnight/OvernightContext";
import { AppChrome } from "@/components/AppChrome";
import "./globals.css";

const manrope = Manrope({
  variable: "--font-manrope",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700", "800"],
  display: "swap",
});

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  display: "swap",
});

export const metadata: Metadata = {
  title: {
    default: "MarketPulse",
    template: "%s · MarketPulse",
  },
  description: "Four AI analysts, one ticker, one screen.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      suppressHydrationWarning
      className={`${manrope.variable} ${inter.variable} h-full antialiased`}
    >
      <head>
        <script
          // Apply persisted theme before paint to avoid FOUC.
          dangerouslySetInnerHTML={{
            __html: `
              try {
                var t = localStorage.getItem('marketpulse-theme') || localStorage.getItem('alpha-lens-theme');
                if (!t) t = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
                if (t === 'dark') document.documentElement.classList.add('dark');
              } catch (e) {}
            `,
          }}
        />
      </head>
      <body className="min-h-full bg-background text-foreground">
        <QueryProvider>
          <MarketProvider>
          <OvernightProvider>
            <AppChrome>{children}</AppChrome>
          </OvernightProvider>
          </MarketProvider>
        </QueryProvider>
      </body>
    </html>
  );
}
