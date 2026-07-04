"""
Authentication & authorization dependencies — self-hosted Google OIDC sessions.

Identity is established by Google sign-in (see app/core/oauth.py and
app/api/routes/auth.py). Our backend then issues an opaque session token in an
HttpOnly cookie and is the *sole* authority for every request — the cookie value
is random, and only its SHA-256 hash is stored (in user_sessions).

get_current_user resolution order:
    1. AUTH_BYPASS_EMAIL    — local development / test convenience only.
    2. Session cookie        — the real path (validated against user_sessions,
                               and the user must still be 'active').
    3. APP_ENV=development   — returns a dev identity so the API is usable
                               locally without configuring Google. Never fires
                               when APP_ENV=production.
    4. Otherwise             → HTTP 401.

Authorization:
    require_admin enforces the operator role SERVER-SIDE (user_details.role, or
    the configured bootstrap-admin list) — never trusting the browser.

Usage in a route:
    from app.core.auth import CurrentUser, AdminUser

    @router.get("/me")
    async def me(user: CurrentUser) -> dict:
        return {"email": user}

    @router.get("/ops")
    async def ops(admin: AdminUser) -> dict:
        return {"operator": admin}
"""

from __future__ import annotations

import hashlib
import logging
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncConnection

from app.core.config import settings
from app.db.engine import get_db
from app.db.repositories import auth as auth_repo
from app.db.repositories import users as user_repo

logger = logging.getLogger(__name__)

# Identity returned in development when no session cookie is present. This can
# never be reached when APP_ENV=production.
DEV_FALLBACK_EMAIL = "test@example.com"

# A non-sensitive marker cookie set on logout. In development it suppresses the
# auto-login fallback below, so "Sign out" is honoured even without Google
# configured. Cleared on a fresh login (or dev-login).
SIGNED_OUT_COOKIE = "mp_signed_out"


def hash_token(raw_token: str) -> str:
    """SHA-256 hex digest of a raw session token — what we store and look up."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


async def _email_from_session(db: AsyncConnection, raw_token: str) -> str | None:
    """Resolve a session-cookie value to an active user's email, or None."""
    token_hash = hash_token(raw_token)
    session = await auth_repo.get_valid_session(db, token_hash)
    if session is None:
        return None
    email = session["user_email"]
    user = await user_repo.get_by_email(db, email)
    if user is None or user.status != "active":
        # Suspended/removed user — the session is no longer honoured.
        return None
    await auth_repo.touch_session(db, token_hash)
    return email


async def get_current_user(
    request: Request,
    db: Annotated[AsyncConnection, Depends(get_db)],
) -> str:
    """FastAPI dependency returning the authenticated user's email."""
    # 1. Dev/test bypass
    if settings.auth_bypass_email:
        return settings.auth_bypass_email.lower().strip()

    # 2. Session cookie (the real path)
    token = request.cookies.get(settings.session_cookie_name)
    if token:
        email = await _email_from_session(db, token)
        if email:
            return email

    # 3. Development fallback (never fires in production, nor after an explicit
    #    sign-out in this browser).
    if settings.app_env == "development" and not request.cookies.get(SIGNED_OUT_COOKIE):
        logger.warning(
            "No valid session cookie; returning '%s' (APP_ENV=development "
            "fallback). Set APP_ENV=production to enforce authentication.",
            DEV_FALLBACK_EMAIL,
        )
        return DEV_FALLBACK_EMAIL

    # 4. Reject
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated. Please sign in.",
        headers={"WWW-Authenticate": "Cookie"},
    )


# Convenience type alias — use this in route signatures.
CurrentUser = Annotated[str, Depends(get_current_user)]


async def is_admin(db: AsyncConnection, email: str) -> bool:
    """True if *email* is an operator (bootstrap-admin list or stored role)."""
    if email.lower().strip() in settings.bootstrap_admin_emails:
        return True
    user = await user_repo.get_by_email(db, email)
    return bool(user and user.role == "admin")


async def require_admin(
    db: Annotated[AsyncConnection, Depends(get_db)],
    user: CurrentUser,
) -> str:
    """FastAPI dependency that allows only operators through (server-enforced)."""
    if not await is_admin(db, user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operator access required.",
        )
    return user


# Convenience type alias for operator-only routes.
AdminUser = Annotated[str, Depends(require_admin)]
