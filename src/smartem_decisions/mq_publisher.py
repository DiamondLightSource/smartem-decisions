from src.smartem_decisions.model.mq_event import (
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
    FoilHoleUpdatedEvent,
    GridCreatedEvent,
    GridDeletedEvent,
    GridSquareCreatedEvent,
    GridSquareDeletedEvent,
    GridSquareUpdatedEvent,
    GridUpdatedEvent,
    MicrographCreatedEvent,
    MicrographDeletedEvent,
    MicrographUpdatedEvent,
)
from src.smartem_decisions.rabbitmq import MessageQueueEventType
from src.smartem_decisions.utils import rmq_publisher


# ========== Acquisition DB Entity Mutations ==========
def publish_acquisition_created(acquisition_data):
    """Publish acquisition created event to RabbitMQ"""
    event = AcquisitionCreatedEvent(**{"event_type": MessageQueueEventType.ACQUISITION_CREATED, **acquisition_data})
    return rmq_publisher.publish_event(MessageQueueEventType.ACQUISITION_CREATED, event)


def publish_acquisition_updated(acquisition_data):
    """Publish acquisition updated event to RabbitMQ"""
    event = AcquisitionUpdatedEvent(**{"event_type": MessageQueueEventType.ACQUISITION_UPDATED, **acquisition_data})
    return rmq_publisher.publish_event(MessageQueueEventType.ACQUISITION_UPDATED, event)


def publish_acquisition_deleted(acquisition_id):
    """Publish acquisition deleted event to RabbitMQ"""
    event = AcquisitionDeletedEvent(event_type=MessageQueueEventType.ACQUISITION_DELETED, id=acquisition_id)
    return rmq_publisher.publish_event(MessageQueueEventType.ACQUISITION_DELETED, event)


# ========== Atlas DB Entity Mutations ==========
def publish_atlas_created(atlas_data):
    """Publish atlas created event to RabbitMQ"""
    event = AtlasCreatedEvent(**{"event_type": MessageQueueEventType.ATLAS_CREATED, **atlas_data})
    return rmq_publisher.publish_event(MessageQueueEventType.ATLAS_CREATED, event)


def publish_atlas_updated(atlas_data):
    """Publish atlas updated event to RabbitMQ"""
    event = AtlasUpdatedEvent(**{"event_type": MessageQueueEventType.ATLAS_UPDATED, **atlas_data})
    return rmq_publisher.publish_event(MessageQueueEventType.ATLAS_UPDATED, event)


def publish_atlas_deleted(atlas_id):
    """Publish atlas deleted event to RabbitMQ"""
    event = AtlasDeletedEvent(event_type=MessageQueueEventType.ATLAS_DELETED, id=atlas_id)
    return rmq_publisher.publish_event(MessageQueueEventType.ATLAS_DELETED, event)


# ========== Atlas Tile DB Entity Mutations ==========
def publish_atlas_tile_created(tile_data):
    """Publish atlas tile created event to RabbitMQ"""
    event = AtlasTileCreatedEvent(**{"event_type": MessageQueueEventType.ATLAS_TILE_CREATED, **tile_data})
    return rmq_publisher.publish_event(MessageQueueEventType.ATLAS_TILE_CREATED, event)


def publish_atlas_tile_updated(tile_data):
    """Publish atlas tile updated event to RabbitMQ"""
    event = AtlasTileUpdatedEvent(**{"event_type": MessageQueueEventType.ATLAS_TILE_UPDATED, **tile_data})
    return rmq_publisher.publish_event(MessageQueueEventType.ATLAS_TILE_UPDATED, event)


def publish_atlas_tile_deleted(tile_id):
    """Publish atlas tile deleted event to RabbitMQ"""
    event = AtlasTileDeletedEvent(event_type=MessageQueueEventType.ATLAS_TILE_DELETED, id=tile_id)
    return rmq_publisher.publish_event(MessageQueueEventType.ATLAS_TILE_DELETED, event)


# ========== Grid DB Entity Mutations ==========
def publish_grid_created(grid_data):
    """Publish grid created event to RabbitMQ"""
    event = GridCreatedEvent(**{"event_type": MessageQueueEventType.GRID_CREATED, **grid_data})
    return rmq_publisher.publish_event(MessageQueueEventType.GRID_CREATED, event)


