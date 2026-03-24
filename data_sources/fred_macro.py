"""
FRED Macro Data — fetch macroeconomic indicators from the Federal Reserve.

Uses the FRED API (Federal Reserve Economic Data) to pull:
  - Federal Funds Rate (interest rate that moves everything)
  - CPI Year-over-Year (inflation)
  - GDP Growth Rate (economic health)
  - Unemployment Rate (labor market)
  - 10-Year Treasury Yield (bond market / risk appetite)
  - Consumer Sentiment (forward-looking demand indicator)

WHY THIS MATTERS FOR SECTOR ANALYSIS:
  - Rising rates → pressure on growth stocks (tech, semis) → cheaper borrowing for competitors
  - High CPI → Fed stays hawkish → dollar strength → hurts exporters
  - GDP slowdown → capex cuts → fewer semiconductor orders → impacts supply chain
  - Unemployment spike → consumer spending drops → hits downstream demand
  - 10Y yield spike → money rotates from equities to bonds → sector-wide pressure
  - Low sentiment → consumers defer big purchases → demand signal for supply chains

GRACEFUL DEGRADATION:
  If no FRED_API_KEY is set, or if the FRED API is down, this module
  returns an empty dict and the pipeline continues without macro context.
  The analysis will just be less informed — it won't crash.
"""

from __future__ import annotations

import os
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger(__name__)

# ── FRED Series IDs ───────────────────────────────────────────────
# These are the official FRED series identifiers.
# Documentation: https://fred.stlouisfed.org/docs/api/fred/
MACRO_SERIES = {
    "fed_funds_rate": {
        "series_id": "FEDFUNDS",
        "name": "Federal Funds Rate",
        "unit": "%",
        "frequency": "monthly",
        "description": (
            "The interest rate at which banks lend reserves to each other overnight. "
            "Set by the Federal Reserve. Higher rates = tighter monetary policy = "
            "more expensive borrowing = pressure on growth stocks and capex spending."
        ),
        "interpretation": {
            "rising": "Hawkish Fed — headwind for growth sectors, higher discount rates on future earnings",
            "falling": "Dovish Fed — tailwind for growth sectors, cheaper capital for expansion",
            "high": "Restrictive — companies pay more to borrow, consumers pay more for mortgages/credit",
            "low": "Accommodative — cheap money fuels investment and risk-taking",
        },
    },
    "cpi_yoy": {
        "series_id": "CPIAUCSL",
        "name": "CPI (Consumer Price Index)",
        "unit": "index",
        "frequency": "monthly",
        "yoy": True,  # We'll compute year-over-year change ourselves
        "description": (
            "Measures overall price inflation for urban consumers. "
            "Year-over-year change shows whether inflation is accelerating or cooling. "
            "High CPI → Fed stays hawkish → bad for equities, especially tech multiples."
        ),
        "interpretation": {
            "rising": "Inflation accelerating — Fed may hike further, compresses multiples",
            "falling": "Inflation cooling — Fed may pause/cut, expands multiples",
            "high": "Above 3% YoY is elevated — supply chain costs rising, margin pressure",
            "low": "Below 2% signals weak demand or deflation risk",
        },
    },
    "gdp_growth": {
        "series_id": "A191RL1Q225SBEA",
        "name": "Real GDP Growth Rate",
        "unit": "% annualized",
        "frequency": "quarterly",
        "description": (
            "Quarter-over-quarter GDP growth rate, seasonally adjusted annual rate. "
            "Measures total economic output growth. Negative = recession territory."
        ),
        "interpretation": {
            "rising": "Economy accelerating — demand for goods/services increasing",
            "falling": "Economy decelerating — capex cuts likely, demand weakening",
            "high": "Above 3% is strong — robust demand across sectors",
            "low": "Below 1% or negative — recession risk, defensive positioning",
        },
    },
    "unemployment": {
        "series_id": "UNRATE",
        "name": "Unemployment Rate",
        "unit": "%",
        "frequency": "monthly",
        "description": (
            "Percentage of labor force that is unemployed and actively seeking work. "
            "Rising unemployment → consumer spending drops → downstream demand falls."
        ),
        "interpretation": {
            "rising": "Labor market weakening — less consumer spending, less demand",
            "falling": "Tight labor market — wage inflation, strong consumer base",
            "high": "Above 5% signals weakness — hits consumer-facing sectors",
            "low": "Below 4% is very tight — wage pressure but strong demand",
        },
    },
    "treasury_10y": {
        "series_id": "DGS10",
        "name": "10-Year Treasury Yield",
        "unit": "%",
        "frequency": "daily",
        "description": (
            "Yield on US 10-year government bonds. The benchmark risk-free rate. "
            "When yields rise, money flows from equities to bonds. "
            "Directly impacts the discount rate used to value growth companies."
        ),
        "interpretation": {
            "rising": "Money rotating to bonds — headwind for equities, especially high-P/E names",
            "falling": "Risk appetite increasing — tailwind for growth stocks and tech",
            "high": "Above 4.5% creates significant competition for equity capital",
            "low": "Below 3% makes equities relatively more attractive (TINA effect)",
        },
    },
    "consumer_sentiment": {
        "series_id": "UMCSENT",
        "name": "U. of Michigan Consumer Sentiment",
        "unit": "index (1966=100)",
        "frequency": "monthly",
        "description": (
            "Forward-looking indicator of consumer confidence and spending intentions. "
            "Low sentiment → consumers defer big purchases → demand signal for supply chains."
        ),
        "interpretation": {
            "rising": "Consumers more optimistic — positive for discretionary spending",
            "falling": "Consumers pessimistic — pullback in spending ahead",
            "high": "Above 80 is healthy — broad-based demand",
            "low": "Below 60 signals distress — historically precedes spending drops",
        },
    },
}


