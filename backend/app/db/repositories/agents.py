"""Repository helpers for MarketPulse analyst agents."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import insert, select, update
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from app.core.builtin_agents import BUILTIN_AGENTS, DEFAULT_AGENT_NAME
from app.db.tables import agents, skills
from app.schemas.agents import AgentRuntimeSchema, AgentSummarySchema


def _normalize_ts(value: Any) -> str:
    if value is None:
        return ""
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


def _row_to_runtime(row: Any, *, identity_layer: str | None = None) -> AgentRuntimeSchema:
    data = dict(row)
    data["created_at"] = _normalize_ts(data.get("created_at"))
    updated = _normalize_ts(data.get("updated_at"))
    data["updated_at"] = updated or None
    data["identity_layer"] = identity_layer if identity_layer is not None else data.get("identity_layer") or ""
    return AgentRuntimeSchema.model_validate(data)


def _runtime_to_summary(agent: AgentRuntimeSchema) -> AgentSummarySchema:
    return AgentSummarySchema.model_validate(agent.model_dump(exclude={"identity_layer"}))


def _agent_columns() -> tuple[Any, ...]:
    return (
        agents.c.id,
        agents.c.name,
        agents.c.description,
        agents.c.identity_layer,
        agents.c.is_builtin,
        agents.c.created_at,
        agents.c.updated_at,
    )


async def _skill_rows_for_agent(db: AsyncConnection, agent_id: int) -> list[Any]:
    return (
        await db.execute(
            select(
                skills.c.name,
                skills.c.skill_type,
                skills.c.content,
                skills.c.version,
            )
            .where(skills.c.agent_id == agent_id)
            .order_by(skills.c.id.asc())
        )
    ).mappings().all()


def _compose_identity_layer(base_identity: str | None, skill_rows: list[Any]) -> str:
    parts: list[str] = []
    if base_identity and base_identity.strip():
        parts.append(base_identity.strip())

    if skill_rows:
        skill_docs = []
        for row in skill_rows:
            skill_docs.append(
                f"### {row['name']} v{row['version']} ({row['skill_type']})\n"
                f"{str(row['content']).strip()}"
            )
        parts.append(
            "## Attached Analyst Skills\n"
            "Use these skills as the agent's specialist lens. They change emphasis, "
            "not the MarketPulse evidence standard or output schema.\n\n"
            + "\n\n".join(skill_docs)
        )

    return "\n\n".join(parts)


async def _row_to_runtime_with_skills(db: AsyncConnection, row: Any) -> AgentRuntimeSchema:
    skill_rows = await _skill_rows_for_agent(db, int(row["id"]))
    identity_layer = _compose_identity_layer(row.get("identity_layer"), skill_rows)
    return _row_to_runtime(row, identity_layer=identity_layer)


async def ensure_builtin_agents(db: AsyncConnection) -> None:
    """Create or refresh the built-in agent rows idempotently."""
    now = datetime.now(timezone.utc)
    for definition in BUILTIN_AGENTS:
        existing = (
            await db.execute(
                select(agents.c.id).where(agents.c.name == definition.name)
            )
        ).scalar_one_or_none()

        values = {
            "description": definition.description,
            "identity_layer": definition.identity_layer,
            "is_builtin": True,
        }
        if existing is None:
            await db.execute(
                insert(agents).values(
                    name=definition.name,
                    created_at=now,
                    **values,
                )
            )
        else:
            await db.execute(
                update(agents)
                .where(agents.c.id == existing)
                .values(updated_at=now, **values)
            )


async def ensure_builtin_agents_for_engine(engine: AsyncEngine) -> None:
    """Seed built-in agents during FastAPI startup."""
    async with engine.begin() as db:
        await ensure_builtin_agents(db)


async def list_agents(db: AsyncConnection) -> list[AgentSummarySchema]:
    await ensure_builtin_agents(db)
    rows = (
        await db.execute(
            select(*_agent_columns()).order_by(agents.c.is_builtin.desc(), agents.c.id.asc())
        )
    ).mappings().all()
    return [_runtime_to_summary(_row_to_runtime(row)) for row in rows]


async def get_agent(db: AsyncConnection, agent_id: int) -> AgentRuntimeSchema | None:
    await ensure_builtin_agents(db)
    row = (
        await db.execute(
            select(*_agent_columns()).where(agents.c.id == agent_id)
        )
    ).mappings().first()
    return await _row_to_runtime_with_skills(db, row) if row else None


async def get_default_agent(db: AsyncConnection) -> AgentRuntimeSchema:
    await ensure_builtin_agents(db)
    row = (
        await db.execute(
            select(*_agent_columns()).where(agents.c.name == DEFAULT_AGENT_NAME)
        )
    ).mappings().one()
    return await _row_to_runtime_with_skills(db, row)


async def create_agent_with_skill(
    db: AsyncConnection,
    *,
    name: str,
    description: str | None,
    skill_name: str | None,
    skill_type: str,
    skill_content: str,
) -> AgentSummarySchema:
    """Create a custom analyst agent and attach its first domain skill."""

    await ensure_builtin_agents(db)
    now = datetime.now(timezone.utc)
    identity_layer = (
        f"You are {name}, a custom MarketPulse analyst. Apply the attached "
        "skill as your specialty lens while staying evidence-gated, source-aware, "
        "and conservative."
    )
    agent_id = (
        await db.execute(
            insert(agents)
            .values(
                name=name,
                description=description,
                identity_layer=identity_layer,
                is_builtin=False,
                created_at=now,
            )
            .returning(agents.c.id)
        )
    ).scalar_one()

    await db.execute(
        insert(skills).values(
            agent_id=agent_id,
            name=skill_name or f"{name} Skill",
            skill_type=skill_type,
            content=skill_content,
            version=1,
            created_at=now,
            updated_at=now,
        )
    )

    agent = await get_agent(db, int(agent_id))
    if agent is None:
        raise RuntimeError("Created agent could not be loaded.")
    return _runtime_to_summary(agent)


async def get_agent_for_run(
    db: AsyncConnection,
    agent_id: int | None,
) -> AgentRuntimeSchema | None:
    """Resolve an optional request agent id to the runtime agent config."""
    if agent_id is None:
        return await get_default_agent(db)
    return await get_agent(db, agent_id)