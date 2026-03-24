"""
RSS News Fetcher — pulls financial news from free RSS feeds.

Covers: CNBC, Reuters, MarketWatch, Yahoo Finance, and more.
Returns clean article dicts with title, summary, source, date, and link.

Performance note: Each feed has a 8-second timeout. Unreachable feeds
are skipped gracefully. Total fetch time should be ~5-15s, not 40+.
"""

import feedparser
import logging
import re
import requests
from datetime import datetime, timedelta, timezone
from config.settings import MAX_ARTICLES_PER_FEED, NEWS_MAX_AGE_DAYS

logger = logging.getLogger(__name__)

# Timeout per feed in seconds — if a feed doesn't respond in this time, skip it
FEED_TIMEOUT = 8


# ── Feed definitions ──────────────────────────────────────────────
# Prioritized by reliability. Dead/flaky feeds removed.
RSS_FEEDS = [
    {
        "name": "CNBC Top News",
        "url": "https://www.cnbc.com/id/100003114/device/rss/rss.html",
    },
    {
        "name": "CNBC Business",
        "url": "https://www.cnbc.com/id/10001147/device/rss/rss.html",
    },
    {
        "name": "Yahoo Finance",
        "url": "https://finance.yahoo.com/news/rssindex",
    },
    {
        "name": "MarketWatch",
        "url": "https://feeds.marketwatch.com/marketwatch/topstories/",
    },
    {
        "name": "Seeking Alpha",
        "url": "https://seekingalpha.com/market_currents.xml",
    },
    {
        "name": "Nasdaq Markets",
        "url": "https://www.nasdaq.com/feed/rssoutbound?category=Markets",
    },
    {
        "name": "Nasdaq Earnings",
        "url": "https://www.nasdaq.com/feed/rssoutbound?category=Earnings",
    },
    {
        "name": "Investing.com",
        "url": "https://www.investing.com/rss/news.rss",
    },
]


def fetch_news_for_sector(sector: dict) -> list[dict]:
    """
    Fetch recent news articles relevant to a sector.

    Strategy:
    1. Scan all general RSS feeds for keyword/ticker matches
    2. ALWAYS fetch Google News per-ticker for EVERY ticker to ensure
       each stock has its own dedicated news coverage
    3. Track per-ticker article counts in metadata

    Returns:
        List of article dicts sorted by date (newest first)
    """
    MIN_ARTICLES = 10  # Minimum articles before we consider coverage sufficient
    MIN_PER_TICKER = 2  # Each ticker should have at least this many articles

    keywords = [kw.lower() for kw in sector.get("keywords", [])]
    tickers = [t.upper() for t in sector.get("tickers", [])]
    cutoff = datetime.now(timezone.utc) - timedelta(days=NEWS_MAX_AGE_DAYS)

    all_articles = []

    # ── Pass 1: General RSS feeds ─────────────────────────────────
    for feed_info in RSS_FEEDS:
        try:
            feed = _fetch_feed_with_timeout(feed_info["url"], feed_info["name"])
            if not feed:
                continue
            for entry in feed.entries[:MAX_ARTICLES_PER_FEED]:
                article = _parse_entry(entry, feed_info["name"])
                if article and _is_relevant(article, keywords, tickers):
                    all_articles.append(article)
        except Exception as e:
            # Don't crash if one feed is down — just skip it
            logger.warning("Failed to fetch %s: %s", feed_info['name'], e)

    # ── Pass 2: Per-ticker Google News (ALWAYS runs for every ticker)
    # This ensures every stock has its own fetched news, even niche ones
    # that general feeds rarely mention (LITE, COHR, RDW, etc.)
    logger.info("Fetching per-ticker Google News for %d tickers...", len(tickers))
    ticker_coverage = _count_per_ticker(all_articles, tickers)
    for ticker in tickers:
        existing_count = ticker_coverage.get(ticker, 0)
        if existing_count >= MIN_PER_TICKER:
            logger.debug("%s already has %d articles — skipping Google News", ticker, existing_count)
            continue
        needed = MIN_PER_TICKER - existing_count
        google_articles = _fetch_google_news_for_ticker(ticker)
        all_articles.extend(google_articles[:max(needed, 3)])
        if google_articles:
            logger.info("%s: +%d articles from Google News (had %d from general feeds)",
                        ticker, len(google_articles[:max(needed, 3)]), existing_count)

    # Log final per-ticker coverage
    final_coverage = _count_per_ticker(all_articles, tickers)
    uncovered = [t for t in tickers if final_coverage.get(t, 0) == 0]
    if uncovered:
        logger.warning("Tickers with ZERO articles: %s", uncovered)
    logger.info("Per-ticker coverage: %s", {t: final_coverage.get(t, 0) for t in tickers})

    # Filter out stale articles older than NEWS_MAX_AGE_DAYS
    filtered = []
    for a in all_articles:
        pub = a.get("published", "unknown")
        if pub != "unknown":
            try:
                pub_dt = datetime.fromisoformat(pub)
                # Ensure timezone-aware (some feeds omit tz info)
                if pub_dt.tzinfo is None:
                    pub_dt = pub_dt.replace(tzinfo=timezone.utc)
                if pub_dt < cutoff:
                    continue  # too old
            except (ValueError, TypeError):
                pass  # keep articles with unparseable dates
        filtered.append(a)

    # Sort by date (newest first), deduplicate by title
    filtered = _deduplicate(filtered)
    filtered.sort(key=lambda a: a["published"], reverse=True)

    return filtered


