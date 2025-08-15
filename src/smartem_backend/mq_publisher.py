from smartem_backend.model.mq_event import (
    AcquisitionCreatedEvent,
    AcquisitionDeletedEvent,
    AcquisitionUpdatedEvent,
    AtlasCreatedEvent,
    AtlasDeletedEvent,
    AtlasTileCreatedEvent,
    AtlasTileDeletedEvent,
    AtlasTileUpdatedEvent,
    AtlasUpdatedEvent,
    FoilHoleCreatedEvent,
    FoilHoleDeletedEvent,
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
)
from smartem_backend.utils import rmq_publisher


# ========== Acquisition DB Entity Mutations ==========
def publish_acquisition_created(uuid, id=None, **kwargs):
    """Publish acquisition created event to RabbitMQ"""
    event = AcquisitionCreatedEvent(event_type=MessageQueueEventType.ACQUISITION_CREATED, uuid=uuid, id=id)
    return rmq_publisher.publish_event(MessageQueueEventType.ACQUISITION_CREATED, event)


def publish_acquisition_updated(uuid, id=None):
    """Publish acquisition updated event to RabbitMQ"""
    event = AcquisitionUpdatedEvent(event_type=MessageQueueEventType.ACQUISITION_UPDATED, uuid=uuid, id=id)
    return rmq_publisher.publish_event(MessageQueueEventType.ACQUISITION_UPDATED, event)


def publish_acquisition_deleted(uuid):
    """Publish acquisition deleted event to RabbitMQ"""
    event = AcquisitionDeletedEvent(event_type=MessageQueueEventType.ACQUISITION_DELETED, uuid=uuid)
    return rmq_publisher.publish_event(MessageQueueEventType.ACQUISITION_DELETED, event)


# ========== Atlas DB Entity Mutations ==========
def publish_atlas_created(uuid, id=None, grid_uuid=None):
    """Publish atlas created event to RabbitMQ"""
    event = AtlasCreatedEvent(event_type=MessageQueueEventType.ATLAS_CREATED, uuid=uuid, id=id, grid_uuid=grid_uuid)
    return rmq_publisher.publish_event(MessageQueueEventType.ATLAS_CREATED, event)


def publish_atlas_updated(uuid, id=None, grid_uuid=None):
    """Publish atlas updated event to RabbitMQ"""
    event = AtlasUpdatedEvent(event_type=MessageQueueEventType.ATLAS_UPDATED, uuid=uuid, id=id, grid_uuid=grid_uuid)
    return rmq_publisher.publish_event(MessageQueueEventType.ATLAS_UPDATED, event)


def publish_atlas_deleted(uuid):
    """Publish atlas deleted event to RabbitMQ"""
    event = AtlasDeletedEvent(event_type=MessageQueueEventType.ATLAS_DELETED, uuid=uuid)
    return rmq_publisher.publish_event(MessageQueueEventType.ATLAS_DELETED, event)


# ========== Atlas Tile DB Entity Mutations ==========
def publish_atlas_tile_created(uuid, id=None, atlas_uuid=None):
    """Publish atlas tile created event to RabbitMQ"""
    event = AtlasTileCreatedEvent(
        event_type=MessageQueueEventType.ATLAS_TILE_CREATED, uuid=uuid, id=id, atlas_uuid=atlas_uuid
    )
    return rmq_publisher.publish_event(MessageQueueEventType.ATLAS_TILE_CREATED, event)


def publish_atlas_tile_updated(uuid, id=None, atlas_uuid=None):
    """Publish atlas tile updated event to RabbitMQ"""
    event = AtlasTileUpdatedEvent(
        event_type=MessageQueueEventType.ATLAS_TILE_UPDATED, uuid=uuid, id=id, atlas_uuid=atlas_uuid
    )
    return rmq_publisher.publish_event(MessageQueueEventType.ATLAS_TILE_UPDATED, event)


def publish_atlas_tile_deleted(uuid):
    """Publish atlas tile deleted event to RabbitMQ"""
    event = AtlasTileDeletedEvent(event_type=MessageQueueEventType.ATLAS_TILE_DELETED, uuid=uuid)
    return rmq_publisher.publish_event(MessageQueueEventType.ATLAS_TILE_DELETED, event)


# ========== Grid DB Entity Mutations ==========
def publish_grid_created(uuid, acquisition_uuid=None):
    """Publish grid created event to RabbitMQ"""
    event = GridCreatedEvent(
        event_type=MessageQueueEventType.GRID_CREATED, uuid=uuid, acquisition_uuid=acquisition_uuid
    )
    return rmq_publisher.publish_event(MessageQueueEventType.GRID_CREATED, event)


