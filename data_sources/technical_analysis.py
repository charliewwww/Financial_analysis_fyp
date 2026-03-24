"""
Technical Analysis — calculates indicators from price data.

Provides: RSI, MACD, Bollinger Bands, moving averages, volume analysis,
and support/resistance levels. All computed locally from Yahoo Finance data.

These indicators are:
1. Fed to the LLM so it can reference them in analysis
2. Stored in the database so users can see the raw data in the UI
3. Used for future anomaly detection (Z-score volume spikes)
"""

import pandas as pd
import numpy as np
from concurrent.futures import ThreadPoolExecutor, as_completed
from data_sources.yahoo_finance import get_price_history

import logging
logger = logging.getLogger(__name__)


def compute_technicals(ticker: str) -> dict:
    """
    Compute a full set of technical indicators for a stock.

    Returns a dict with all indicators, ready to:
    - Feed to the LLM as part of analysis context
    - Store in the database
    - Display in the UI
    """
    hist = get_price_history(ticker, period="1y")

    if hist.empty or len(hist) < 30:
        return {"ticker": ticker, "error": "Insufficient price history (need 30+ days)"}

    close = hist["Close"]
    volume = hist["Volume"]

    try:
        result = {
            "ticker": ticker,
            "error": None,
            "period": "1y",
            "data_points": len(hist),

            # ── Price & Trend ───────────────────────────────────
            "current_price": round(float(close.iloc[-1]), 2),
            "sma_20": round(float(close.rolling(20).mean().iloc[-1]), 2),
            "sma_50": round(float(close.rolling(50).mean().iloc[-1]), 2) if len(close) >= 50 else None,
            "ema_12": round(float(close.ewm(span=12).mean().iloc[-1]), 2),
            "ema_26": round(float(close.ewm(span=26).mean().iloc[-1]), 2),

            # Price vs moving averages (trend signals)
            "above_sma_20": bool(close.iloc[-1] > close.rolling(20).mean().iloc[-1]),
            "above_sma_50": bool(close.iloc[-1] > close.rolling(50).mean().iloc[-1]) if len(close) >= 50 else None,

            # ── RSI (Relative Strength Index) ───────────────────
            # RSI > 70 = overbought, RSI < 30 = oversold
            "rsi_14": _compute_rsi(close, period=14),

            # ── MACD ────────────────────────────────────────────
            # MACD > Signal = bullish, MACD < Signal = bearish
            **_compute_macd(close),

            # ── Bollinger Bands ─────────────────────────────────
            # Price near upper band = overbought, near lower = oversold
            **_compute_bollinger(close),

            # ── Volume Analysis ─────────────────────────────────
            "volume_latest": int(volume.iloc[-1]) if not pd.isna(volume.iloc[-1]) else 0,
            "volume_avg_20d": int(volume.rolling(20).mean().iloc[-1]) if not pd.isna(volume.rolling(20).mean().iloc[-1]) else 0,
            "volume_ratio": round(float(volume.iloc[-1] / volume.rolling(20).mean().iloc[-1]), 2) if volume.rolling(20).mean().iloc[-1] > 0 else None,
            # Z-score: how unusual is today's volume? > 2 = anomaly
            "volume_zscore": _volume_zscore(volume),

            # ── Support & Resistance ────────────────────────────
            "support_level": round(float(close.rolling(20).min().iloc[-1]), 2),
            "resistance_level": round(float(close.rolling(20).max().iloc[-1]), 2),
            "52w_high": round(float(close.max()), 2),
            "52w_low": round(float(close.min()), 2),
            "pct_from_52w_high": round(float((close.iloc[-1] - close.max()) / close.max() * 100), 1),

            # ── Momentum ────────────────────────────────────────
            "change_5d_pct": _pct_change_safe(close, 5),
            "change_10d_pct": _pct_change_safe(close, 10),
            "change_20d_pct": _pct_change_safe(close, 20),

            # ── Volatility ──────────────────────────────────────
            "volatility_20d": round(float(close.pct_change().rolling(20).std().iloc[-1] * 100), 2) if len(close) >= 21 else None,
        }

        # Add a human-readable summary line
        result["summary"] = _generate_ta_summary(result)

        return result

    except Exception as e:
        return {"ticker": ticker, "error": f"Technical analysis failed: {e}"}


def compute_sector_technicals(tickers: list[str]) -> list[dict]:
    """Compute technical indicators for all tickers in a sector — concurrently."""
    if not tickers:
        return []

    results_map: dict[str, dict] = {}

    with ThreadPoolExecutor(max_workers=min(len(tickers), 6)) as pool:
        future_to_ticker = {
            pool.submit(compute_technicals, t): t for t in tickers
        }
        for future in as_completed(future_to_ticker):
            ticker = future_to_ticker[future]
            try:
                results_map[ticker] = future.result(timeout=60)
            except Exception as e:
                logger.error("Technicals for %s failed: %s", ticker, e)
                results_map[ticker] = {"ticker": ticker, "error": str(e)}

    # Preserve original ticker order
    return [results_map[t] for t in tickers]


