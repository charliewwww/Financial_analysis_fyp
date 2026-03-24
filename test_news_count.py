from data_sources.rss_fetcher import fetch_news_for_sector
from config.sectors import SECTORS
for sid, sector in SECTORS.items():
    news = fetch_news_for_sector(sector)
    print(f"{sector['name']}: {len(news)} articles")
