"""
Market definitions — US and Hong Kong universes.

This module exists so the app can:
  1. Tell which market a ticker belongs to (US vs HK).
  2. Offer curated quick-pick shortlists per market (S&P 500 majors,
     Hang Seng majors) without limiting free-form search.
  3. Drive *real* sector research: each sector points at a tradable
     instrument (a sector ETF or an index) plus a constituent basket.
     The headline read comes from the instrument; a market-cap weighted
     aggregate of the constituents gives the breadth read. This replaces
     the old approach of analysing a few names and pretending it described
     the whole sector.

Nothing here triggers LLM analysis — it is light read-only metadata used
by the markets router and the frontend Sectors page.
"""

from __future__ import annotations


def classify_market(ticker: str) -> str:
    """Return the market id ('us' or 'hk') for a ticker symbol.

    Hong Kong listings use a numeric symbol with a ``.HK`` suffix
    (e.g. ``0700.HK``). Everything else is treated as US for now.
    """
    t = (ticker or "").strip().upper()
    if t.endswith(".HK"):
        return "hk"
    return "us"


# Sector research instruments + constituent baskets, grouped by market.
# `instrument` is a tradable ETF or index whose price IS the sector read.
# `constituents` are used for a market-cap weighted breadth aggregate.
_US_SECTORS: list[dict] = [
    {
        "id": "us_technology",
        "name": "Technology",
        "instrument": "XLK",
        "instrument_name": "Technology Select Sector SPDR",
        "constituents": ["AAPL", "MSFT", "NVDA", "AVGO", "ORCL", "CRM", "AMD", "ADBE"],
    },
    {
        "id": "us_semiconductors",
        "name": "Semiconductors",
        "instrument": "SOXX",
        "instrument_name": "iShares Semiconductor ETF",
        "constituents": ["NVDA", "AVGO", "AMD", "TSM", "QCOM", "TXN", "INTC", "MU"],
    },
    {
        "id": "us_communication",
        "name": "Communication Services",
        "instrument": "XLC",
        "instrument_name": "Communication Services Select Sector SPDR",
        "constituents": ["META", "GOOGL", "NFLX", "DIS", "T", "VZ", "TMUS"],
    },
    {
        "id": "us_consumer_discretionary",
        "name": "Consumer Discretionary",
        "instrument": "XLY",
        "instrument_name": "Consumer Discretionary Select Sector SPDR",
        "constituents": ["AMZN", "TSLA", "HD", "MCD", "NKE", "LOW", "SBUX"],
    },
    {
        "id": "us_financials",
        "name": "Financials",
        "instrument": "XLF",
        "instrument_name": "Financial Select Sector SPDR",
        "constituents": ["JPM", "BAC", "WFC", "GS", "MS", "BLK", "C"],
    },
    {
        "id": "us_health_care",
        "name": "Health Care",
        "instrument": "XLV",
        "instrument_name": "Health Care Select Sector SPDR",
        "constituents": ["LLY", "UNH", "JNJ", "MRK", "ABBV", "PFE", "TMO"],
    },
    {
        "id": "us_energy",
        "name": "Energy",
        "instrument": "XLE",
        "instrument_name": "Energy Select Sector SPDR",
        "constituents": ["XOM", "CVX", "COP", "SLB", "EOG", "MPC", "PSX"],
    },
    {
        "id": "us_industrials",
        "name": "Industrials",
        "instrument": "XLI",
        "instrument_name": "Industrial Select Sector SPDR",
        "constituents": ["GE", "CAT", "RTX", "HON", "UNP", "BA", "DE"],
    },
]

