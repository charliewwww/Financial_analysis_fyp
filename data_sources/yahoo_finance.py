"""
Yahoo Finance Data Fetcher — stock prices, fundamentals, and key ratios.

Uses the `yfinance` library (free, no API key needed).
Provides: current price, price history, key financial metrics, and basic info.
"""

import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import time as _time

import logging
logger = logging.getLogger(__name__)

# Retry parameters for transient yfinance failures
_YFINANCE_RETRIES = 2
_YFINANCE_RETRY_DELAY = 1.0


def get_stock_snapshot(ticker: str) -> dict:
    """
    Get a comprehensive snapshot of a stock for analysis.
    Includes automatic retry for transient yfinance failures.
    """
    last_err = None
    for attempt in range(_YFINANCE_RETRIES + 1):
        try:
            stock = yf.Ticker(ticker)
            info = stock.info

            # Get price history for change calculations
            hist = stock.history(period="3mo")
            if hist.empty:
                return {"ticker": ticker, "error": "No price data available"}

            current_price = hist["Close"].iloc[-1]

            # Calculate % changes
            change_1w = _pct_change(hist, days=5)
            change_1m = _pct_change(hist, days=21)

            return {
                "ticker": ticker,
                "price": round(current_price, 2),
                "change_1w_pct": round(change_1w, 2) if change_1w else None,
                "change_1m_pct": round(change_1m, 2) if change_1m else None,
                "volume": int(hist["Volume"].iloc[-1]) if not pd.isna(hist["Volume"].iloc[-1]) else None,
                "avg_volume": info.get("averageVolume"),
                "market_cap": info.get("marketCap"),
                "pe_ratio": info.get("trailingPE"),
                "forward_pe": info.get("forwardPE"),
                "revenue_ttm": info.get("totalRevenue"),
                "profit_margin": info.get("profitMargins"),
                "eps_ttm": info.get("trailingEps"),
                "52w_high": info.get("fiftyTwoWeekHigh"),
                "52w_low": info.get("fiftyTwoWeekLow"),
                "sector": info.get("sector", "N/A"),
                "industry": info.get("industry", "N/A"),
                "summary": (info.get("longBusinessSummary") or "")[:300],
                "currency": info.get("currency", "USD"),
                "error": None,
            }
        except Exception as e:
            last_err = e
            if attempt < _YFINANCE_RETRIES:
                logger.warning("%s: attempt %d/%d failed (%s) — retrying in %.1fs",
                               ticker, attempt + 1, _YFINANCE_RETRIES + 1, e,
                               _YFINANCE_RETRY_DELAY * (attempt + 1))
                _time.sleep(_YFINANCE_RETRY_DELAY * (attempt + 1))

    return {"ticker": ticker, "error": str(last_err)}


def get_sector_prices(tickers: list[str]) -> list[dict]:
    """
    Get price snapshots for all tickers in a sector — concurrently.
    Returns a list of snapshot dicts (order matches input tickers).
    """
    if not tickers:
        return []

    results: dict[str, dict] = {}

    with ThreadPoolExecutor(max_workers=min(len(tickers), 6)) as pool:
        future_to_ticker = {
            pool.submit(get_stock_snapshot, t): t for t in tickers
        }
        for future in as_completed(future_to_ticker):
            ticker = future_to_ticker[future]
            try:
                results[ticker] = future.result(timeout=60)
            except Exception as e:
                logger.error("%s fetch failed: %s", ticker, e)
                results[ticker] = {"ticker": ticker, "error": str(e)}

    # Preserve original ticker order
    return [results[t] for t in tickers]


def get_price_history(ticker: str, period: str = "6mo") -> pd.DataFrame:
    """
    Get OHLCV price history for a stock.

    Args:
        ticker: Stock ticker symbol
        period: Time period ('1mo', '3mo', '6mo', '1y', '2y', '5y')

    Returns:
        DataFrame with Date, Open, High, Low, Close, Volume columns
    """
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period=period)
        return hist
    except Exception as e:
        logger.warning("Failed to get price history for %s: %s", ticker, e)
        return pd.DataFrame()


def _pct_change(hist: pd.DataFrame, days: int) -> float | None:
    """Calculate % price change over N trading days."""
    if len(hist) < days + 1:
        return None
    current = hist["Close"].iloc[-1]
    past = hist["Close"].iloc[-min(days + 1, len(hist))]
    if past == 0:
        return None
    return ((current - past) / past) * 100