def publish_grid_updated(uuid, acquisition_uuid=None):
    """Publish grid updated event to RabbitMQ"""
    event = GridUpdatedEvent(
        event_type=MessageQueueEventType.GRID_UPDATED, uuid=uuid, acquisition_uuid=acquisition_uuid
    )
    return rmq_publisher.publish_event(MessageQueueEventType.GRID_UPDATED, event)


def publish_grid_deleted(uuid):
    """Publish grid deleted event to RabbitMQ"""
    event = GridDeletedEvent(event_type=MessageQueueEventType.GRID_DELETED, uuid=uuid)
    return rmq_publisher.publish_event(MessageQueueEventType.GRID_DELETED, event)


def publish_grid_registered(uuid: str):
    """Publish grid updated event to RabbitMQ"""
    event = GridRegisteredEvent(
        event_type=MessageQueueEventType.GRID_REGISTERED,
        grid_uuid=uuid,
    )
    return rmq_publisher.publish_event(MessageQueueEventType.GRID_REGISTERED, event)


# ========== Grid Square DB Entity Mutations ==========
def publish_gridsquare_created(uuid, grid_uuid=None, gridsquare_id=None):
    """Publish grid square created event to RabbitMQ"""
    event = GridSquareCreatedEvent(
        event_type=MessageQueueEventType.GRIDSQUARE_CREATED, uuid=uuid, grid_uuid=grid_uuid, gridsquare_id=gridsquare_id
    )
    return rmq_publisher.publish_event(MessageQueueEventType.GRIDSQUARE_CREATED, event)


def publish_gridsquare_updated(uuid, grid_uuid=None, gridsquare_id=None):
    """Publish grid square updated event to RabbitMQ"""
    event = GridSquareUpdatedEvent(
        event_type=MessageQueueEventType.GRIDSQUARE_UPDATED, uuid=uuid, grid_uuid=grid_uuid, gridsquare_id=gridsquare_id
    )
    return rmq_publisher.publish_event(MessageQueueEventType.GRIDSQUARE_UPDATED, event)


def publish_gridsquare_deleted(uuid):
    """Publish grid square deleted event to RabbitMQ"""
    event = GridSquareDeletedEvent(event_type=MessageQueueEventType.GRIDSQUARE_DELETED, uuid=uuid)
    return rmq_publisher.publish_event(MessageQueueEventType.GRIDSQUARE_DELETED, event)


def publish_gridsquare_registered(uuid: str):
    """Publish grid square updated event to RabbitMQ"""
    event = GridSquareRegisteredEvent(
        event_type=MessageQueueEventType.GRIDSQUARE_REGISTERED,
        uuid=uuid,
    )
    return rmq_publisher.publish_event(MessageQueueEventType.GRIDSQUARE_REGISTERED, event)


def publish_gridsquare_lowmag_created(uuid, grid_uuid=None, gridsquare_id=None):
    """Publish low mag grid square created event to RabbitMQ"""
    event = GridSquareCreatedEvent(
        event_type=MessageQueueEventType.GRIDSQUARE_LOWMAG_CREATED,
        uuid=uuid,
        grid_uuid=grid_uuid,
        gridsquare_id=gridsquare_id,
    )
    return rmq_publisher.publish_event(MessageQueueEventType.GRIDSQUARE_LOWMAG_CREATED, event)


def publish_gridsquare_lowmag_updated(uuid, grid_uuid=None, gridsquare_id=None):
    """Publish low mag grid square updated event to RabbitMQ"""
    event = GridSquareUpdatedEvent(
        event_type=MessageQueueEventType.GRIDSQUARE_LOWMAG_UPDATED,
        uuid=uuid,
        grid_uuid=grid_uuid,
        gridsquare_id=gridsquare_id,
    )
    return rmq_publisher.publish_event(MessageQueueEventType.GRIDSQUARE_LOWMAG_UPDATED, event)


def publish_gridsquare_lowmag_deleted(uuid):
    """Publish low mag grid square deleted event to RabbitMQ"""
    event = GridSquareDeletedEvent(event_type=MessageQueueEventType.GRIDSQUARE_LOWMAG_DELETED, uuid=uuid)
    return rmq_publisher.publish_event(MessageQueueEventType.GRIDSQUARE_LOWMAG_DELETED, event)


