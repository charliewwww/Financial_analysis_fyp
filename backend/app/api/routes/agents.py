"""Agent catalog routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncConnection

from app.core.auth import CurrentUser
from app.db.engine import get_db
from app.db.repositories import agents as agent_repo
from app.schemas.agents import AgentCreateRequest, AgentSummarySchema


router = APIRouter(prefix="/agents", tags=["agents"])
DB = Annotated[AsyncConnection, Depends(get_db)]


@router.get("", response_model=list[AgentSummarySchema], summary="List agents")
async def list_agents(db: DB) -> list[AgentSummarySchema]:
    """Return public metadata for built-in and user-created agents."""
    return await agent_repo.list_agents(db)


@router.post(
    "",
    response_model=AgentSummarySchema,
    status_code=status.HTTP_201_CREATED,
    summary="Create custom skill agent",
)
async def create_agent_skill(
    body: AgentCreateRequest,
    db: DB,
    _user: CurrentUser,
) -> AgentSummarySchema:
    """Create a custom analyst agent from a user-authored domain skill."""
    try:
        return await agent_repo.create_agent_with_skill(
            db,
            name=body.name,
            description=body.description,
            skill_name=body.skill_name,
            skill_type=body.skill_type,
            skill_content=body.skill_content,
        )
    except IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Agent {body.name!r} already exists.",
        ) from exc