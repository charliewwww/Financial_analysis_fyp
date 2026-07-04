"""
Admin (operator console) schemas — invites, waitlist, and user management.

We deliberately avoid pydantic's EmailStr (which pulls in the optional
email-validator dependency) and do a light, dependency-free email check, since
these endpoints are operator-only and the email is normalized server-side.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


def _validate_email(value: str) -> str:
    v = value.strip().lower()
    parts = v.split("@")
    if len(parts) != 2 or not parts[0] or "." not in parts[1]:
        raise ValueError("Enter a valid email address.")
    return v


class AllowlistEntrySchema(BaseModel):
    """An invited email on the private-beta allow-list."""

    email: str
    role: str = "user"
    note: str | None = None
    invited_by: str | None = None
    created_at: str | None = None


class AllowlistAddRequest(BaseModel):
    """Body for inviting an email to the private beta."""

    email: str = Field(min_length=3, max_length=254)
    role: Literal["user", "admin"] = "user"
    note: str | None = Field(default=None, max_length=240)

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        return _validate_email(v)


class AccessRequestSchema(BaseModel):
    """A not-yet-invited sign-in attempt sitting on the waitlist."""

    email: str
    name: str | None = None
    status: str
    requested_at: str | None = None
    decided_at: str | None = None
    decided_by: str | None = None


class RoleUpdateRequest(BaseModel):
    role: Literal["user", "admin"]
