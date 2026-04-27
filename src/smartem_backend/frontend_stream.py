from datetime import datetime

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from smartem_backend.model.database import (
    Acquisition,
    AgentConnection,
    AgentInstruction,
    AgentInstructionAcknowledgement,
    AgentLog,
    AgentSession,
    FoilHole,
    Grid,
    GridSquare,
    Micrograph,
)


async def query_agent_statuses(db: AsyncSession, agent_id: str | None = None) -> list[dict]:
    query = (
        select(
            AgentConnection.agent_id,
            AgentConnection.status,
            AgentConnection.last_heartbeat_at,
            AgentSession.session_id,
            AgentSession.acquisition_uuid,
            func.count(AgentConnection.id).label("connection_count"),
        )
        .join(AgentSession, AgentConnection.session_id == AgentSession.session_id)
        .where(AgentConnection.status == "active")
        .group_by(
            AgentConnection.agent_id,
            AgentConnection.status,
            AgentConnection.last_heartbeat_at,
            AgentSession.session_id,
            AgentSession.acquisition_uuid,
        )
    )
    if agent_id:
        query = query.where(AgentConnection.agent_id == agent_id)

    rows = (await db.execute(query)).all()
    return [
        {
            "agent_id": row.agent_id,
            "status": "online",
            "session_id": row.session_id,
            "acquisition_uuid": row.acquisition_uuid,
            "last_heartbeat_at": row.last_heartbeat_at.isoformat() if row.last_heartbeat_at else None,
            "connection_count": row.connection_count,
        }
        for row in rows
    ]


async def query_acquisition_progress(db: AsyncSession, acquisition_uuid: str | None = None) -> list[dict]:
    acq_query = select(Acquisition.uuid, Acquisition.status)
    if acquisition_uuid:
        acq_query = acq_query.where(Acquisition.uuid == acquisition_uuid)

    acquisitions = (await db.execute(acq_query)).all()
    results = []
    for acq in acquisitions:
        grid_count = (
            await db.execute(select(func.count()).select_from(Grid).where(Grid.acquisition_uuid == acq.uuid))
        ).scalar_one()
        gridsquare_count = (
            await db.execute(
                select(func.count())
                .select_from(GridSquare)
                .join(Grid, GridSquare.grid_uuid == Grid.uuid)
                .where(Grid.acquisition_uuid == acq.uuid)
            )
        ).scalar_one()
        foilhole_count = (
            await db.execute(
                select(func.count())
                .select_from(FoilHole)
                .join(GridSquare, FoilHole.gridsquare_uuid == GridSquare.uuid)
                .join(Grid, GridSquare.grid_uuid == Grid.uuid)
                .where(Grid.acquisition_uuid == acq.uuid)
            )
        ).scalar_one()
        micrograph_count = (
            await db.execute(
                select(func.count())
                .select_from(Micrograph)
                .join(FoilHole, Micrograph.foilhole_uuid == FoilHole.uuid)
                .join(GridSquare, FoilHole.gridsquare_uuid == GridSquare.uuid)
                .join(Grid, GridSquare.grid_uuid == Grid.uuid)
                .where(Grid.acquisition_uuid == acq.uuid)
            )
        ).scalar_one()
        results.append(
            {
                "acquisition_uuid": acq.uuid,
                "grid_count": grid_count,
                "gridsquare_count": gridsquare_count,
                "foilhole_count": foilhole_count,
                "micrograph_count": micrograph_count,
                "status": str(acq.status.value) if hasattr(acq.status, "value") else str(acq.status),
            }
        )
    return results


async def query_instruction_updates(db: AsyncSession, since: datetime, agent_id: str | None = None) -> list[dict]:
    query = select(AgentInstruction).where(
        (AgentInstruction.created_at > since)
        | (AgentInstruction.sent_at > since)
        | (AgentInstruction.acknowledged_at > since)
    )
    if agent_id:
        query = query.where(AgentInstruction.agent_id == agent_id)

    instructions = (await db.execute(query)).scalars().all()
    results = []
    for instr in instructions:
        ack = (
            (
                await db.execute(
                    select(AgentInstructionAcknowledgement)
                    .where(AgentInstructionAcknowledgement.instruction_id == instr.instruction_id)
                    .order_by(AgentInstructionAcknowledgement.created_at.desc())
                )
            )
            .scalars()
            .first()
        )
        results.append(
            {
                "instruction_id": instr.instruction_id,
                "agent_id": instr.agent_id,
                "session_id": instr.session_id,
                "instruction_type": instr.instruction_type,
                "status": instr.status,
                "created_at": instr.created_at.isoformat(),
                "sent_at": instr.sent_at.isoformat() if instr.sent_at else None,
                "acknowledged_at": instr.acknowledged_at.isoformat() if instr.acknowledged_at else None,
                "ack_status": ack.status if ack else None,
            }
        )
    return results


async def query_processing_metrics(
    db: AsyncSession, since: datetime, acquisition_uuid: str | None = None
) -> list[dict]:
    query = select(Micrograph).where(and_(Micrograph.updated_at.is_not(None), Micrograph.updated_at > since))
    if acquisition_uuid:
        query = (
            query.join(FoilHole, Micrograph.foilhole_uuid == FoilHole.uuid)
            .join(GridSquare, FoilHole.gridsquare_uuid == GridSquare.uuid)
            .join(Grid, GridSquare.grid_uuid == Grid.uuid)
            .where(Grid.acquisition_uuid == acquisition_uuid)
        )

    micrographs = (await db.execute(query)).scalars().all()
    return [
        {
            "micrograph_uuid": m.uuid,
            "foilhole_uuid": m.foilhole_uuid,
            "total_motion": m.total_motion,
            "average_motion": m.average_motion,
            "ctf_max_resolution_estimate": m.ctf_max_resolution_estimate,
            "number_of_particles_picked": m.number_of_particles_picked,
            "number_of_particles_selected": m.number_of_particles_selected,
        }
        for m in micrographs
    ]


async def query_agent_logs(
    db: AsyncSession, since_id: int, agent_id: str | None = None, limit: int = 200
) -> list[dict]:
    query = select(AgentLog).where(AgentLog.id > since_id).order_by(AgentLog.id).limit(limit)
    if agent_id:
        query = query.where(AgentLog.agent_id == agent_id)

    logs = (await db.execute(query)).scalars().all()
    return [
        {
            "id": log.id,
            "agent_id": log.agent_id,
            "session_id": log.session_id,
            "timestamp": log.timestamp.isoformat(),
            "level": log.level,
            "logger_name": log.logger_name,
            "message": log.message,
        }
        for log in logs
    ]