# ========== Foil Hole DB Entity Mutations ==========
def publish_foilhole_created(uuid, foilhole_id=None, gridsquare_uuid=None, gridsquare_id=None):
    """Publish foil hole created event to RabbitMQ"""
    event = FoilHoleCreatedEvent(
        event_type=MessageQueueEventType.FOILHOLE_CREATED,
        uuid=uuid,
        foilhole_id=foilhole_id,
        gridsquare_uuid=gridsquare_uuid,
        gridsquare_id=gridsquare_id,
    )
    return rmq_publisher.publish_event(MessageQueueEventType.FOILHOLE_CREATED, event)


def publish_foilhole_updated(uuid, foilhole_id=None, gridsquare_uuid=None, gridsquare_id=None):
    """Publish foil hole updated event to RabbitMQ"""
    event = FoilHoleUpdatedEvent(
        event_type=MessageQueueEventType.FOILHOLE_UPDATED,
        uuid=uuid,
        foilhole_id=foilhole_id,
        gridsquare_uuid=gridsquare_uuid,
        gridsquare_id=gridsquare_id,
    )
    return rmq_publisher.publish_event(MessageQueueEventType.FOILHOLE_UPDATED, event)


def publish_foilhole_deleted(uuid):
    """Publish foil hole deleted event to RabbitMQ"""
    event = FoilHoleDeletedEvent(event_type=MessageQueueEventType.FOILHOLE_DELETED, uuid=uuid)
    return rmq_publisher.publish_event(MessageQueueEventType.FOILHOLE_DELETED, event)


# ========== Micrograph DB Entity Mutations ==========
def publish_micrograph_created(uuid, foilhole_uuid=None, foilhole_id=None, micrograph_id=None):
    """Publish micrograph created event to RabbitMQ"""
    event = MicrographCreatedEvent(
        event_type=MessageQueueEventType.MICROGRAPH_CREATED,
        uuid=uuid,
        foilhole_uuid=foilhole_uuid,
        foilhole_id=foilhole_id,
        micrograph_id=micrograph_id,
    )
    return rmq_publisher.publish_event(MessageQueueEventType.MICROGRAPH_CREATED, event)


def publish_micrograph_updated(uuid, foilhole_uuid=None, foilhole_id=None, micrograph_id=None):
    """Publish micrograph updated event to RabbitMQ"""
    event = MicrographUpdatedEvent(
        event_type=MessageQueueEventType.MICROGRAPH_UPDATED,
        uuid=uuid,
        foilhole_uuid=foilhole_uuid,
        foilhole_id=foilhole_id,
        micrograph_id=micrograph_id,
    )
    return rmq_publisher.publish_event(MessageQueueEventType.MICROGRAPH_UPDATED, event)


def publish_micrograph_deleted(uuid):
    """Publish micrograph deleted event to RabbitMQ"""
    event = MicrographDeletedEvent(event_type=MessageQueueEventType.MICROGRAPH_DELETED, uuid=uuid)
    return rmq_publisher.publish_event(MessageQueueEventType.MICROGRAPH_DELETED, event)


def publish_gridsquare_model_prediction(gridsquare_uuid: str, model_name: str, prediction_value: float):
    """Publish model prediction event for a grid square to RabbitMQ"""
    event = GridSquareModelPredictionEvent(
        event_type=MessageQueueEventType.GRIDSQUARE_MODEL_PREDICTION,
        gridsquare_uuid=gridsquare_uuid,
        prediction_model_name=model_name,
        prediction_value=prediction_value,
    )
    return rmq_publisher.publish_event(MessageQueueEventType.GRIDSQUARE_MODEL_PREDICTION, event)


def publish_foilhole_model_prediction(foilhole_uuid: str, model_name: str, prediction_value: float):
    """Publish model prediction event for a foil hole to RabbitMQ"""
    event = FoilHoleModelPredictionEvent(
        event_type=MessageQueueEventType.FOILHOLE_MODEL_PREDICTION,
        foilhole_uuid=foilhole_uuid,
        prediction_model_name=model_name,
        prediction_value=prediction_value,
    )
    return rmq_publisher.publish_event(MessageQueueEventType.FOILHOLE_MODEL_PREDICTION, event)


def publish_model_parameter_update(grid_uuid: str, model_name: str, key: str, value: float, group: str = ""):
    """Publish model parameter update event to RabbitMQ"""
    event = ModelParameterUpdateEvent(
        event_type=MessageQueueEventType.MODEL_PARAMETER_UPDATE,
        grid_uuid=grid_uuid,
        prediction_model_name=model_name,
        key=key,
        value=value,
        group=group,
    )
    return rmq_publisher.publish_event(MessageQueueEventType.MODEL_PARAMETER_UPDATE, event)
