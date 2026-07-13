"""
Watchlist router — the user's "My Favourites" tickers.

Endpoints:
    GET    /api/v1/watchlist            List the current user's favourites
    POST   /api/v1/watchlist            Add a ticker to favourites
    DELETE /api/v1/watchlist/{ticker}   Remove a ticker from favourites

Every row is scoped to the authenticated user's email, so one user never
sees another's favourites.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncConnection

from app.core.auth import CurrentUser
from app.db.engine import get_db
from app.db.repositories import watchlist as watchlist_repo
from app.schemas.watchlist import WatchlistAddRequest, WatchlistItemSchema

router = APIRouter(prefix="/watchlist", tags=["watchlist"])

DB = Annotated[AsyncConnection, Depends(get_db)]


@router.get(
    "",
    response_model=list[WatchlistItemSchema],
    summary="List my favourites",
    description="Returns the authenticated user's saved favourite tickers, newest first.",
)
async def list_watchlist(db: DB, user: CurrentUser) -> list[WatchlistItemSchema]:
    return await watchlist_repo.list_for_user(db, user)


@router.post(
    "",
    response_model=WatchlistItemSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Add to favourites",
    description=(
        "Adds a ticker to the user's favourites. Idempotent: re-adding an "
        "existing ticker updates its notes/sector instead of erroring."
    ),
)
async def add_to_watchlist(
    body: WatchlistAddRequest, db: DB, user: CurrentUser
) -> WatchlistItemSchema:
    return await watchlist_repo.add(
        db, user, body.ticker, notes=body.notes, sector_id=body.sector_id
    )


@router.delete(
    "/{ticker}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove from favourites",
    description="Removes a ticker from the user's favourites.",
)
async def remove_from_watchlist(ticker: str, db: DB, user: CurrentUser) -> Response:
    removed = await watchlist_repo.remove(db, user, ticker)
    if not removed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"'{ticker.upper()}' is not in your favourites.",
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
