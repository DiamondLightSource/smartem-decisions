import logging

from smartem_backend.model.mq_event import (
    AcquisitionCreatedEvent,
    AcquisitionDeletedEvent,
    AcquisitionUpdatedEvent,
    AgentInstructionCreatedEvent,
    AgentInstructionExpiredEvent,
    AgentInstructionUpdatedEvent,
    AtlasCreatedEvent,
    AtlasDeletedEvent,
    AtlasPredictionEvent,
    AtlasTileCreatedEvent,
    AtlasTileDeletedEvent,
    AtlasTileUpdatedEvent,
    AtlasUpdatedEvent,
    CreateFoilHoleGroupEvent,
    CtfCompleteBody,
    CtfRegisteredBody,
    FoilHoleCreatedEvent,
    FoilHoleDeletedEvent,
    FoilHoleGroupModelPredictionEvent,
    FoilHoleModelPredictionEvent,
    FoilHoleUpdatedEvent,
    GridCreatedEvent,
    GridDeletedEvent,
    GridRegisteredEvent,
    GridSquareCreatedEvent,
    GridSquareDeletedEvent,
    GridSquareModelPredictionEvent,
    GridSquareRegisteredEvent,
    GridSquareUpdatedEvent,
    GridUpdatedEvent,
    MessageQueueEventType,
    MicrographCreatedEvent,
    MicrographDeletedEvent,
    MicrographUpdatedEvent,
    ModelParameterUpdateEvent,
    MotionCorrectionCompleteBody,
    MotionCorrectionRegisteredBody,
    MultiFoilHoleModelPredictionEvent,
    ParticlePickingCompleteBody,
    ParticlePickingRegisteredBody,
    RefreshPredictionsEvent,
)
from smartem_backend.rmq import AioPikaPublisher

logger = logging.getLogger(__name__)

_publisher: AioPikaPublisher | None = None


def set_publisher(publisher: AioPikaPublisher | None) -> None:
    """Bind the singleton publisher. Called by FastAPI lifespan on startup and shutdown."""
    global _publisher
    _publisher = publisher


def get_publisher() -> AioPikaPublisher | None:
    """Expose the bound publisher for health checks and direct access."""
    return _publisher


async def _publish(event_type: MessageQueueEventType, payload) -> bool:
    if _publisher is None:
        logger.error("Publish attempted before publisher bound: %s", event_type.value)
        return False
    return await _publisher.publish_event(event_type, payload)


async def _publish_batch(items) -> bool:
    if _publisher is None:
        logger.error("Batch publish attempted before publisher bound: %d items", len(items))
        return False
    return await _publisher.publish_events(items)


# ========== Acquisition DB Entity Mutations ==========
async def publish_acquisition_created(uuid, id=None, **kwargs) -> bool:
    event = AcquisitionCreatedEvent(event_type=MessageQueueEventType.ACQUISITION_CREATED, uuid=uuid, id=id)
    return await _publish(MessageQueueEventType.ACQUISITION_CREATED, event)


async def publish_acquisition_updated(uuid, id=None) -> bool:
    event = AcquisitionUpdatedEvent(event_type=MessageQueueEventType.ACQUISITION_UPDATED, uuid=uuid, id=id)
    return await _publish(MessageQueueEventType.ACQUISITION_UPDATED, event)


async def publish_acquisition_deleted(uuid) -> bool:
    event = AcquisitionDeletedEvent(event_type=MessageQueueEventType.ACQUISITION_DELETED, uuid=uuid)
    return await _publish(MessageQueueEventType.ACQUISITION_DELETED, event)


# ========== Atlas DB Entity Mutations ==========
async def publish_atlas_created(uuid, id=None, grid_uuid=None) -> bool:
    event = AtlasCreatedEvent(event_type=MessageQueueEventType.ATLAS_CREATED, uuid=uuid, id=id, grid_uuid=grid_uuid)
    return await _publish(MessageQueueEventType.ATLAS_CREATED, event)


async def publish_atlas_updated(uuid, id=None, grid_uuid=None) -> bool:
    event = AtlasUpdatedEvent(event_type=MessageQueueEventType.ATLAS_UPDATED, uuid=uuid, id=id, grid_uuid=grid_uuid)
    return await _publish(MessageQueueEventType.ATLAS_UPDATED, event)


