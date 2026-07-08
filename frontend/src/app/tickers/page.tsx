import { TickerBoard } from "@/components/TickerBoard";

export const metadata = { title: "Decision Desk — MarketPulse" };

export default async function TickersPage({
  searchParams,
}: {
  searchParams: Promise<{ ticker?: string | string[] }>;
}) {
  const params = await searchParams;
  const raw = Array.isArray(params.ticker) ? params.ticker[0] : params.ticker;
  return <TickerBoard initialTicker={raw} />;
}
