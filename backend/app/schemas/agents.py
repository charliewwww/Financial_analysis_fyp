"""Schemas for MarketPulse analyst agents."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AgentSummarySchema(BaseModel):
    """Public agent metadata shown in the agent gallery."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None = None
    is_builtin: bool = False
    created_at: str
    updated_at: str | None = None


class AgentRuntimeSchema(AgentSummarySchema):
    """Internal runtime shape used by the pipeline router."""

    identity_layer: str = ""


class AgentCreateRequest(BaseModel):
    """Create a custom analyst agent backed by one domain skill."""

    name: str = Field(min_length=3, max_length=80)
    description: str | None = Field(default=None, max_length=300)
    skill_name: str | None = Field(default=None, max_length=80)
    skill_type: Literal["domain"] = "domain"
    skill_content: str = Field(min_length=40, max_length=6000)

    @field_validator("name", "skill_name", "description", mode="before")
    @classmethod
    def _strip_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return value
        cleaned = str(value).strip()
        return cleaned or None

    @field_validator("name")
    @classmethod
    def _name_required(cls, value: str | None) -> str:
        if not value:
            raise ValueError("Agent name is required.")
        return value

    @field_validator("skill_content")
    @classmethod
    def _skill_content_required(cls, value: str) -> str:
        cleaned = value.strip()
        if len(cleaned) < 40:
            raise ValueError("Skill content must be at least 40 characters.")
        return cleaned