async def publish_atlas_deleted(uuid) -> bool:
    event = AtlasDeletedEvent(event_type=MessageQueueEventType.ATLAS_DELETED, uuid=uuid)
    return await _publish(MessageQueueEventType.ATLAS_DELETED, event)


# ========== Atlas Tile DB Entity Mutations ==========
async def publish_atlas_tile_created(uuid, id=None, atlas_uuid=None) -> bool:
    event = AtlasTileCreatedEvent(
        event_type=MessageQueueEventType.ATLAS_TILE_CREATED, uuid=uuid, id=id, atlas_uuid=atlas_uuid
    )
    return await _publish(MessageQueueEventType.ATLAS_TILE_CREATED, event)


async def publish_atlas_tile_updated(uuid, id=None, atlas_uuid=None) -> bool:
    event = AtlasTileUpdatedEvent(
        event_type=MessageQueueEventType.ATLAS_TILE_UPDATED, uuid=uuid, id=id, atlas_uuid=atlas_uuid
    )
    return await _publish(MessageQueueEventType.ATLAS_TILE_UPDATED, event)


async def publish_atlas_tile_deleted(uuid) -> bool:
    event = AtlasTileDeletedEvent(event_type=MessageQueueEventType.ATLAS_TILE_DELETED, uuid=uuid)
    return await _publish(MessageQueueEventType.ATLAS_TILE_DELETED, event)


# ========== Grid DB Entity Mutations ==========
async def publish_grid_created(uuid, acquisition_uuid=None) -> bool:
    event = GridCreatedEvent(
        event_type=MessageQueueEventType.GRID_CREATED, uuid=uuid, acquisition_uuid=acquisition_uuid
    )
    return await _publish(MessageQueueEventType.GRID_CREATED, event)


async def publish_grid_updated(uuid, acquisition_uuid=None) -> bool:
    event = GridUpdatedEvent(
        event_type=MessageQueueEventType.GRID_UPDATED, uuid=uuid, acquisition_uuid=acquisition_uuid
    )
    return await _publish(MessageQueueEventType.GRID_UPDATED, event)


async def publish_grid_deleted(uuid) -> bool:
    event = GridDeletedEvent(event_type=MessageQueueEventType.GRID_DELETED, uuid=uuid)
    return await _publish(MessageQueueEventType.GRID_DELETED, event)


async def publish_grid_registered(uuid: str) -> bool:
    event = GridRegisteredEvent(event_type=MessageQueueEventType.GRID_REGISTERED, grid_uuid=uuid)
    return await _publish(MessageQueueEventType.GRID_REGISTERED, event)


# ========== Grid Square DB Entity Mutations ==========
async def publish_gridsquare_created(uuid, grid_uuid=None, gridsquare_id=None) -> bool:
    event = GridSquareCreatedEvent(
        event_type=MessageQueueEventType.GRIDSQUARE_CREATED, uuid=uuid, grid_uuid=grid_uuid, gridsquare_id=gridsquare_id
    )
    return await _publish(MessageQueueEventType.GRIDSQUARE_CREATED, event)


async def publish_gridsquare_updated(uuid, grid_uuid=None, gridsquare_id=None) -> bool:
    event = GridSquareUpdatedEvent(
        event_type=MessageQueueEventType.GRIDSQUARE_UPDATED, uuid=uuid, grid_uuid=grid_uuid, gridsquare_id=gridsquare_id
    )
    return await _publish(MessageQueueEventType.GRIDSQUARE_UPDATED, event)


async def publish_gridsquare_deleted(uuid) -> bool:
    event = GridSquareDeletedEvent(event_type=MessageQueueEventType.GRIDSQUARE_DELETED, uuid=uuid)
    return await _publish(MessageQueueEventType.GRIDSQUARE_DELETED, event)


async def publish_gridsquare_registered(uuid: str, count: int | None = None) -> bool:
    event = GridSquareRegisteredEvent(
        event_type=MessageQueueEventType.GRIDSQUARE_REGISTERED, uuid=uuid, count=count
    )
    return await _publish(MessageQueueEventType.GRIDSQUARE_REGISTERED, event)


async def publish_gridsquare_lowmag_created(uuid, grid_uuid=None, gridsquare_id=None) -> bool:
    event = GridSquareCreatedEvent(
        event_type=MessageQueueEventType.GRIDSQUARE_LOWMAG_CREATED,
        uuid=uuid,
        grid_uuid=grid_uuid,
        gridsquare_id=gridsquare_id,
    )
    return await _publish(MessageQueueEventType.GRIDSQUARE_LOWMAG_CREATED, event)


