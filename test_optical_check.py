"""Quick check: what articles could match the optical sector?"""
from data_sources.rss_fetcher import _fetch_all_articles

articles = _fetch_all_articles()
print(f"Total articles from RSS: {len(articles)}")

optical_tickers = ["LITE", "COHR", "CIENA", "INFN", "CIEN", "ANET", "KEYS"]
broad_keywords = ["fiber", "optical", "networking", "arista", "ciena", "lumentum",
                   "data center", "coherent", "transceiver", "photon", "bandwidth"]

matches = []
for article in articles:
    text = (article["title"] + " " + article["summary"]).lower()
    
    for t in optical_tickers:
        if t.lower() in text:
            matches.append(f"  TICKER [{t}]: {article['title'][:80]}")
    
    for kw in broad_keywords:
        if kw in text:
            matches.append(f"  KW [{kw}]: {article['title'][:80]}")
            break

if matches:
    print("\nPotential matches:")
    for m in matches:
        print(m)
else:
    print("\nNo articles match optical sector at all — this sector needs specialized feeds.")
