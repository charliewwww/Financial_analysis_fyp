"""Diagnose RSS feeds — which work, which don't, how many articles."""
import sys
sys.path.insert(0, ".")

from data_sources.rss_fetcher import RSS_FEEDS, _fetch_feed_with_timeout, fetch_news_for_sector
from config.sectors import SECTORS
import time

print("=" * 60)
print("  RSS FEED DIAGNOSIS")
print("=" * 60)

total_articles = 0
for feed_info in RSS_FEEDS:
    start = time.time()
    feed = _fetch_feed_with_timeout(feed_info["url"], feed_info["name"])
    elapsed = time.time() - start

    if feed and feed.entries:
        count = len(feed.entries)
        total_articles += count
        print(f"  ✅ {feed_info['name']:<25} {count:>3} articles  ({elapsed:.1f}s)")
        # Show first article title
        print(f"     → {feed.entries[0].title[:70]}...")
    else:
        print(f"  ❌ {feed_info['name']:<25}   0 articles  ({elapsed:.1f}s)")

print(f"\n  Total raw articles: {total_articles}")

print("\n" + "=" * 60)
print("  SECTOR RELEVANCE CHECK")
print("=" * 60)

for sector_id, sector in SECTORS.items():
    news = fetch_news_for_sector(sector)
    print(f"\n  {sector['name']}: {len(news)} relevant articles")
    for article in news[:5]:
        print(f"    - [{article['relevance']}] {article['title'][:65]}...")

print("\n" + "=" * 60)
print("  STOCK DATA CHECK")
print("=" * 60)

from data_sources.yahoo_finance import get_stock_snapshot

# Test a few tickers and show what data we're actually getting
for ticker in ["NVDA", "RKLB", "LITE"]:
    snap = get_stock_snapshot(ticker)
    if snap.get("error"):
        print(f"\n  ❌ {ticker}: {snap['error']}")
    else:
        print(f"\n  ✅ {ticker}: ${snap['price']}")
        print(f"     1W: {snap.get('change_1w_pct', 'N/A')}% | 1M: {snap.get('change_1m_pct', 'N/A')}%")
        print(f"     MCap: ${snap.get('market_cap', 0)/1e9:.1f}B | P/E: {snap.get('pe_ratio', 'N/A')}")
        print(f"     Vol: {snap.get('volume', 'N/A'):,} | AvgVol: {snap.get('avg_volume', 'N/A'):,}")
        print(f"     Revenue: ${snap.get('revenue_ttm', 0)/1e9:.1f}B | Margin: {snap.get('profit_margin', 'N/A')}")
        print(f"     52W: ${snap.get('52w_low', 'N/A')} - ${snap.get('52w_high', 'N/A')}")
        # Show what's MISSING
        missing = [k for k, v in snap.items() if v is None and k != 'error']
        if missing:
            print(f"     ⚠ Missing fields: {missing}")