async def publish_gridsquare_lowmag_updated(uuid, grid_uuid=None, gridsquare_id=None) -> bool:
    event = GridSquareUpdatedEvent(
        event_type=MessageQueueEventType.GRIDSQUARE_LOWMAG_UPDATED,
        uuid=uuid,
        grid_uuid=grid_uuid,
        gridsquare_id=gridsquare_id,
    )
    return await _publish(MessageQueueEventType.GRIDSQUARE_LOWMAG_UPDATED, event)


async def publish_gridsquares_created_batch(
    entries: list[tuple[str, str | None, str | None, bool]],
) -> bool:
    items: list[tuple[MessageQueueEventType, GridSquareCreatedEvent]] = []
    for uuid, grid_uuid, gridsquare_id, lowmag in entries:
        event_type = (
            MessageQueueEventType.GRIDSQUARE_LOWMAG_CREATED if lowmag else MessageQueueEventType.GRIDSQUARE_CREATED
        )
        items.append(
            (
                event_type,
                GridSquareCreatedEvent(
                    event_type=event_type, uuid=uuid, grid_uuid=grid_uuid, gridsquare_id=gridsquare_id
                ),
            )
        )
    return await _publish_batch(items)


async def publish_gridsquare_lowmag_deleted(uuid) -> bool:
    event = GridSquareDeletedEvent(event_type=MessageQueueEventType.GRIDSQUARE_LOWMAG_DELETED, uuid=uuid)
    return await _publish(MessageQueueEventType.GRIDSQUARE_LOWMAG_DELETED, event)


# ========== Foil Hole DB Entity Mutations ==========
async def publish_foilhole_created(uuid, foilhole_id=None, gridsquare_uuid=None, gridsquare_id=None) -> bool:
    event = FoilHoleCreatedEvent(
        event_type=MessageQueueEventType.FOILHOLE_CREATED,
        uuid=uuid,
        foilhole_id=foilhole_id,
        gridsquare_uuid=gridsquare_uuid,
        gridsquare_id=gridsquare_id,
    )
    return await _publish(MessageQueueEventType.FOILHOLE_CREATED, event)


async def publish_foilhole_updated(uuid, foilhole_id=None, gridsquare_uuid=None, gridsquare_id=None) -> bool:
    event = FoilHoleUpdatedEvent(
        event_type=MessageQueueEventType.FOILHOLE_UPDATED,
        uuid=uuid,
        foilhole_id=foilhole_id,
        gridsquare_uuid=gridsquare_uuid,
        gridsquare_id=gridsquare_id,
    )
    return await _publish(MessageQueueEventType.FOILHOLE_UPDATED, event)


async def publish_foilhole_deleted(uuid) -> bool:
    event = FoilHoleDeletedEvent(event_type=MessageQueueEventType.FOILHOLE_DELETED, uuid=uuid)
    return await _publish(MessageQueueEventType.FOILHOLE_DELETED, event)


# ========== Micrograph DB Entity Mutations ==========
async def publish_micrograph_created(uuid, foilhole_uuid=None, foilhole_id=None, micrograph_id=None) -> bool:
    event = MicrographCreatedEvent(
        event_type=MessageQueueEventType.MICROGRAPH_CREATED,
        uuid=uuid,
        foilhole_uuid=foilhole_uuid,
        foilhole_id=foilhole_id,
        micrograph_id=micrograph_id,
    )
    return await _publish(MessageQueueEventType.MICROGRAPH_CREATED, event)


async def publish_micrograph_updated(uuid, foilhole_uuid=None, foilhole_id=None, micrograph_id=None) -> bool:
    event = MicrographUpdatedEvent(
        event_type=MessageQueueEventType.MICROGRAPH_UPDATED,
        uuid=uuid,
        foilhole_uuid=foilhole_uuid,
        foilhole_id=foilhole_id,
        micrograph_id=micrograph_id,
    )
    return await _publish(MessageQueueEventType.MICROGRAPH_UPDATED, event)


async def publish_micrograph_deleted(uuid) -> bool:
    event = MicrographDeletedEvent(event_type=MessageQueueEventType.MICROGRAPH_DELETED, uuid=uuid)
    return await _publish(MessageQueueEventType.MICROGRAPH_DELETED, event)


