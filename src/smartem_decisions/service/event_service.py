from smartem_decisions.rabbitmq_publisher import EventType
from src.smartem_decisions.utils import rmq_publisher
from smartem_decisions.model.rmq_event_models import (
    AcquisitionCreatedEvent, AcquisitionUpdatedEvent, AcquisitionDeletedEvent,
    AtlasCreatedEvent, AtlasUpdatedEvent, AtlasDeletedEvent,
    AtlasTileCreatedEvent, AtlasTileUpdatedEvent, AtlasTileDeletedEvent,
    GridCreatedEvent, GridUpdatedEvent, GridDeletedEvent,
    GridSquareCreatedEvent, GridSquareUpdatedEvent, GridSquareDeletedEvent,
    FoilHoleCreatedEvent, FoilHoleUpdatedEvent, FoilHoleDeletedEvent,
    MicrographCreatedEvent, MicrographUpdatedEvent, MicrographDeletedEvent
)


# ========== Acquisition Operations ==========
def publish_acquisition_created(acquisition_data):
    """Publish acquisition created event to RabbitMQ"""
    event = AcquisitionCreatedEvent(**acquisition_data)
    return rmq_publisher.publish_event(EventType.ACQUISITION_CREATED, event)


def publish_acquisition_updated(acquisition_data):
    """Publish acquisition updated event to RabbitMQ"""
    event = AcquisitionUpdatedEvent(**acquisition_data)
    return rmq_publisher.publish_event(EventType.ACQUISITION_UPDATED, event)


def publish_acquisition_deleted(acquisition_id):
    """Publish acquisition deleted event to RabbitMQ"""
    event = AcquisitionDeletedEvent(id=acquisition_id)
    return rmq_publisher.publish_event(EventType.ACQUISITION_DELETED, event)


# ========== Atlas Operations ==========
def publish_atlas_created(atlas_data):
    """Publish atlas created event to RabbitMQ"""
    event = AtlasCreatedEvent(**atlas_data)
    return rmq_publisher.publish_event(EventType.ATLAS_CREATED, event)


def publish_atlas_updated(atlas_data):
    """Publish atlas updated event to RabbitMQ"""
    event = AtlasUpdatedEvent(**atlas_data)
    return rmq_publisher.publish_event(EventType.ATLAS_UPDATED, event)


def publish_atlas_deleted(atlas_id):
    """Publish atlas deleted event to RabbitMQ"""
    event = AtlasDeletedEvent(id=atlas_id)
    return rmq_publisher.publish_event(EventType.ATLAS_DELETED, event)


# ========== Atlas Tile Operations ==========
def publish_atlas_tile_created(tile_data):
    """Publish atlas tile created event to RabbitMQ"""
    event = AtlasTileCreatedEvent(**tile_data)
    return rmq_publisher.publish_event(EventType.ATLAS_TILE_CREATED, event)


def publish_atlas_tile_updated(tile_data):
    """Publish atlas tile updated event to RabbitMQ"""
    event = AtlasTileUpdatedEvent(**tile_data)
    return rmq_publisher.publish_event(EventType.ATLAS_TILE_UPDATED, event)


def publish_atlas_tile_deleted(tile_id):
    """Publish atlas tile deleted event to RabbitMQ"""
    event = AtlasTileDeletedEvent(id=tile_id)
    return rmq_publisher.publish_event(EventType.ATLAS_TILE_DELETED, event)


# ========== Grid Operations ==========
def publish_grid_created(grid_data):
    """Publish grid created event to RabbitMQ"""
    event = GridCreatedEvent(**grid_data)
    return rmq_publisher.publish_event(EventType.GRID_CREATED, event)


def publish_grid_updated(grid_data):
    """Publish grid updated event to RabbitMQ"""
    event = GridUpdatedEvent(**grid_data)
    return rmq_publisher.publish_event(EventType.GRID_UPDATED, event)


def publish_grid_deleted(grid_id):
    """Publish grid deleted event to RabbitMQ"""
    event = GridDeletedEvent(id=grid_id)
    return rmq_publisher.publish_event(EventType.GRID_DELETED, event)


# ========== Grid Square Operations ==========
def publish_gridsquare_created(gridsquare_data):
    """Publish grid square created event to RabbitMQ"""
    event = GridSquareCreatedEvent(**gridsquare_data)
    return rmq_publisher.publish_event(EventType.GRID_SQUARE_CREATED, event)


def publish_gridsquare_updated(gridsquare_data):
    """Publish grid square updated event to RabbitMQ"""
    event = GridSquareUpdatedEvent(**gridsquare_data)
    return rmq_publisher.publish_event(EventType.GRID_SQUARE_UPDATED, event)


def publish_gridsquare_deleted(gridsquare_id):
    """Publish grid square deleted event to RabbitMQ"""
    event = GridSquareDeletedEvent(id=gridsquare_id)
    return rmq_publisher.publish_event(EventType.GRID_SQUARE_DELETED, event)


# ========== Foil Hole Operations ==========
def publish_foilhole_created(foilhole_data):
    """Publish foil hole created event to RabbitMQ"""
    event = FoilHoleCreatedEvent(**foilhole_data)
    return rmq_publisher.publish_event(EventType.FOIL_HOLE_CREATED, event)


def publish_foilhole_updated(foilhole_data):
    """Publish foil hole updated event to RabbitMQ"""
    event = FoilHoleUpdatedEvent(**foilhole_data)
    return rmq_publisher.publish_event(EventType.FOIL_HOLE_UPDATED, event)


def publish_foilhole_deleted(foilhole_id):
    """Publish foil hole deleted event to RabbitMQ"""
    event = FoilHoleDeletedEvent(id=foilhole_id)
    return rmq_publisher.publish_event(EventType.FOIL_HOLE_DELETED, event)


# ========== Micrograph Operations ==========
def publish_micrograph_created(micrograph_data):
    """Publish micrograph created event to RabbitMQ"""
    event = MicrographCreatedEvent(**micrograph_data)
    return rmq_publisher.publish_event(EventType.MICROGRAPH_CREATED, event)


def publish_micrograph_updated(micrograph_data):
    """Publish micrograph updated event to RabbitMQ"""
    event = MicrographUpdatedEvent(**micrograph_data)
    return rmq_publisher.publish_event(EventType.MICROGRAPH_UPDATED, event)


def publish_micrograph_deleted(micrograph_id):
    """Publish micrograph deleted event to RabbitMQ"""
    event = MicrographDeletedEvent(id=micrograph_id)
    return rmq_publisher.publish_event(EventType.MICROGRAPH_DELETED, event)
