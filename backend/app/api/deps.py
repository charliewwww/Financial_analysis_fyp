"""
Route dependency re-exports.

All routes can import shared FastAPI dependencies from here rather than
reaching into core/ directly.  New dependencies (rate limiting, pagination,
query parsing, etc.) should be added here over time.

Usage in a route:
    from app.api.deps import CurrentUser, get_current_user

    @router.get("/me")
    async def me(user: CurrentUser) -> dict:
        return {"email": user}
"""

from app.core.auth import CurrentUser, get_current_user  # noqa: F401

__all__ = ["CurrentUser", "get_current_user"]
