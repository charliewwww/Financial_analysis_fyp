"""
Authentication dependency — Cloudflare Access identity extraction.

Cloudflare Access sits in front of every ingress request and injects:
    Cf-Access-Authenticated-User-Email: alice@example.com

This header is SIGNED and VERIFIED by Cloudflare before it reaches the
origin.  We never trust a client-supplied version of this header —
Cloudflare strips any client-set copies before forwarding.

Local development:
    Set AUTH_BYPASS_EMAIL=dev@local in your .env file.
    The dependency will return that email for every request so you don't
    need a Cloudflare tunnel running locally.

Usage in a route:
    from app.core.auth import get_current_user, CurrentUser

    @router.get("/me")
    async def me(user: CurrentUser) -> dict:
        return {"email": user}
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status

from app.core.config import settings

logger = logging.getLogger(__name__)

# The exact header name Cloudflare injects (case-insensitive in HTTP/2,
# but we register the canonical capitalisation for documentation clarity).
_CF_HEADER = "cf-access-authenticated-user-email"


async def get_current_user(
    cf_email: Annotated[
        str | None,
        Header(alias="Cf-Access-Authenticated-User-Email"),
    ] = None,
) -> str:
    """
    FastAPI dependency that returns the authenticated user's email.

    Priority:
        1. AUTH_BYPASS_EMAIL setting (local dev only — never set in prod).
        2. Cf-Access-Authenticated-User-Email header (production path).

    Raises HTTP 401 if neither source provides a non-empty email.
    """
    # ── Dev bypass ────────────────────────────────────────────────
    if settings.auth_bypass_email:
        return settings.auth_bypass_email.lower().strip()

    # ── Production: Cloudflare-injected header ────────────────────
    if not cf_email or not cf_email.strip():
        # ── Dev-mode automatic fallback ───────────────────────────
        # When APP_ENV=development (the default) and no CF header is
        # present, return test@example.com rather than raising 401.
        # This lets you run the backend locally without a Cloudflare
        # tunnel and without setting AUTH_BYPASS_EMAIL explicitly.
        # Set APP_ENV=production to disable this safety net.
        if settings.app_env == "development":
            logger.warning(
                "No Cf-Access-Authenticated-User-Email header received. "
                "Returning 'test@example.com' (APP_ENV=development fallback). "
                "Set APP_ENV=production to enforce authentication."
            )
            return "test@example.com"

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=(
                "Missing authentication. "
                "Requests must pass through Cloudflare Access."
            ),
            headers={"WWW-Authenticate": "Bearer"},
        )

    return cf_email.lower().strip()


# Convenience type alias — use this in route signatures instead of repeating
# the full Annotated[...] every time.
CurrentUser = Annotated[str, Depends(get_current_user)]
