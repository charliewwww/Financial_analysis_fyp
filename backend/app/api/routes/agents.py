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
async def list_agents(db: DB, user: CurrentUser) -> list[AgentSummarySchema]:
    """Return the built-in agents plus the caller's own custom agents."""
    return await agent_repo.list_agents(db, user_email=user)


@router.post(
    "",
    response_model=AgentSummarySchema,
    status_code=status.HTTP_201_CREATED,
    summary="Create custom skill agent",
)
async def create_agent_skill(
    body: AgentCreateRequest,
    db: DB,
    user: CurrentUser,
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
            user_email=user,
        )
    except IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Agent {body.name!r} already exists.",
        ) from exc


@router.delete(
    "/{agent_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    # This module uses ``from __future__ import annotations``, so the ``-> None``
    # return annotation reaches FastAPI 0.115.x as the string "None", which it
    # resolves to ``NoneType`` (truthy) and mistakes for a response body on a
    # 204 route. Passing ``response_model=None`` explicitly skips that inference.
    response_model=None,
    summary="Delete a custom agent",
)
async def delete_agent(agent_id: int, db: DB, user: CurrentUser) -> None:
    """Delete one of the caller's own custom agents.

    Built-in agents and agents owned by other users cannot be deleted; both
    respond with 404 so an agent's existence is never revealed cross-user.
    """
    deleted = await agent_repo.delete_agent(db, agent_id, user_email=user)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Custom agent not found.",
        )