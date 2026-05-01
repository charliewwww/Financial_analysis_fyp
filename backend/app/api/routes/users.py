"""
Users router — profile management for authenticated users.

Endpoints:
    GET   /api/v1/users/me          Fetch the current user's profile
    PATCH /api/v1/users/me          Update username, saved sectors, or preferences
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncConnection
from typing import Annotated

from app.core.auth import CurrentUser
from app.db.engine import get_db
from app.db.repositories import users as user_repo
from app.schemas.users import UserDetailSchema, UserUpdateRequest

router = APIRouter(prefix="/users", tags=["users"])

DB = Annotated[AsyncConnection, Depends(get_db)]


@router.get(
    "/me",
    response_model=UserDetailSchema,
    summary="Get my profile",
    description=(
        "Returns the profile for the authenticated user. "
        "A blank profile is created automatically on the first call."
    ),
)
async def get_me(db: DB, user: CurrentUser) -> UserDetailSchema:
    return await user_repo.get_or_create(db, user)


@router.patch(
    "/me",
    response_model=UserDetailSchema,
    summary="Update my profile",
    description=(
        "Partial update — only fields present in the request body are changed. "
        "Omitted fields are left unchanged."
    ),
)
async def update_me(
    body: UserUpdateRequest,
    db: DB,
    user: CurrentUser,
) -> UserDetailSchema:
    # Ensure the row exists before updating
    await user_repo.get_or_create(db, user)
    return await user_repo.update_profile(
        db,
        user,
        username=body.username,
        saved_sectors=body.saved_sectors,
        preferences=body.preferences,
    )