def fetch_all_news() -> list[dict]:
    """Fetch ALL recent news from all feeds (unfiltered). Useful for broad scanning."""
    all_articles = []
    for feed_info in RSS_FEEDS:
        try:
            feed = _fetch_feed_with_timeout(feed_info["url"], feed_info["name"])
            if not feed:
                continue
            for entry in feed.entries[:MAX_ARTICLES_PER_FEED]:
                article = _parse_entry(entry, feed_info["name"])
                if article:
                    all_articles.append(article)
        except Exception as e:
            logger.warning("Failed to fetch %s: %s", feed_info['name'], e)

    all_articles = _deduplicate(all_articles)
    all_articles.sort(key=lambda a: a["published"], reverse=True)
    return all_articles


def _fetch_feed_with_timeout(url: str, name: str):
    """
    Fetch an RSS feed with a hard timeout and automatic retry.

    Uses resilient_get() for exponential-backoff retry on transient
    failures, then parses the XML with feedparser.
    """
    from utils.http_retry import resilient_get

    try:
        response = resilient_get(
            url,
            timeout=FEED_TIMEOUT,
            max_retries=2,
            backoff_base=1.0,
            headers={"User-Agent": "SupplyChainAlpha/1.0 (Financial Analysis Tool)"},
            label=name,
        )
        response.raise_for_status()
        feed = feedparser.parse(response.content)
        return feed
    except Exception as e:
        logger.warning("%s: %s — skipping", name, e)
        return None


def _parse_entry(entry, source_name: str) -> dict | None:
    """Convert a feedparser entry into a clean article dict."""
    title = getattr(entry, "title", "").strip()
    if not title:
        return None

    # Get summary/description
    summary = ""
    if hasattr(entry, "summary"):
        summary = entry.summary
    elif hasattr(entry, "description"):
        summary = entry.description

    # Strip HTML tags from summary (simple approach)
    from bs4 import BeautifulSoup
    summary = BeautifulSoup(summary, "html.parser").get_text()[:500].strip()

    # Parse date
    published = "unknown"
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        try:
            dt = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
            published = dt.isoformat()
        except Exception:
            pass

    link = getattr(entry, "link", "")

    return {
        "title": title,
        "summary": summary,
        "source": source_name,
        "published": published,
        "link": link,
        "relevance": "",  # filled in by _is_relevant
    }


def _is_relevant(article: dict, keywords: list[str], tickers: list[str]) -> bool:
    """
    Check if an article is relevant to the sector based on keywords/tickers.

    Uses a scoring system instead of single-keyword match to reduce false positives.
    An article needs either:
    - A direct ticker mention, OR
    - At least 2 keyword matches (prevents 'launch' alone from matching rockets)
    """
    text = (article["title"] + " " + article["summary"]).lower()

    # Check tickers (case-insensitive, word boundary check)
    for ticker in tickers:
        tk = ticker.lower()
        # Use regex word boundary to match all delimiter contexts:
        # " NVDA ", "$NVDA", "(NVDA)", "NVDA-related", "NVDA," etc.
        if re.search(rf'(?<![a-z]){re.escape(tk)}(?![a-z])', text):
            article["relevance"] = f"ticker:{ticker}"
            return True

    # Check keywords — require at least 2 matches to reduce false positives
    matched_keywords = []
    for kw in keywords:
        if kw in text:
            matched_keywords.append(kw)

    if len(matched_keywords) >= 2:
        article["relevance"] = f"keywords:{'+'.join(matched_keywords[:3])}"
        return True

    # Single keyword match only if it's a strong/specific keyword (3+ words)
    for kw in matched_keywords:
        if len(kw.split()) >= 2:  # Multi-word keywords are specific enough alone
            article["relevance"] = f"keyword:{kw}"
            return True

    return False


def _count_per_ticker(articles: list[dict], tickers: list[str]) -> dict[str, int]:
    """Count how many articles mention each ticker (in title, summary, or relevance tag)."""
    counts: dict[str, int] = {t: 0 for t in tickers}
    for article in articles:
        text = (article.get("title", "") + " " + article.get("summary", "")
                + " " + article.get("relevance", "")).upper()
        for ticker in tickers:
            if ticker in text:
                counts[ticker] += 1
    return counts


def _deduplicate(articles: list[dict]) -> list[dict]:
    """Remove duplicate articles by title (keep first occurrence)."""
    seen = set()
    unique = []
    for article in articles:
        key = article["title"].lower().strip()
        if key not in seen:
            seen.add(key)
            unique.append(article)
    return unique


def _fetch_google_news_for_ticker(ticker: str) -> list[dict]:
    """
    Fallback: fetch news for a specific ticker via Google News RSS.

    Google News provides RSS feeds for any search query. This ensures
    even niche tickers (LITE, COHR, CIENA) get news coverage when
    general financial feeds don't mention them.
    """
    from urllib.parse import quote
    query = quote(f"{ticker} stock")
    url = f"https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"

    try:
        feed = _fetch_feed_with_timeout(url, f"Google News ({ticker})")
        if not feed:
            return []

        articles = []
        for entry in feed.entries[:5]:  # Cap at 5 per ticker
            article = _parse_entry(entry, f"Google News ({ticker})")
            if article:
                article["relevance"] = f"ticker-search:{ticker}"
                articles.append(article)

        return articles
    except Exception as e:
        logger.warning("Google News (%s): %s", ticker, e)
        return []