def get_macro_snapshot() -> dict[str, Any]:
    """
    Fetch the latest values for all macro indicators from FRED.

    Returns a dict like:
        {
            "fed_funds_rate": {
                "value": 5.33,
                "date": "2024-01-01",
                "name": "Federal Funds Rate",
                "unit": "%",
                "description": "...",
                "interpretation": {...},
                "previous_value": 5.33,
                "change": 0.0,
                "trend": "stable",
            },
            "cpi_yoy": { ... },
            ...
            "_meta": {
                "fetched_at": "2024-12-15T10:00:00",
                "source": "FRED (Federal Reserve Economic Data)",
                "api_status": "ok",
            }
        }

    If FRED_API_KEY is not set or the API fails, returns:
        {"_meta": {"api_status": "unavailable", "reason": "..."}}
    """
    from config.settings import FRED_API_KEY

    if not FRED_API_KEY:
        logger.info("No FRED_API_KEY set — skipping macro data (set it in .env for richer analysis)")
        return {
            "_meta": {
                "api_status": "unavailable",
                "reason": "No FRED_API_KEY in .env — get a free key at https://fred.stlouisfed.org/docs/api/api_key.html",
                "source": "FRED (Federal Reserve Economic Data)",
            }
        }

    try:
        from fredapi import Fred
    except ImportError:
        logger.warning("fredapi not installed — run: pip install fredapi")
        return {
            "_meta": {
                "api_status": "unavailable",
                "reason": "fredapi package not installed",
                "source": "FRED (Federal Reserve Economic Data)",
            }
        }

    try:
        fred = Fred(api_key=FRED_API_KEY)
    except Exception as e:
        logger.warning("FRED API init failed: %s", e)
        return {
            "_meta": {
                "api_status": "error",
                "reason": str(e),
                "source": "FRED (Federal Reserve Economic Data)",
            }
        }

    result: dict[str, Any] = {}
    errors = []

    for key, config in MACRO_SERIES.items():
        try:
            series = fred.get_series(
                config["series_id"],
                observation_start=(datetime.now() - timedelta(days=400)).strftime("%Y-%m-%d"),
            )

            # Drop NaN values and get recent data
            series = series.dropna()
            if series.empty:
                errors.append(f"{key}: no data returned")
                continue

            latest_value = float(series.iloc[-1])
            latest_date = series.index[-1].strftime("%Y-%m-%d")

            # For CPI, compute year-over-year percentage change
            if config.get("yoy") and len(series) >= 13:
                current = series.iloc[-1]
                year_ago = series.iloc[-13]  # 12 months back (monthly data)
                yoy_change = ((current - year_ago) / year_ago) * 100
                latest_value = round(yoy_change, 2)

            # Get previous value for trend detection
            previous_value = None
            change = None
            trend = "unknown"

            if len(series) >= 2:
                if config.get("yoy") and len(series) >= 14:
                    prev_current = series.iloc[-2]
                    prev_year_ago = series.iloc[-14]
                    previous_value = round(((prev_current - prev_year_ago) / prev_year_ago) * 100, 2)
                else:
                    previous_value = float(series.iloc[-2])

                if previous_value is not None:
                    change = round(latest_value - previous_value, 4)
                    if abs(change) < 0.01:
                        trend = "stable"
                    elif change > 0:
                        trend = "rising"
                    else:
                        trend = "falling"

            result[key] = {
                "value": round(latest_value, 2),
                "date": latest_date,
                "name": config["name"],
                "unit": "% YoY" if config.get("yoy") else config["unit"],
                "description": config["description"],
                "interpretation": config["interpretation"],
                "previous_value": round(previous_value, 2) if previous_value is not None else None,
                "change": round(change, 4) if change is not None else None,
                "trend": trend,
            }

        except Exception as e:
            errors.append(f"{key}: {e}")
            continue

    result["_meta"] = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "source": "FRED (Federal Reserve Economic Data)",
        "api_status": "ok" if len(errors) < len(MACRO_SERIES) else "partial",
        "indicators_fetched": len(result) - 1,  # Exclude _meta itself
        "errors": errors if errors else None,
    }

    if errors:
        logger.warning("FRED: %d indicator(s) failed — %s", len(errors), ', '.join(errors[:3]))

    return result


