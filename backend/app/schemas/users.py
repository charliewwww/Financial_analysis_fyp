"""
User-related Pydantic schemas.

UserDetailSchema   — the profile stored in the user_details table.
UserUpdateRequest  — the body accepted by PATCH /api/v1/users/me.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserDetailSchema(BaseModel):
    """Full profile row as returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    username: str | None = None
    saved_sectors: list[str] = Field(default_factory=list)
    preferences: dict[str, Any] = Field(default_factory=dict)
    created_at: str
    updated_at: str | None = None


class UserUpdateRequest(BaseModel):
    """
    Body for PATCH /api/v1/users/me.

    All fields are optional — only the ones provided are updated.
    """

    username: str | None = Field(
        default=None,
        max_length=64,
        description="Display name shown in the UI.",
    )
    saved_sectors: list[str] | None = Field(
        default=None,
        description='List of sector_id values, e.g. ["semiconductors", "ev_battery"].',
    )
    preferences: dict[str, Any] | None = Field(
        default=None,
        description="Free-form UI / notification preferences object.",
    )
