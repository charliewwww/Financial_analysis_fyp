"""
Point-in-time data assembly for the model backtest.

Given a cutoff date, returns the data that WOULD have been available on/before
that date — with no lookahead:

  * prices / technicals : Yahoo Finance history truncated to <= cutoff
  * news                : the dated vector-store articles published <= cutoff
                          (RSS feeds are live-only and cannot be time-travelled,
                          so the ChromaDB news archive is the only honest source
                          of historical headlines)
  * filings / macro     : omitted (cannot be cleanly reconstructed as-of)

This module is ONLY used when PipelineState.as_of_date is set. Live runs never
touch it, so it carries zero risk to the production path.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta

from data_sources.yahoo_finance import get_stock_snapshot
from data_sources.technical_analysis import compute_technicals

logger = logging.getLogger(__name__)


def _to_date(value: str) -> date | None:
    try:
        return date.fromisoformat(value[:10])
    except Exception:
        return None


def news_as_of(sector_dict: dict, as_of_date: str, lookback_days: int = 14,
               max_articles: int = 15) -> list[dict]:
    """Retrieve dated vector-store articles published within
    [cutoff - lookback_days, cutoff], ranked by semantic relevance to the
    sector/ticker query then recency. Returns article dicts shaped like the
    live RSS fetch so fetch_node can build Article objects unchanged."""
    try:
        from vectordb import chroma_store as cs
    except Exception as e:  # pragma: no cover
        logger.warning("chroma unavailable for as-of news: %s", e)
        return []

    col = cs._get_collection(cs.COL_NEWS)
    if col is None:
        return []

    tickers = sector_dict.get("tickers", []) or []
    keywords = sector_dict.get("keywords", []) or []
    query = " ".join([sector_dict.get("name", "")] + list(tickers) + list(keywords)).strip()
    query = query[:300] or "market news"

    try:
        res = col.query(query_texts=[query], n_results=150)
    except Exception as e:
        logger.warning("as-of news query failed: %s", e)
        return []

    docs = (res.get("documents") or [[]])[0]
    metas = (res.get("metadatas") or [[]])[0]

    cutoff = _to_date(as_of_date)
    if cutoff is None:
        return []
    low = cutoff - timedelta(days=lookback_days)

    picked: list[dict] = []
    for doc, meta in zip(docs, metas):
        meta = meta or {}
        pub_raw = str(meta.get("published", ""))[:10]
        pub = _to_date(pub_raw)
        if pub is None or not (low <= pub <= cutoff):
            continue
        text = doc or ""
        first_line = text.split("\n", 1)[0].strip()
        title = (first_line or (meta.get("source", "") + " headline"))[:160]
        picked.append({
            "title": title,
            "source": meta.get("source", "") or "Archive",
            "link": meta.get("link", "") or "",
            "published": pub_raw,
            "summary": text[:800],
            "relevance": "point-in-time",
            "source_url": "",
            "aggregator": "",
        })

    picked.sort(key=lambda a: a["published"], reverse=True)
    return picked[:max_articles]


def fetch_point_in_time(tickers: list[str], sector_dict: dict, as_of_date: str) -> dict:
    """Assemble the `results` dict fetch_node expects, frozen to <= cutoff."""
    prices = [get_stock_snapshot(t, as_of_date=as_of_date) for t in tickers]
    technicals = [compute_technicals(t, as_of_date=as_of_date) for t in tickers]
    articles = news_as_of(sector_dict, as_of_date)
    logger.info(
        "Point-in-time @ %s: %d priced, %d technicals, %d archived articles",
        as_of_date,
        len([p for p in prices if not p.get("error")]),
        len([t for t in technicals if not t.get("error")]),
        len(articles),
    )
    return {
        "news": articles,
        "prices": prices,
        "technicals": technicals,
        "filings": [],   # not reconstructable as-of
        "macro": {},     # not reconstructable as-of
    }


def forward_return(ticker: str, as_of_date: str, days: int = 7,
                   neutral_band_pct: float = 1.0) -> dict | None:
    """The ACTUAL outcome: % price change from the cutoff close to the close
    ~`days` calendar days later (the 'following week'). Used to grade the AI's
    predicted direction. Returns None if data is unavailable."""
    import yfinance as yf
    import pandas as pd

    try:
        start = pd.Timestamp(as_of_date) - pd.Timedelta(days=7)
        end = pd.Timestamp(as_of_date) + pd.Timedelta(days=days + 10)
        hist = yf.Ticker(ticker).history(start=start.date().isoformat(), end=end.date().isoformat())
        if hist.empty:
            return None
        cutoff = pd.Timestamp(as_of_date).date()
        target = cutoff + timedelta(days=days)
        at = hist[hist.index.date <= cutoff]
        after = hist[hist.index.date <= target]
        if at.empty or after.empty:
            return None
        p0 = float(at["Close"].iloc[-1])
        p1 = float(after["Close"].iloc[-1])
        if p0 == 0:
            return None
        change = (p1 - p0) / p0 * 100.0
        if change > neutral_band_pct:
            direction = "BULLISH"
        elif change < -neutral_band_pct:
            direction = "BEARISH"
        else:
            direction = "NEUTRAL"
        return {
            "ticker": ticker,
            "as_of": as_of_date,
            "price_at": round(p0, 2),
            "price_after": round(p1, 2),
            "change_pct": round(change, 2),
            "actual_direction": direction,
            "settled_on": str(after.index[-1].date()),
            "horizon_days": days,
        }
    except Exception as e:
        logger.warning("forward_return failed for %s @ %s: %s", ticker, as_of_date, e)
        return None
