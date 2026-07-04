"""Supply chain router — exposes the static topology + flows from
`config/supply_chain_data.py` to the frontend.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.pipeline import runner as _runner  # noqa: F401 — ensures sys.path patch

from config.supply_chain_data import SUPPLY_CHAIN_DATA  # type: ignore[import]

router = APIRouter(tags=["supply-chain"])


@router.get(
    "/supply-chain",
    summary="List sectors that have curated supply chain data",
)
async def list_supply_chain_sectors(
    market: str | None = Query(default=None, description="us | hk"),
) -> list[dict]:
    wanted = market.strip().lower() if market else None
    return [
        {
            "id": sid,
            "name": data.get("sector_name", sid),
            "description": data.get("description", ""),
            "market": data.get("market", "us"),
        }
        for sid, data in SUPPLY_CHAIN_DATA.items()
        if wanted is None or data.get("market", "us") == wanted
    ]


@router.get(
    "/supply-chain/{sector_id}",
    summary="Curated supply chain topology for one sector",
)
async def get_sector_supply_chain(sector_id: str) -> dict:
    sector = SUPPLY_CHAIN_DATA.get(sector_id)
    if sector is None:
        raise HTTPException(status_code=404, detail="Sector not found")
    companies = sector.get("companies", {})
    return {
        "id": sector_id,
        "name": sector.get("sector_name", sector_id),
        "description": sector.get("description", ""),
        "chain_layers": sector.get("chain_layers", []),
        "companies": [
            {
                "ticker": ticker,
                "name": c.get("name", ticker),
                "layer": c.get("layer"),
                "products": c.get("products", []),
                "supplies_to": c.get("supplies_to", []),
                "receives_from": c.get("receives_from", []),
                "revenue_segments": c.get("revenue_segments", {}),
                "cost_inputs": c.get("cost_inputs", {}),
            }
            for ticker, c in companies.items()
        ],
        "key_flows": sector.get("key_flows", []),
    }
