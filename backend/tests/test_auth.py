"""
Authentication & authorization tests.

Covers the self-hosted Google-OIDC session model end-to-end at the repository
and dependency level against a real in-memory SQLite DB (the `db` fixture):

  * session lifecycle (create / validate / expire / revoke)
  * cookie-based get_current_user (active vs suspended, prod 401)
  * server-side require_admin (admin / non-admin / bootstrap)
  * invite allow-list + waitlist (access_requests)
  * multi-user session isolation
  * the per-user daily free-analysis quota (operators exempt)
  * the production startup guardrail (refuses to boot without real auth)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.core import auth as auth_core
from app.core.auth import (
    SIGNED_OUT_COOKIE,
    get_current_user,
    hash_token,
    is_admin,
    require_admin,
)
from app.db.repositories import auth as auth_repo
from app.db.repositories import signals as signal_repo
from app.db.repositories import users as user_repo
from app.api.routes import pipeline as pipeline_routes
from app.api.routes import users as users_routes


# ── Helpers ────────────────────────────────────────────────────────

def _request_with_cookies(**cookies: str) -> Request:
    header = "; ".join(f"{k}={v}" for k, v in cookies.items()).encode()
    return Request(
        {"type": "http", "path": "/", "query_string": b"", "headers": [(b"cookie", header)]}
    )


def _request_with_cookie(name: str, token: str) -> Request:
    header = f"{name}={token}".encode()
    return Request(
        {"type": "http", "path": "/", "query_string": b"", "headers": [(b"cookie", header)]}
    )


def _request_no_cookie() -> Request:
    return Request({"type": "http", "path": "/", "query_string": b"", "headers": []})


def _future() -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=1)


def _past() -> datetime:
    return datetime.now(timezone.utc) - timedelta(seconds=5)


# ── Sessions ───────────────────────────────────────────────────────

async def test_create_and_validate_session(db):
    await user_repo.get_or_create(db, "alice@example.com")
    raw = "tok-alice"
    await auth_repo.create_session(
        db, token_hash=hash_token(raw), user_email="alice@example.com", expires_at=_future()
    )
    session = await auth_repo.get_valid_session(db, hash_token(raw))
    assert session is not None
    assert session["user_email"] == "alice@example.com"


async def test_expired_session_is_rejected(db):
    await user_repo.get_or_create(db, "bob@example.com")
    raw = "tok-bob"
    await auth_repo.create_session(
        db, token_hash=hash_token(raw), user_email="bob@example.com", expires_at=_past()
    )
    assert await auth_repo.get_valid_session(db, hash_token(raw)) is None


async def test_only_token_hash_is_stored(db):
    # The raw token must never be recoverable from the DB.
    await user_repo.get_or_create(db, "h@example.com")
    raw = "super-secret-token"
    await auth_repo.create_session(
        db, token_hash=hash_token(raw), user_email="h@example.com", expires_at=_future()
    )
    # Looking up by the raw token (not its hash) must miss.
    assert await auth_repo.get_valid_session(db, raw) is None
    assert await auth_repo.get_valid_session(db, hash_token(raw)) is not None


async def test_logout_revokes_session(db):
    await user_repo.get_or_create(db, "c@example.com")
    raw = "tok-c"
    await auth_repo.create_session(
        db, token_hash=hash_token(raw), user_email="c@example.com", expires_at=_future()
    )
    await auth_repo.delete_session(db, hash_token(raw))
    assert await auth_repo.get_valid_session(db, hash_token(raw)) is None


# ── get_current_user (cookie path) ─────────────────────────────────

async def test_get_current_user_from_cookie(db):
    await user_repo.record_login(db, "carol@example.com")
    raw = "tok-carol"
    await auth_repo.create_session(
        db, token_hash=hash_token(raw), user_email="carol@example.com", expires_at=_future()
    )
    with (
        patch.object(auth_core.settings, "auth_bypass_email", ""),
        patch.object(auth_core.settings, "app_env", "production"),
    ):
        req = _request_with_cookie(auth_core.settings.session_cookie_name, raw)
        email = await get_current_user(req, db)
    assert email == "carol@example.com"


async def test_suspended_user_cannot_authenticate(db):
    await user_repo.record_login(db, "dave@example.com")
    await user_repo.set_status(db, "dave@example.com", "suspended")
    raw = "tok-dave"
    await auth_repo.create_session(
        db, token_hash=hash_token(raw), user_email="dave@example.com", expires_at=_future()
    )
    with (
        patch.object(auth_core.settings, "auth_bypass_email", ""),
        patch.object(auth_core.settings, "app_env", "production"),
    ):
        req = _request_with_cookie(auth_core.settings.session_cookie_name, raw)
        with pytest.raises(HTTPException) as exc:
            await get_current_user(req, db)
    assert exc.value.status_code == 401


async def test_no_cookie_in_production_is_401(db):
    with (
        patch.object(auth_core.settings, "auth_bypass_email", ""),
        patch.object(auth_core.settings, "app_env", "production"),
    ):
        with pytest.raises(HTTPException) as exc:
            await get_current_user(_request_no_cookie(), db)
    assert exc.value.status_code == 401


async def test_bypass_email_short_circuits(db):
    with patch.object(auth_core.settings, "auth_bypass_email", "Dev@Example.com "):
        email = await get_current_user(_request_no_cookie(), db)
    assert email == "dev@example.com"


async def test_dev_fallback_returns_dev_identity(db):
    with (
        patch.object(auth_core.settings, "auth_bypass_email", ""),
        patch.object(auth_core.settings, "app_env", "development"),
    ):
        email = await get_current_user(_request_no_cookie(), db)
    assert email == auth_core.DEV_FALLBACK_EMAIL


async def test_signed_out_marker_suppresses_dev_fallback(db):
    # After an explicit sign-out, the dev auto-login must NOT re-authenticate.
    with (
        patch.object(auth_core.settings, "auth_bypass_email", ""),
        patch.object(auth_core.settings, "app_env", "development"),
    ):
        req = _request_with_cookies(**{SIGNED_OUT_COOKIE: "1"})
        with pytest.raises(HTTPException) as exc:
            await get_current_user(req, db)
    assert exc.value.status_code == 401


# ── require_admin (server-side authorization) ──────────────────────

async def test_require_admin_allows_admin_and_blocks_user(db):
    await user_repo.record_login(db, "ops@example.com", role="admin")
    await user_repo.get_or_create(db, "plain@example.com")
    with patch.object(auth_core.settings, "auth_bootstrap_admin_emails", ""):
        assert await require_admin(db=db, user="ops@example.com") == "ops@example.com"
        with pytest.raises(HTTPException) as exc:
            await require_admin(db=db, user="plain@example.com")
    assert exc.value.status_code == 403


async def test_bootstrap_admin_is_admin_without_db_row(db):
    with patch.object(auth_core.settings, "auth_bootstrap_admin_emails", "founder@example.com"):
        assert await is_admin(db, "founder@example.com") is True
        assert await is_admin(db, "someone@example.com") is False


async def test_users_me_reflects_bootstrap_admin(db):
    # A bootstrap operator should read back as role='admin' from /users/me so the
    # UI's admin surfaces match what the server authorizes.
    with patch.object(users_routes.settings, "auth_bootstrap_admin_emails", "founder@example.com"):
        profile = await users_routes.get_me(db=db, user="founder@example.com")
    assert profile.role == "admin"


# ── Allow-list + waitlist ──────────────────────────────────────────

async def test_allowlist_and_waitlist_flow(db):
    assert await auth_repo.is_allowed(db, "x@example.com") is False

    # Not-yet-invited sign-in lands on the waitlist.
    await auth_repo.upsert_access_request(db, email="x@example.com", name="X User")
    pending = await auth_repo.list_access_requests(db, status="pending")
    assert any(r["email"] == "x@example.com" for r in pending)

    # Approving moves them onto the allow-list and clears the request.
    await auth_repo.add_to_allowlist(db, email="x@example.com", invited_by="ops@example.com")
    await auth_repo.set_request_status(db, "x@example.com", status="approved", decided_by="ops@example.com")
    assert await auth_repo.is_allowed(db, "x@example.com") is True
    assert all(
        r["email"] != "x@example.com"
        for r in await auth_repo.list_access_requests(db, status="pending")
    )

    # Revoking the invite removes them.
    await auth_repo.remove_from_allowlist(db, "x@example.com")
    assert await auth_repo.is_allowed(db, "x@example.com") is False


async def test_allowlist_can_preassign_admin_role(db):
    await auth_repo.add_to_allowlist(db, email="boss@example.com", role="admin")
    entry = await auth_repo.get_allow_entry(db, "boss@example.com")
    assert entry is not None and entry["role"] == "admin"


# ── Multi-user isolation ───────────────────────────────────────────

async def test_session_isolation_between_users(db):
    await user_repo.get_or_create(db, "u1@example.com")
    await user_repo.get_or_create(db, "u2@example.com")
    await auth_repo.create_session(db, token_hash=hash_token("t1"), user_email="u1@example.com", expires_at=_future())
    await auth_repo.create_session(db, token_hash=hash_token("t2"), user_email="u2@example.com", expires_at=_future())

    s1 = await auth_repo.get_valid_session(db, hash_token("t1"))
    s2 = await auth_repo.get_valid_session(db, hash_token("t2"))
    assert s1 is not None and s1["user_email"] == "u1@example.com"
    assert s2 is not None and s2["user_email"] == "u2@example.com"

    # Revoking u1's sessions leaves u2 untouched.
    await auth_repo.delete_user_sessions(db, "u1@example.com")
    assert await auth_repo.get_valid_session(db, hash_token("t1")) is None
    assert await auth_repo.get_valid_session(db, hash_token("t2")) is not None


# ── Daily free-analysis quota ──────────────────────────────────────

async def test_count_runs_since_counts_only_this_user(db):
    await signal_repo.create_run(db, "ra", "NVDA", "ai_semiconductors", user_email="me@example.com")
    await signal_repo.create_run(db, "rb", "AMD", "ai_semiconductors", user_email="me@example.com")
    await signal_repo.create_run(db, "rc", "TSM", "ai_semiconductors", user_email="other@example.com")
    start = datetime.now(timezone.utc) - timedelta(hours=1)
    assert await signal_repo.count_runs_since(db, user_email="me@example.com", since=start) == 2
    assert await signal_repo.count_runs_since(db, user_email="other@example.com", since=start) == 1


async def test_daily_quota_blocks_when_exceeded(db):
    user = "quota@example.com"
    await user_repo.get_or_create(db, user)
    await signal_repo.create_run(db, "q1", "NVDA", "ai_semiconductors", user_email=user)
    await signal_repo.create_run(db, "q2", "AMD", "ai_semiconductors", user_email=user)
    with (
        patch.object(pipeline_routes.settings, "daily_run_quota", 2),
        patch.object(pipeline_routes.settings, "auth_bootstrap_admin_emails", ""),
    ):
        with pytest.raises(HTTPException) as exc:
            await pipeline_routes._enforce_run_quota(db, user, additional=1)
    assert exc.value.status_code == 429


async def test_daily_quota_exempts_operators(db):
    user = "adminquota@example.com"
    await user_repo.record_login(db, user, role="admin")
    await signal_repo.create_run(db, "aq1", "NVDA", "ai_semiconductors", user_email=user)
    await signal_repo.create_run(db, "aq2", "AMD", "ai_semiconductors", user_email=user)
    with (
        patch.object(pipeline_routes.settings, "daily_run_quota", 1),
        patch.object(pipeline_routes.settings, "auth_bootstrap_admin_emails", ""),
    ):
        # Operator is exempt — this must not raise even though they're over.
        await pipeline_routes._enforce_run_quota(db, user, additional=5)


# ── Production startup guardrail ───────────────────────────────────

async def test_production_refuses_to_start_without_auth_config():
    import app.main as main_mod

    with (
        patch.object(main_mod.settings, "app_env", "production"),
        patch.object(main_mod.settings, "auth_bypass_email", ""),
        patch.object(main_mod.settings, "google_client_id", ""),
        patch.object(main_mod.settings, "google_client_secret", ""),
        patch.object(main_mod.settings, "session_secret_key", ""),
    ):
        with pytest.raises(RuntimeError):
            async with main_mod.lifespan(main_mod.app):
                pass


# ── Stale-run reconciliation ("stuck for years" fix) ───────────────

async def test_fail_stale_runs_fails_all_in_flight(db):
    await signal_repo.create_run(db, "s1", "NVDA", "ai_semiconductors", user_email="u@example.com")
    await signal_repo.create_run(db, "s2", "AMD", "ai_semiconductors", user_email="u@example.com")
    await signal_repo.update_run_status(db, "s2", status="running")
    await signal_repo.create_run(db, "s3", "TSM", "ai_semiconductors", user_email="u@example.com")
    await signal_repo.update_run_status(db, "s3", status="completed")

    # No threshold → reconcile ALL pending/running (the startup orphan sweep).
    failed = await signal_repo.fail_stale_runs(db)
    assert failed == 2

    assert (await signal_repo.get_run(db, "s1")).status == "failed"
    assert (await signal_repo.get_run(db, "s2")).status == "failed"
    # A finished run is never touched.
    assert (await signal_repo.get_run(db, "s3")).status == "completed"


async def test_fail_stale_runs_respects_age_threshold(db):
    # A brand-new run must survive the periodic reaper's age filter.
    await signal_repo.create_run(db, "fresh", "NVDA", "ai_semiconductors", user_email="u@example.com")
    await signal_repo.update_run_status(db, "fresh", status="running")

    failed = await signal_repo.fail_stale_runs(db, older_than_minutes=30)
    assert failed == 0
    assert (await signal_repo.get_run(db, "fresh")).status == "running"