def publish_grid_updated(grid_data):
    """Publish grid updated event to RabbitMQ"""
    event = GridUpdatedEvent(**{"event_type": MessageQueueEventType.GRID_UPDATED, **grid_data})
    return rmq_publisher.publish_event(MessageQueueEventType.GRID_UPDATED, event)


def publish_grid_deleted(grid_id):
    """Publish grid deleted event to RabbitMQ"""
    event = GridDeletedEvent(event_type=MessageQueueEventType.GRID_DELETED, id=grid_id)
    return rmq_publisher.publish_event(MessageQueueEventType.GRID_DELETED, event)


# ========== Grid Square DB Entity Mutations ==========
def publish_gridsquare_created(gridsquare_data):
    """Publish grid square created event to RabbitMQ"""
    event = GridSquareCreatedEvent(**{"event_type": MessageQueueEventType.GRID_SQUARE_CREATED, **gridsquare_data})
    return rmq_publisher.publish_event(MessageQueueEventType.GRID_SQUARE_CREATED, event)


def publish_gridsquare_updated(gridsquare_data):
    """Publish grid square updated event to RabbitMQ"""
    event = GridSquareUpdatedEvent(**{"event_type": MessageQueueEventType.GRID_SQUARE_UPDATED, **gridsquare_data})
    return rmq_publisher.publish_event(MessageQueueEventType.GRID_SQUARE_UPDATED, event)


def publish_gridsquare_deleted(gridsquare_id):
    """Publish grid square deleted event to RabbitMQ"""
    event = GridSquareDeletedEvent(event_type=MessageQueueEventType.GRID_SQUARE_DELETED, id=gridsquare_id)
    return rmq_publisher.publish_event(MessageQueueEventType.GRID_SQUARE_DELETED, event)


# ========== Foil Hole DB Entity Mutations ==========
def publish_foilhole_created(foilhole_data):
    """Publish foil hole created event to RabbitMQ"""
    event = FoilHoleCreatedEvent(**{"event_type": MessageQueueEventType.FOIL_HOLE_CREATED, **foilhole_data})
    return rmq_publisher.publish_event(MessageQueueEventType.FOIL_HOLE_CREATED, event)


def publish_foilhole_updated(foilhole_data):
    """Publish foil hole updated event to RabbitMQ"""
    event = FoilHoleUpdatedEvent(**{"event_type": MessageQueueEventType.FOIL_HOLE_UPDATED, **foilhole_data})
    return rmq_publisher.publish_event(MessageQueueEventType.FOIL_HOLE_UPDATED, event)


def publish_foilhole_deleted(foilhole_id):
    """Publish foil hole deleted event to RabbitMQ"""
    event = FoilHoleDeletedEvent(event_type=MessageQueueEventType.FOIL_HOLE_DELETED, id=foilhole_id)
    return rmq_publisher.publish_event(MessageQueueEventType.FOIL_HOLE_DELETED, event)


# ========== Micrograph DB Entity Mutations ==========
def publish_micrograph_created(micrograph_data):
    """Publish micrograph created event to RabbitMQ"""
    event = MicrographCreatedEvent(**{"event_type": MessageQueueEventType.MICROGRAPH_CREATED, **micrograph_data})
    return rmq_publisher.publish_event(MessageQueueEventType.MICROGRAPH_CREATED, event)


def publish_micrograph_updated(micrograph_data):
    """Publish micrograph updated event to RabbitMQ"""
    event = MicrographUpdatedEvent(**{"event_type": MessageQueueEventType.MICROGRAPH_UPDATED, **micrograph_data})
    return rmq_publisher.publish_event(MessageQueueEventType.MICROGRAPH_UPDATED, event)


def publish_micrograph_deleted(micrograph_id):
    """Publish micrograph deleted event to RabbitMQ"""
    event = MicrographDeletedEvent(event_type=MessageQueueEventType.MICROGRAPH_DELETED, id=micrograph_id)
    return rmq_publisher.publish_event(MessageQueueEventType.MICROGRAPH_DELETED, event)
