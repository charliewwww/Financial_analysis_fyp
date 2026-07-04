"""
Watchlist schemas — the user's "My Favourites" tickers.

One row per (user_email, ticker). Powers the favourites list and the
"run all favourites" one-click fan-out on the Decision Desk.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class WatchlistItemSchema(BaseModel):
    """A single saved favourite ticker."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    ticker: str
    notes: str | None = None
    sector_id: str | None = None
    added_at: str = ""


class WatchlistAddRequest(BaseModel):
    """Add a ticker to the user's favourites."""

    ticker: str = Field(min_length=1, max_length=20)
    notes: str | None = Field(default=None, max_length=500)
    sector_id: str | None = Field(default=None, max_length=64)
