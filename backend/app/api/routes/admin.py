"""
Admin (operator console) routes — private-beta access management.

Every endpoint here is operator-only, enforced SERVER-SIDE via the AdminUser
dependency (a user's role lives in user_details.role or the bootstrap-admin
config — never trusted from the browser).

    Invites (allow-list)
        GET    /api/v1/admin/allowlist
        POST   /api/v1/admin/allowlist
        DELETE /api/v1/admin/allowlist/{email}

    Waitlist (access requests)
        GET    /api/v1/admin/access-requests
        POST   /api/v1/admin/access-requests/{email}/approve
        POST   /api/v1/admin/access-requests/{email}/deny

    Users
        GET    /api/v1/admin/users
        POST   /api/v1/admin/users/{email}/role
        POST   /api/v1/admin/users/{email}/suspend
        POST   /api/v1/admin/users/{email}/reactivate
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncConnection

from app.core.auth import AdminUser
from app.db.engine import get_db
from app.db.repositories import auth as auth_repo
from app.db.repositories import users as user_repo
from app.schemas.admin import (
    AccessRequestSchema,
    AllowlistAddRequest,
    AllowlistEntrySchema,
    RoleUpdateRequest,
)
from app.schemas.users import UserDetailSchema

router = APIRouter(prefix="/admin", tags=["admin"])

DB = Annotated[AsyncConnection, Depends(get_db)]


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


def _allow_entry(row: dict[str, Any]) -> AllowlistEntrySchema:
    return AllowlistEntrySchema(
        email=row["email"],
        role=row.get("role", "user"),
        note=row.get("note"),
        invited_by=row.get("invited_by"),
        created_at=_iso(row.get("created_at")),
    )


def _request_entry(row: dict[str, Any]) -> AccessRequestSchema:
    return AccessRequestSchema(
        email=row["email"],
        name=row.get("name"),
        status=row["status"],
        requested_at=_iso(row.get("requested_at")),
        decided_at=_iso(row.get("decided_at")),
        decided_by=row.get("decided_by"),
    )


# ── Invites (allow-list) ───────────────────────────────────────────

@router.get("/allowlist", response_model=list[AllowlistEntrySchema])
async def list_allowlist(db: DB, admin: AdminUser) -> list[AllowlistEntrySchema]:
    rows = await auth_repo.list_allowlist(db)
    return [_allow_entry(r) for r in rows]


@router.post(
    "/allowlist",
    response_model=AllowlistEntrySchema,
    status_code=status.HTTP_201_CREATED,
)
async def add_allowlist(
    body: AllowlistAddRequest, db: DB, admin: AdminUser
) -> AllowlistEntrySchema:
    await auth_repo.add_to_allowlist(
        db, email=body.email, role=body.role, note=body.note, invited_by=admin
    )
    # Clear any matching waitlist request and apply the role to an existing user.
    await auth_repo.set_request_status(
        db, body.email, status="approved", decided_by=admin
    )
    if body.role == "admin":
        await user_repo.set_role(db, body.email, "admin")
    entry = await auth_repo.get_allow_entry(db, body.email)
    return _allow_entry(entry or {"email": body.email, "role": body.role})


@router.delete("/allowlist/{email}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_allowlist(email: str, db: DB, admin: AdminUser) -> Response:
    normalized = email.strip().lower()
    await auth_repo.remove_from_allowlist(db, normalized)
    # Revoking an invite kicks the user out of any active session immediately.
    await auth_repo.delete_user_sessions(db, normalized)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ── Waitlist (access requests) ─────────────────────────────────────

@router.get("/access-requests", response_model=list[AccessRequestSchema])
async def list_access_requests(
    db: DB,
    admin: AdminUser,
    request_status: Annotated[str | None, Query(alias="status")] = None,
) -> list[AccessRequestSchema]:
    rows = await auth_repo.list_access_requests(db, status=request_status)
    return [_request_entry(r) for r in rows]


@router.post(
    "/access-requests/{email}/approve",
    response_model=AllowlistEntrySchema,
    status_code=status.HTTP_201_CREATED,
)
async def approve_access_request(
    email: str, db: DB, admin: AdminUser
) -> AllowlistEntrySchema:
    normalized = email.strip().lower()
    await auth_repo.add_to_allowlist(db, email=normalized, role="user", invited_by=admin)
    await auth_repo.set_request_status(
        db, normalized, status="approved", decided_by=admin
    )
    entry = await auth_repo.get_allow_entry(db, normalized)
    return _allow_entry(entry or {"email": normalized, "role": "user"})


@router.post("/access-requests/{email}/deny")
async def deny_access_request(email: str, db: DB, admin: AdminUser) -> dict:
    await auth_repo.set_request_status(
        db, email.strip().lower(), status="denied", decided_by=admin
    )
    return {"ok": True}


# ── Users ──────────────────────────────────────────────────────────

@router.get("/users", response_model=list[UserDetailSchema])
async def list_users(db: DB, admin: AdminUser) -> list[UserDetailSchema]:
    return await user_repo.list_users(db)


@router.post("/users/{email}/role", response_model=UserDetailSchema)
async def set_user_role(
    email: str, body: RoleUpdateRequest, db: DB, admin: AdminUser
) -> UserDetailSchema:
    normalized = email.strip().lower()
    await user_repo.set_role(db, normalized, body.role)
    return await user_repo.get_or_create(db, normalized)


@router.post("/users/{email}/suspend", response_model=UserDetailSchema)
async def suspend_user(email: str, db: DB, admin: AdminUser) -> UserDetailSchema:
    normalized = email.strip().lower()
    await user_repo.set_status(db, normalized, "suspended")
    # Immediately revoke their sessions so suspension takes effect now.
    await auth_repo.delete_user_sessions(db, normalized)
    return await user_repo.get_or_create(db, normalized)


@router.post("/users/{email}/reactivate", response_model=UserDetailSchema)
async def reactivate_user(email: str, db: DB, admin: AdminUser) -> UserDetailSchema:
    normalized = email.strip().lower()
    await user_repo.set_status(db, normalized, "active")
    return await user_repo.get_or_create(db, normalized)