_HK_SECTORS: list[dict] = [
    {
        "id": "hk_tech",
        "name": "Hang Seng TECH",
        "instrument": "^HSTECH",
        "instrument_name": "Hang Seng TECH Index",
        "constituents": ["0700.HK", "9988.HK", "3690.HK", "9618.HK", "1810.HK", "9999.HK", "9888.HK"],
    },
    {
        "id": "hk_financials",
        "name": "Financials",
        "instrument": "^HSCE",
        "instrument_name": "Hang Seng China Enterprises Index",
        "constituents": ["1398.HK", "0939.HK", "3988.HK", "2318.HK", "1288.HK", "0388.HK"],
    },
    {
        "id": "hk_consumer",
        "name": "Consumer",
        "instrument": "^HSI",
        "instrument_name": "Hang Seng Index",
        "constituents": ["2020.HK", "1876.HK", "0288.HK", "6862.HK", "1929.HK"],
    },
    {
        "id": "hk_property",
        "name": "Property",
        "instrument": "^HSI",
        "instrument_name": "Hang Seng Index",
        "constituents": ["0016.HK", "0001.HK", "0688.HK", "0823.HK", "0012.HK"],
    },
    {
        "id": "hk_energy",
        "name": "Energy & Utilities",
        "instrument": "^HSI",
        "instrument_name": "Hang Seng Index",
        "constituents": ["0883.HK", "0386.HK", "0857.HK", "0002.HK", "0003.HK"],
    },
]


MARKETS: dict[str, dict] = {
    "us": {
        "id": "us",
        "name": "United States",
        "short_name": "US",
        "currency": "USD",
        "benchmarks": [
            {"ticker": "^GSPC", "name": "S&P 500"},
            {"ticker": "^IXIC", "name": "Nasdaq Composite"},
            {"ticker": "^DJI", "name": "Dow Jones"},
        ],
        # Curated mega-cap shortlist — NOT a hard limit; free-form search
        # accepts any symbol that Yahoo can price.
        "quick_picks": [
            "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "AVGO",
            "JPM", "LLY", "UNH", "XOM", "V", "MA", "HD", "COST",
        ],
        "sectors": _US_SECTORS,
    },
    "hk": {
        "id": "hk",
        "name": "Hong Kong",
        "short_name": "HK",
        "currency": "HKD",
        "benchmarks": [
            {"ticker": "^HSI", "name": "Hang Seng Index"},
            {"ticker": "^HSTECH", "name": "Hang Seng TECH"},
            {"ticker": "^HSCE", "name": "HSCEI"},
        ],
        "quick_picks": [
            "0700.HK", "9988.HK", "3690.HK", "9618.HK", "1810.HK", "9999.HK",
            "1398.HK", "0939.HK", "2318.HK", "0388.HK", "0941.HK", "1299.HK",
            "0883.HK", "0016.HK", "2020.HK", "0005.HK",
        ],
        "sectors": _HK_SECTORS,
    },
}


def get_market(market_id: str) -> dict | None:
    """Look up a market by id ('us' or 'hk')."""
    return MARKETS.get((market_id or "").strip().lower())


def get_sector(sector_id: str) -> dict | None:
    """Find a sector definition by id across every market.

    Returns the raw sector dict (id, name, instrument, instrument_name,
    constituents) or ``None`` if the id is not a known market sector.
    """
    sid = (sector_id or "").strip().lower()
    for market in MARKETS.values():
        for sector in market.get("sectors", []):
            if sector["id"] == sid:
                return sector
    return None


def market_of_sector(sector_id: str) -> str | None:
    """Return the market id ('us'/'hk') that owns a sector id."""
    sid = (sector_id or "").strip().lower()
    for market_id, market in MARKETS.items():
        for sector in market.get("sectors", []):
            if sector["id"] == sid:
                return market_id
    return None


def list_sector_catalog(market_id: str) -> list[dict]:
    """Fast, LLM-free sector catalog for one market.

    Unlike ``/markets/sectors`` (which fetches live prices), this is pure
    metadata: the sector id, display name, instrument, and the constituent
    ticker basket. Used to populate the Stocks-page sector picker and to let
    the backend resolve which tickers a sector run should cover.
    """
    market_cfg = get_market(market_id) or MARKETS["us"]
    return [
        {
            "id": sector["id"],
            "name": sector["name"],
            "instrument": sector["instrument"],
            "instrument_name": sector.get("instrument_name", sector["instrument"]),
            "constituents": list(sector.get("constituents", [])),
        }
        for sector in market_cfg.get("sectors", [])
    ]


def list_markets() -> list[dict]:
    """Lightweight market metadata for the header toggle / quick-picks."""
    return [
        {
            "id": m["id"],
            "name": m["name"],
            "short_name": m["short_name"],
            "currency": m["currency"],
            "benchmarks": m["benchmarks"],
            "quick_picks": m["quick_picks"],
        }
        for m in MARKETS.values()
    ]
