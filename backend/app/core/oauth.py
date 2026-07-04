"""
Google OIDC client (Authlib).

We delegate "who is this person?" to Google via OpenID Connect, then our own
backend issues and owns the session (see app/core/auth.py). No passwords are
stored anywhere.

The client is registered lazily: if Google credentials and a session secret are
not configured, `google_configured()` returns False and the auth routes fall
back to a clear "sign-in not configured" response (local dev uses the
AUTH_BYPASS_EMAIL / development fallback instead).
"""

from __future__ import annotations

from authlib.integrations.starlette_client import OAuth

from app.core.config import settings

# Google publishes its endpoints + JWKS here; Authlib fetches and caches them,
# and validates the ID-token signature + nonce for us.
GOOGLE_METADATA_URL = "https://accounts.google.com/.well-known/openid-configuration"

oauth = OAuth()


def google_configured() -> bool:
    """True when Google OAuth and the session secret are all configured."""
    return bool(
        settings.google_client_id
        and settings.google_client_secret
        and settings.session_secret_key
    )


def _register_google() -> None:
    oauth.register(
        name="google",
        server_metadata_url=GOOGLE_METADATA_URL,
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
        client_kwargs={"scope": "openid email profile"},
    )


# Register at import time when configured so `oauth.google` is ready to use.
if google_configured():
    _register_google()