async def publish_atlas_model_prediction(atlas_uuid: str, prediction_value: float, model_name: str = "") -> bool:
    event = AtlasPredictionEvent(
        event_type=MessageQueueEventType.ATLAS_MODEL_PREDICTION,
        uuid=atlas_uuid,
        prediction_value=prediction_value,
        model_name=model_name,
    )
    return await _publish(MessageQueueEventType.ATLAS_MODEL_PREDICTION, event)


async def publish_gridsquare_model_prediction(
    gridsquare_uuid: str, model_name: str, prediction_value: float, metric: str | None = None
) -> bool:
    event = GridSquareModelPredictionEvent(
        event_type=MessageQueueEventType.GRIDSQUARE_MODEL_PREDICTION,
        gridsquare_uuid=gridsquare_uuid,
        prediction_model_name=model_name,
        prediction_value=prediction_value,
        metric=metric,
    )
    return await _publish(MessageQueueEventType.GRIDSQUARE_MODEL_PREDICTION, event)


async def publish_foilhole_model_prediction(
    foilhole_uuid: str, model_name: str, prediction_value: float, metric: str | None = None
) -> bool:
    event = FoilHoleModelPredictionEvent(
        event_type=MessageQueueEventType.FOILHOLE_MODEL_PREDICTION,
        foilhole_uuid=foilhole_uuid,
        prediction_model_name=model_name,
        prediction_value=prediction_value,
        metric=metric,
    )
    return await _publish(MessageQueueEventType.FOILHOLE_MODEL_PREDICTION, event)


async def publish_multi_foilhole_model_prediction(
    foilhole_uuids: list[str], model_name: str, prediction_value: float, metric: str | None = None
) -> bool:
    event = MultiFoilHoleModelPredictionEvent(
        event_type=MessageQueueEventType.MULTI_FOILHOLE_MODEL_PREDICTION,
        foilhole_uuids=foilhole_uuids,
        prediction_model_name=model_name,
        prediction_value=prediction_value,
        metric=metric,
    )
    return await _publish(MessageQueueEventType.MULTI_FOILHOLE_MODEL_PREDICTION, event)


async def publish_create_foilhole_group(
    grid_uuid: str, foilhole_uuids: list[str], group_uuid: str, name: str | None = None
) -> bool:
    event = CreateFoilHoleGroupEvent(
        event_type=MessageQueueEventType.CREATE_FOILHOLE_GROUP,
        grid_uuid=grid_uuid,
        foilhole_uuids=foilhole_uuids,
        group_uuid=group_uuid,
        name=name,
    )
    return await _publish(MessageQueueEventType.CREATE_FOILHOLE_GROUP, event)


async def publish_foilhole_group_model_prediction(
    group_uuid: str, model_name: str, prediction_value: float, metric: str | None = None
) -> bool:
    event = FoilHoleGroupModelPredictionEvent(
        event_type=MessageQueueEventType.FOILHOLE_GROUP_MODEL_PREDICTION,
        group_uuid=group_uuid,
        prediction_model_name=model_name,
        prediction_value=prediction_value,
        metric=metric,
    )
    return await _publish(MessageQueueEventType.FOILHOLE_GROUP_MODEL_PREDICTION, event)


async def publish_model_parameter_update(
    grid_uuid: str, model_name: str, key: str, value: float, metric: str | None = None, group: str = ""
) -> bool:
    event = ModelParameterUpdateEvent(
        event_type=MessageQueueEventType.MODEL_PARAMETER_UPDATE,
        grid_uuid=grid_uuid,
        prediction_model_name=model_name,
        key=key,
        value=value,
        metric=metric,
        group=group,
    )
    return await _publish(MessageQueueEventType.MODEL_PARAMETER_UPDATE, event)


async def publish_motion_correction_completed(
    micrograph_uuid: str, total_motion: float, average_motion: float
) -> bool:
    event = MotionCorrectionCompleteBody(
        event_type=MessageQueueEventType.MOTION_CORRECTION_COMPLETE,
        micrograph_uuid=micrograph_uuid,
        total_motion=total_motion,
        average_motion=average_motion,
    )
    return await _publish(MessageQueueEventType.MOTION_CORRECTION_COMPLETE, event)