def format_macro_for_prompt(macro_data: dict[str, Any]) -> str:
    """
    Format macro data into a clean text block for injection into analysis prompts.

    This is designed to be appended to the analysis prompt so the LLM
    can reason about how macro conditions affect the sector.

    Returns an empty string if no macro data is available.
    """
    meta = macro_data.get("_meta", {})
    if meta.get("api_status") == "unavailable":
        return ""

    if meta.get("indicators_fetched", 0) == 0:
        return ""

    lines = [
        "## MACROECONOMIC CONTEXT",
        f"Source: FRED (Federal Reserve Economic Data) | Fetched: {meta.get('fetched_at', 'unknown')[:10]}",
        "",
        "These macro indicators provide context for how broader economic forces",
        "may be affecting this sector's supply chain and demand dynamics.",
        "",
    ]

    trend_icons = {
        "rising": "📈",
        "falling": "📉",
        "stable": "➡️",
        "unknown": "❓",
    }

    for key, config in MACRO_SERIES.items():
        data = macro_data.get(key)
        if not data:
            continue

        icon = trend_icons.get(data.get("trend", "unknown"), "❓")
        value = data["value"]
        unit = data["unit"]
        trend = data.get("trend", "unknown")
        change = data.get("change")
        name = data["name"]

        # Format the value line
        change_str = ""
        if change is not None:
            change_str = f" ({change:+.2f} from previous)"

        lines.append(f"### {name}")
        lines.append(f"- **Current: {value}{unit}** {icon} Trend: {trend}{change_str}")
        lines.append(f"- Date: {data.get('date', 'N/A')}")

        # Add the relevant interpretation based on current trend
        interp = data.get("interpretation", {})
        if trend in interp:
            lines.append(f"- Signal: {interp[trend]}")

        # Add level-based interpretation
        if key == "fed_funds_rate":
            if value > 4.5:
                level_note = interp.get("high", "")
            elif value < 2.0:
                level_note = interp.get("low", "")
            else:
                level_note = ""
        elif key == "cpi_yoy":
            if value > 3.0:
                level_note = interp.get("high", "")
            elif value < 2.0:
                level_note = interp.get("low", "")
            else:
                level_note = ""
        elif key == "gdp_growth":
            if value > 3.0:
                level_note = interp.get("high", "")
            elif value < 1.0:
                level_note = interp.get("low", "")
            else:
                level_note = ""
        elif key == "unemployment":
            if value > 5.0:
                level_note = interp.get("high", "")
            elif value < 4.0:
                level_note = interp.get("low", "")
            else:
                level_note = ""
        elif key == "treasury_10y":
            if value > 4.5:
                level_note = interp.get("high", "")
            elif value < 3.0:
                level_note = interp.get("low", "")
            else:
                level_note = ""
        elif key == "consumer_sentiment":
            if value > 80:
                level_note = interp.get("high", "")
            elif value < 60:
                level_note = interp.get("low", "")
            else:
                level_note = ""
        else:
            level_note = ""

        if level_note:
            lines.append(f"- Level: {level_note}")

        lines.append("")

    lines.append(
        "**Use these macro indicators to contextualize your sector analysis. "
        "How do current interest rates, inflation, and economic growth "
        "affect this sector's supply chain and demand outlook?**"
    )

    return "\n".join(lines)
