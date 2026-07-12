"""
Authentication routes — Google OIDC sign-in, sign-out, and a config probe.

Flow:
    GET  /api/v1/auth/login     → redirect the browser to Google.
    GET  /api/v1/auth/callback  → Google returns here. We verify the identity,
                                  create a server-side session, set an HttpOnly
                                  cookie, and redirect back to the frontend.
    POST /api/v1/auth/logout    → revoke the session and clear the cookie.
    GET  /api/v1/auth/config    → public: tells the login page whether Google
                                  sign-in is configured.

Identity is delegated to Google; the *session* is ours (opaque token, stored
hashed in user_sessions). Sign-in is open: anyone with a verified Google
account gets in and receives their own private workspace.
"""

from __future__ import annotations

import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Annotated
from urllib.parse import urlencode

from authlib.integrations.starlette_client import OAuthError
from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncConnection

from app.core.auth import SIGNED_OUT_COOKIE, hash_token
from app.core.config import settings
from app.core.oauth import google_configured, oauth
from app.db.engine import get_db
from app.db.repositories import auth as auth_repo
from app.db.repositories import users as user_repo
from app.schemas.admin import SignupRequest

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])

DB = Annotated[AsyncConnection, Depends(get_db)]


# ── Helpers ────────────────────────────────────────────────────────

def _callback_url(request: Request) -> str:
    """Absolute URL Google should redirect back to (must match the console)."""
    base = (
        settings.backend_base_url.rstrip("/")
        if settings.backend_base_url
        else str(request.base_url).rstrip("/")
    )
    return f"{base}/api/v1/auth/callback"


def _frontend(path: str = "/", **params: str) -> str:
    """Build a frontend URL with optional query params."""
    url = f"{settings.frontend_base_url.rstrip('/')}{path}"
    if params:
        url += "?" + urlencode(params)
    return url


def _set_session_cookie(response: Response, raw_token: str) -> None:
    response.set_cookie(
        key=settings.session_cookie_name,
        value=raw_token,
        max_age=settings.session_ttl_days * 24 * 3600,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        domain=settings.cookie_domain or None,
        path="/",
    )
    # A fresh login overrides any prior "signed out" marker in this browser.
    response.delete_cookie(
        key=SIGNED_OUT_COOKIE, domain=settings.cookie_domain or None, path="/"
    )


def _dev_login_available() -> bool:
    """True when the development auto-login affordance applies."""
    return settings.app_env == "development" and not settings.auth_bypass_email


# ── Routes ─────────────────────────────────────────────────────────

@router.get("/config", summary="Is Google sign-in configured?")
async def auth_config() -> dict:
    """Public probe so the login page can show the right UI."""
    return {
        "google_configured": google_configured(),
        "dev_login_available": _dev_login_available(),
    }


@router.get("/login", summary="Begin Google sign-in")
async def auth_login(request: Request):
    if not google_configured():
        return RedirectResponse(_frontend("/login", error="not_configured"))
    return await oauth.google.authorize_redirect(request, _callback_url(request))


@router.get("/callback", summary="Google OIDC callback")
async def auth_callback(request: Request, db: DB):
    if not google_configured():
        return RedirectResponse(_frontend("/login", error="not_configured"))

    try:
        token = await oauth.google.authorize_access_token(request)
    except OAuthError:
        logger.warning("Google OAuth token exchange failed", exc_info=True)
        return RedirectResponse(_frontend("/login", error="oauth_failed"))

    userinfo = token.get("userinfo") or {}
    email = (userinfo.get("email") or "").lower().strip()
    if not email or not userinfo.get("email_verified", False):
        return RedirectResponse(_frontend("/login", error="email_unverified"))

    name = userinfo.get("name")
    picture = userinfo.get("picture")

    # Open sign-in: any verified Google account is welcome and receives its own
    # private workspace. Bootstrap-operator emails are granted admin; everyone
    # else signs in as a normal user.
    role: str | None = "admin" if email in settings.bootstrap_admin_emails else None

    await user_repo.record_login(
        db, email, role=role, picture=picture, username=name
    )

    # A suspended account may not start a session.
    user = await user_repo.get_by_email(db, email)
    if user and user.status == "suspended":
        return RedirectResponse(_frontend("/login", error="suspended"))

    # ── Issue the session ─────────────────────────────────────────
    raw_token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.session_ttl_days)
    await auth_repo.create_session(
        db,
        token_hash=hash_token(raw_token),
        user_email=email,
        expires_at=expires_at,
        user_agent=request.headers.get("user-agent"),
    )

    response = RedirectResponse(_frontend("/"))
    _set_session_cookie(response, raw_token)
    return response


@router.post("/logout", summary="Sign out (revoke this session)")
async def auth_logout(request: Request, db: DB) -> Response:
    token = request.cookies.get(settings.session_cookie_name)
    if token:
        await auth_repo.delete_session(db, hash_token(token))
    response = JSONResponse({"ok": True})
    response.delete_cookie(
        key=settings.session_cookie_name,
        domain=settings.cookie_domain or None,
        path="/",
    )
    # In development there is no real identity provider, so without a marker the
    # auto-login fallback would immediately sign the user back in. Set it so the
    # sign-out actually sticks; a later login clears it.
    response.set_cookie(
        key=SIGNED_OUT_COOKIE,
        value="1",
        max_age=settings.session_ttl_days * 24 * 3600,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        domain=settings.cookie_domain or None,
        path="/",
    )
    return response


@router.get("/dev-login", summary="Development-only auto sign-in")
async def auth_dev_login() -> Response:
    """
    Clear the sign-out marker so the development auto-login fallback applies
    again, then bounce to the app. Disabled outside development.
    """
    if not _dev_login_available():
        return RedirectResponse(_frontend("/login", error="not_configured"))
    response = RedirectResponse(_frontend("/"))
    response.delete_cookie(
        key=SIGNED_OUT_COOKIE, domain=settings.cookie_domain or None, path="/"
    )
    return response


@router.post("/signup", summary="Sign up (open access)")
async def auth_signup(body: SignupRequest) -> dict:
    """
    Kept for backwards compatibility with the Create Account page.

    Sign-in is open — anyone with a verified Google account gets in and receives
    their own private workspace — so there is no waitlist or approval step. We
    simply direct the visitor to continue with Google.
    """
    return {
        "ok": True,
        "status": "open",
        "message": (
            f"No approval needed for {body.email.strip().lower()} — "
            "continue with Google to create your account."
        ),
    }