async def publish_motion_correction_registered(
    micrograph_uuid: str, quality: bool, metric_name: str | None = None
) -> bool:
    event = MotionCorrectionRegisteredBody(
        event_type=MessageQueueEventType.MOTION_CORRECTION_REGISTERED,
        micrograph_uuid=micrograph_uuid,
        quality=quality,
        metric_name=metric_name,
    )
    return await _publish(MessageQueueEventType.MOTION_CORRECTION_REGISTERED, event)


async def publish_ctf_estimation_completed(micrograph_uuid: str, ctf_max_res: float) -> bool:
    event = CtfCompleteBody(
        event_type=MessageQueueEventType.CTF_COMPLETE,
        micrograph_uuid=micrograph_uuid,
        ctf_max_resolution_estimate=ctf_max_res,
    )
    return await _publish(MessageQueueEventType.CTF_COMPLETE, event)


async def publish_ctf_estimation_registered(
    micrograph_uuid: str, quality: bool, metric_name: str | None = None
) -> bool:
    event = CtfRegisteredBody(
        event_type=MessageQueueEventType.CTF_REGISTERED,
        micrograph_uuid=micrograph_uuid,
        quality=quality,
        metric_name=metric_name,
    )
    return await _publish(MessageQueueEventType.CTF_REGISTERED, event)


async def publish_particle_picking_completed(micrograph_uuid: str, number_of_particles_picked: int) -> bool:
    event = ParticlePickingCompleteBody(
        event_type=MessageQueueEventType.PARTICLE_PICKING_COMPLETE,
        micrograph_uuid=micrograph_uuid,
        number_of_particles_picked=number_of_particles_picked,
    )
    return await _publish(MessageQueueEventType.PARTICLE_PICKING_COMPLETE, event)


async def publish_particle_picking_registered(
    micrograph_uuid: str, quality: bool, metric_name: str | None = None
) -> bool:
    event = ParticlePickingRegisteredBody(
        event_type=MessageQueueEventType.PARTICLE_PICKING_REGISTERED,
        micrograph_uuid=micrograph_uuid,
        quality=quality,
        metric_name=metric_name,
    )
    return await _publish(MessageQueueEventType.PARTICLE_PICKING_REGISTERED, event)


async def publish_refresh_predictions(grid_uuid: str) -> bool:
    event = RefreshPredictionsEvent(event_type=MessageQueueEventType.REFRESH_PREDICTIONS, grid_uuid=grid_uuid)
    return await _publish(MessageQueueEventType.REFRESH_PREDICTIONS, event)


# ========== Agent Communication Events ==========


async def publish_agent_instruction_created(
    instruction_id, session_id, agent_id, instruction_type, payload, **kwargs
) -> bool:
    event = AgentInstructionCreatedEvent(
        event_type=MessageQueueEventType.AGENT_INSTRUCTION_CREATED,
        instruction_id=instruction_id,
        session_id=session_id,
        agent_id=agent_id,
        instruction_type=instruction_type,
        payload=payload,
        sequence_number=kwargs.get("sequence_number"),
        priority=kwargs.get("priority", "normal"),
        expires_at=kwargs.get("expires_at"),
        instruction_metadata=kwargs.get("instruction_metadata"),
    )
    return await _publish(MessageQueueEventType.AGENT_INSTRUCTION_CREATED, event)


async def publish_agent_instruction_updated(
    instruction_id, session_id, agent_id, status, acknowledged_at=None
) -> bool:
    event = AgentInstructionUpdatedEvent(
        event_type=MessageQueueEventType.AGENT_INSTRUCTION_UPDATED,
        instruction_id=instruction_id,
        session_id=session_id,
        agent_id=agent_id,
        status=status,
        acknowledged_at=acknowledged_at,
    )
    return await _publish(MessageQueueEventType.AGENT_INSTRUCTION_UPDATED, event)


async def publish_agent_instruction_expired(instruction_id, session_id, agent_id, expires_at, retry_count) -> bool:
    event = AgentInstructionExpiredEvent(
        event_type=MessageQueueEventType.AGENT_INSTRUCTION_EXPIRED,
        instruction_id=instruction_id,
        session_id=session_id,
        agent_id=agent_id,
        expires_at=expires_at,
        retry_count=retry_count,
    )
    return await _publish(MessageQueueEventType.AGENT_INSTRUCTION_EXPIRED, event)
