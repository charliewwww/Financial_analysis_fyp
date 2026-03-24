"""Quick smoke test — run this to verify all data sources work."""

import sys
sys.path.insert(0, ".")

print("=" * 50)
print("  SMOKE TEST — Data Sources")
print("=" * 50)

# Test 1: Yahoo Finance
print("\n🧪 Test 1: Yahoo Finance")
try:
    from data_sources.yahoo_finance import get_stock_snapshot
    result = get_stock_snapshot("NVDA")
    if result.get("error"):
        print(f"   ⚠ Error: {result['error']}")
    else:
        print(f"   ✅ NVDA: ${result['price']} | 1W: {result.get('change_1w_pct', 'N/A')}%")
        print(f"      MCap: ${result.get('market_cap', 0)/1e9:.0f}B | P/E: {result.get('pe_ratio', 'N/A')}")
except Exception as e:
    print(f"   ❌ Failed: {e}")

# Test 2: RSS News
print("\n🧪 Test 2: RSS News Feeds")
try:
    from data_sources.rss_fetcher import fetch_all_news
    news = fetch_all_news()
    print(f"   ✅ Fetched {len(news)} articles from RSS feeds")
    if news:
        print(f"      Latest: [{news[0]['source']}] {news[0]['title'][:80]}...")
except Exception as e:
    print(f"   ❌ Failed: {e}")

# Test 3: Sector-filtered news
print("\n🧪 Test 3: Sector-Filtered News (AI/Semis)")
try:
    from data_sources.rss_fetcher import fetch_news_for_sector
    from config.sectors import SECTORS
    sector = SECTORS["ai_semiconductors"]
    news = fetch_news_for_sector(sector)
    print(f"   ✅ Found {len(news)} relevant articles for AI/Semis")
    for article in news[:3]:
        print(f"      - {article['title'][:70]}... ({article['relevance']})")
except Exception as e:
    print(f"   ❌ Failed: {e}")

# Test 4: OpenRouter LLM
print("\n🧪 Test 4: OpenRouter LLM Connection")
try:
    from agents.llm_client import call_llm_fast
    response = call_llm_fast("Say 'Hello, Supply Chain Alpha is online!' in exactly those words.")
    if "ERROR" in response:
        print(f"   ⚠ LLM Error: {response}")
        print("   → Make sure OPENROUTER_API_KEY is set in .env")
    else:
        print(f"   ✅ LLM Response: {response[:100]}")
except Exception as e:
    print(f"   ❌ Failed: {e}")

# Test 5: Database
print("\n🧪 Test 5: SQLite Database")
try:
    from database.reports_db import _get_conn
    conn = _get_conn()
    tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    print(f"   ✅ Database ready — tables: {[t['name'] for t in tables]}")
    conn.close()
except Exception as e:
    print(f"   ❌ Failed: {e}")

print("\n" + "=" * 50)
print("  Smoke test complete!")
print("=" * 50)
