"""Schemas for MarketPulse analyst agents."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


# High-precision markers that signal an attempt to override the system prompt
# (prompt injection) rather than describe an analytical lens. Kept deliberately
# narrow to minimise false positives; the prompt-assembly layer isolates the
# persona as defence-in-depth.
_INJECTION_MARKERS = (
    "ignore previous instruction",
    "ignore all previous",
    "ignore the above",
    "disregard previous",
    "disregard the system",
    "disregard all prior",
    "override the system",
    "reveal your system prompt",
    "print your system prompt",
    "show your system prompt",
    "system prompt:",
    "you are now",
    "act as the system",
    "<|im_start|>",
    "<|im_end|>",
    "<system>",
    "</system>",
    "begin system",
)


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
        # Strip control + zero-width characters (defuse hidden-instruction
        # tricks), keeping only newlines/tabs and printable text.
        cleaned = "".join(
            ch for ch in value
            if ch in ("\n", "\t") or (32 <= ord(ch) != 0x7F)
        )
        for zw in ("\u200b", "\u200c", "\u200d", "\u200e", "\u202e", "\ufeff"):
            cleaned = cleaned.replace(zw, "")
        cleaned = cleaned.strip()
        if len(cleaned) < 40:
            raise ValueError("Skill content must be at least 40 characters.")
        lowered = cleaned.lower()
        if any(marker in lowered for marker in _INJECTION_MARKERS):
            raise ValueError(
                "Agent instructions look like an attempt to override the system "
                "(prompt injection). Describe the analytical lens and focus areas "
                "instead."
            )
        return cleaned