# ── Indicator Calculations ─────────────────────────────────────────

def _compute_rsi(close: pd.Series, period: int = 14) -> float | None:
    """RSI: 0-100. Above 70 = overbought, below 30 = oversold."""
    if len(close) < period + 1:
        return None
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0.0)).rolling(period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    val = rsi.iloc[-1]
    return round(float(val), 1) if not pd.isna(val) else None


def _compute_macd(close: pd.Series) -> dict:
    """MACD: trend-following momentum indicator."""
    if len(close) < 26:
        return {"macd_line": None, "macd_signal": None, "macd_histogram": None, "macd_bullish": None}
    ema12 = close.ewm(span=12).mean()
    ema26 = close.ewm(span=26).mean()
    macd_line = ema12 - ema26
    signal = macd_line.ewm(span=9).mean()
    histogram = macd_line - signal
    return {
        "macd_line": round(float(macd_line.iloc[-1]), 3),
        "macd_signal": round(float(signal.iloc[-1]), 3),
        "macd_histogram": round(float(histogram.iloc[-1]), 3),
        "macd_bullish": bool(macd_line.iloc[-1] > signal.iloc[-1]),
    }


def _compute_bollinger(close: pd.Series, period: int = 20, std_dev: int = 2) -> dict:
    """Bollinger Bands: volatility indicator."""
    if len(close) < period:
        return {"bb_upper": None, "bb_middle": None, "bb_lower": None, "bb_position": None}
    sma = close.rolling(period).mean()
    std = close.rolling(period).std()
    upper = sma + (std * std_dev)
    lower = sma - (std * std_dev)
    # Position: 0 = at lower band, 1 = at upper band, 0.5 = at middle
    band_width = upper.iloc[-1] - lower.iloc[-1]
    position = (close.iloc[-1] - lower.iloc[-1]) / band_width if band_width > 0 else 0.5
    return {
        "bb_upper": round(float(upper.iloc[-1]), 2),
        "bb_middle": round(float(sma.iloc[-1]), 2),
        "bb_lower": round(float(lower.iloc[-1]), 2),
        "bb_position": round(float(position), 2),  # 0-1 scale
    }


def _volume_zscore(volume: pd.Series, period: int = 20) -> float | None:
    """Z-score of latest volume vs 20-day mean. > 2 = unusual spike."""
    if len(volume) < period:
        return None
    mean = volume.rolling(period).mean().iloc[-1]
    std = volume.rolling(period).std().iloc[-1]
    if std == 0 or pd.isna(std):
        return 0.0
    z = (volume.iloc[-1] - mean) / std
    return round(float(z), 2) if not pd.isna(z) else None


def _pct_change_safe(series: pd.Series, days: int) -> float | None:
    """Safe percentage change calculation."""
    if len(series) < days + 1:
        return None
    current = series.iloc[-1]
    past = series.iloc[-(days + 1)]
    if past == 0 or pd.isna(past):
        return None
    return round(float((current - past) / past * 100), 2)


def _generate_ta_summary(ta: dict) -> str:
    """Generate a one-line human-readable summary of the technical picture."""
    parts = []

    # Trend
    rsi = ta.get("rsi_14")
    if rsi is not None:
        if rsi > 70:
            parts.append(f"RSI={rsi} (OVERBOUGHT)")
        elif rsi < 30:
            parts.append(f"RSI={rsi} (OVERSOLD)")
        else:
            parts.append(f"RSI={rsi}")

    # MACD
    if ta.get("macd_bullish") is not None:
        parts.append("MACD: BULLISH crossover" if ta["macd_bullish"] else "MACD: BEARISH crossover")

    # Bollinger position
    bb = ta.get("bb_position")
    if bb is not None:
        if bb > 0.9:
            parts.append("Near upper Bollinger (overbought)")
        elif bb < 0.1:
            parts.append("Near lower Bollinger (oversold)")

    # Volume
    vz = ta.get("volume_zscore")
    if vz is not None and abs(vz) > 2:
        parts.append(f"UNUSUAL VOLUME (Z={vz})")

    # Trend direction
    if ta.get("above_sma_50") is not None:
        parts.append("Above 50-SMA (uptrend)" if ta["above_sma_50"] else "Below 50-SMA (downtrend)")

    return " | ".join(parts) if parts else "Neutral"
