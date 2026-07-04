"""Markets router — US/HK universes, quick-picks, and real sector reads.

Endpoints (under /api/v1):

    GET /markets                List markets (US, HK) + curated quick-picks.
    GET /markets/sectors        Real sector snapshots for one market:
                                a tradable instrument (sector ETF / index)
                                plus a market-cap weighted breadth aggregate
                                of the constituent basket.

This is read-only market data (no LLM). Results are cached in-process for a
short TTL because the underlying Yahoo Finance calls are slow.
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, Query

from app.pipeline import runner as _runner  # noqa: F401 — ensures sys.path patch

from config.markets import MARKETS, get_market, list_markets, list_sector_catalog  # type: ignore[import]
from data_sources.yahoo_finance import get_sector_prices, get_stock_snapshot  # type: ignore[import]

router = APIRouter(tags=["markets"])

# Simple in-process TTL cache for the (slow) sector snapshot aggregation.
_SECTOR_CACHE: dict[str, tuple[float, list[dict]]] = {}
_SECTOR_TTL_SECONDS = 300  # 5 minutes


@router.get(
    "/markets",
    summary="List markets",
    description="Returns the US and Hong Kong universes with curated quick-pick shortlists.",
)
async def get_markets() -> list[dict]:
    return list_markets()


@router.get(
    "/markets/sector-catalog",
    summary="Sector catalog for a market (fast, no prices)",
    description=(
        "Lightweight, LLM-free list of a market's sectors with their "
        "constituent ticker baskets. Used to populate the Stocks-page sector "
        "picker and drive market-correct sector runs. No live price fetching."
    ),
)
async def get_market_sector_catalog(
    market: str = Query("us", description="Market id: 'us' or 'hk'"),
) -> dict:
    market_id = (market or "us").strip().lower()
    market_cfg = get_market(market_id) or MARKETS["us"]
    return {
        "market": {
            "id": market_cfg["id"],
            "name": market_cfg["name"],
            "currency": market_cfg["currency"],
        },
        "sectors": list_sector_catalog(market_cfg["id"]),
    }


def _weighted_sector_read(sector: dict) -> dict:
    """Build one sector card: instrument read + cap-weighted breadth."""
    instrument_ticker = sector["instrument"]
    constituents = sector.get("constituents", [])

    instrument = get_stock_snapshot(instrument_ticker)
    rows = get_sector_prices(constituents)

    valid = [r for r in rows if not r.get("error") and r.get("change_1w_pct") is not None]

    # Market-cap weighted 1-week move across the basket (breadth read).
    total_cap = 0.0
    weighted_1w = 0.0
    advancers = 0
    decliners = 0
    for r in valid:
        cap = r.get("market_cap") or 0
        change = r.get("change_1w_pct")
        if change is None:
            continue
        if change > 0:
            advancers += 1
        elif change < 0:
            decliners += 1
        if cap and cap > 0:
            total_cap += cap
            weighted_1w += cap * change

    cap_weighted_change_1w = round(weighted_1w / total_cap, 2) if total_cap > 0 else None

    leaders = sorted(
        (r for r in valid),
        key=lambda r: r.get("change_1w_pct") or 0,
        reverse=True,
    )

    def _slim(r: dict) -> dict:
        return {
            "ticker": r.get("ticker"),
            "price": r.get("price"),
            "change_1w_pct": r.get("change_1w_pct"),
            "market_cap": r.get("market_cap"),
        }

    return {
        "id": sector["id"],
        "name": sector["name"],
        "instrument": {
            "ticker": instrument_ticker,
            "name": sector.get("instrument_name", instrument_ticker),
            "price": instrument.get("price") if not instrument.get("error") else None,
            "change_1w_pct": instrument.get("change_1w_pct") if not instrument.get("error") else None,
            "change_1m_pct": instrument.get("change_1m_pct") if not instrument.get("error") else None,
        },
        "cap_weighted_change_1w_pct": cap_weighted_change_1w,
        "breadth": {
            "advancers": advancers,
            "decliners": decliners,
            "total": len(valid),
        },
        "constituent_count": len(constituents),
        "top_movers": [_slim(r) for r in leaders[:3]],
        "bottom_movers": [_slim(r) for r in leaders[-3:][::-1]] if len(leaders) > 3 else [],
    }


@router.get(
    "/markets/sectors",
    summary="Real sector snapshots for a market",
    description=(
        "For each sector in the chosen market, returns the tradable instrument "
        "read (sector ETF or index) plus a market-cap weighted breadth aggregate "
        "of its constituent basket. Cached for 5 minutes."
    ),
)
async def get_market_sectors(
    market: str = Query("us", description="Market id: 'us' or 'hk'"),
) -> dict:
    market_id = (market or "us").strip().lower()
    market_cfg = get_market(market_id)
    if market_cfg is None:
        market_id = "us"
        market_cfg = MARKETS["us"]

    cached = _SECTOR_CACHE.get(market_id)
    now = time.time()
    if cached and (now - cached[0]) < _SECTOR_TTL_SECONDS:
        sectors = cached[1]
    else:
        sector_defs = market_cfg.get("sectors", [])
        with ThreadPoolExecutor(max_workers=min(len(sector_defs) or 1, 4)) as pool:
            sectors = list(pool.map(_weighted_sector_read, sector_defs))
        _SECTOR_CACHE[market_id] = (now, sectors)

    return {
        "market": {
            "id": market_cfg["id"],
            "name": market_cfg["name"],
            "currency": market_cfg["currency"],
        },
        "sectors": sectors,
    }
