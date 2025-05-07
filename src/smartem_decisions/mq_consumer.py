#!/usr/bin/env python

import json
from typing import Any, Callable

from dotenv import load_dotenv
from sqlalchemy.orm import Session as SqlAlchemySession
from pydantic import ValidationError

from src.smartem_decisions.log_manager import logger
from src.smartem_decisions.utils import (
    load_conf,
    setup_postgres_connection,
    rmq_consumer,
)
from src.smartem_decisions.model.mq_event import (
    MessageQueueEventType,
    AcquisitionCreatedEvent,
    AcquisitionUpdatedEvent,
    AcquisitionDeletedEvent,
    AtlasCreatedEvent,
    AtlasUpdatedEvent,
    AtlasDeletedEvent,
    GridCreatedEvent,
    GridUpdatedEvent,
    GridDeletedEvent,
    GridSquareCreatedEvent,
    GridSquareUpdatedEvent,
    GridSquareDeletedEvent,
    FoilHoleCreatedEvent,
    FoilHoleUpdatedEvent,
    FoilHoleDeletedEvent,
    MicrographCreatedEvent,
    MicrographUpdatedEvent,
    MicrographDeletedEvent,
)
from src.smartem_decisions.model.database import (
    Acquisition,
    Atlas,
    Grid,
    GridSquare,
    FoilHole,
    Micrograph,
)


load_dotenv()
conf = load_conf()
db_engine = setup_postgres_connection()


def handle_acquisition_created(event_data: dict[str, Any], session: SqlAlchemySession) -> None:
    """
    Handle acquisition created event by creating an acquisition in the database

    Args:
        event_data: Event data for acquisition created
        session: Database session
    """
    try:
        event = AcquisitionCreatedEvent(**event_data)

        existing = session.query(Acquisition).filter(Acquisition.id == event.id).first()
        if existing:
            logger.warning(f"Acquisition with ID {event.id} already exists, skipping creation")
            return

        acquisition = Acquisition(
            id=event.id,
            name=event.name,
            status=event.status,
            epu_id=event.epu_id,
            start_time=event.start_time,
            end_time=event.end_time,
            metadata=event.metadata,
        )
        session.add(acquisition)
        session.commit()
        logger.info(f"Created acquisition with ID {acquisition.id}")

    except ValidationError as e:
        logger.error(f"Validation error processing acquisition created event: {e}")
    except Exception as e:
        session.rollback()
        logger.error(f"Error processing acquisition created event: {e}")
        raise


def handle_acquisition_updated(event_data: dict[str, Any], session: SqlAlchemySession) -> None:
    """
    Handle acquisition updated event by updating an acquisition in the database

    Args:
        event_data: Event data for acquisition updated
        session: Database session
    """
    try:
        event = AcquisitionUpdatedEvent(**event_data)

        acquisition = session.query(Acquisition).filter(Acquisition.id == event.id).first()
        if not acquisition:
            logger.warning(f"Acquisition with ID {event.id} not found, cannot update")
            return

        if event.name is not None:
            acquisition.name = event.name
        if event.status is not None:
            acquisition.status = event.status
        if event.epu_id is not None:
            acquisition.id = event.epu_id
        if event.start_time is not None:
            acquisition.start_time = event.start_time
        if event.end_time is not None:
            acquisition.end_time = event.end_time
        if event.metadata is not None:
            acquisition.metadata = event.metadata

        session.commit()
        logger.info(f"Updated acquisition with ID {acquisition.id}")

    except ValidationError as e:
        logger.error(f"Validation error processing acquisition updated event: {e}")
    except Exception as e:
        session.rollback()
        logger.error(f"Error processing acquisition updated event: {e}")
        raise


def handle_acquisition_deleted(event_data: dict[str, Any], session: SqlAlchemySession) -> None:
    """
    Handle acquisition deleted event by deleting an acquisition from the database

    Args:
        event_data: Event data for acquisition deleted
        session: Database session
    """
    try:
        event = AcquisitionDeletedEvent(**event_data)

        acquisition = session.query(Acquisition).filter(Acquisition.id == event.id).first()
        if not acquisition:
            logger.warning(f"Acquisition with ID {event.id} not found, cannot delete")
            return

        session.delete(acquisition)
        session.commit()
        logger.info(f"Deleted acquisition with ID {event.id}")

    except ValidationError as e:
        logger.error(f"Validation error processing acquisition deleted event: {e}")
    except Exception as e:
        session.rollback()
        logger.error(f"Error processing acquisition deleted event: {e}")
        raise


def handle_atlas_created(event_data: dict[str, Any], session: SqlAlchemySession) -> None:
    """
    Handle atlas created event by creating an atlas in the database

    Args:
        event_data: Event data for atlas created
        session: Database session
    """
    try:
        event = AtlasCreatedEvent(**event_data)

        existing = session.query(Atlas).filter(Atlas.id == event.id).first()
        if existing:
            logger.warning(f"Atlas with ID {event.id} already exists, skipping creation")
            return

        atlas = Atlas(
            id=event.id, name=event.name, grid_id=event.grid_id, pixel_size=event.pixel_size, metadata=event.metadata
        )
        session.add(atlas)
        session.commit()
        logger.info(f"Created atlas with ID {atlas.id}")

    except ValidationError as e:
        logger.error(f"Validation error processing atlas created event: {e}")
    except Exception as e:
        session.rollback()
        logger.error(f"Error processing atlas created event: {e}")
        raise


def handle_atlas_updated(event_data: dict[str, Any], session: SqlAlchemySession) -> None:
    """
    Handle atlas updated event by updating an atlas in the database

    Args:
        event_data: Event data for atlas updated
        session: Database session
    """
    try:
        event = AtlasUpdatedEvent(**event_data)

        atlas = session.query(Atlas).filter(Atlas.id == event.id).first()
        if not atlas:
            logger.warning(f"Atlas with ID {event.id} not found, cannot update")
            return

        if event.name is not None:
            atlas.name = event.name
        if event.grid_id is not None:
            atlas.grid_id = event.grid_id
        if event.pixel_size is not None:
            atlas.pixel_size = event.pixel_size
        if event.metadata is not None:
            atlas.metadata = event.metadata

        session.commit()
        logger.info(f"Updated atlas with ID {atlas.id}")

    except ValidationError as e:
        logger.error(f"Validation error processing atlas updated event: {e}")
    except Exception as e:
        session.rollback()
        logger.error(f"Error processing atlas updated event: {e}")
        raise


def handle_atlas_deleted(event_data: dict[str, Any], session: SqlAlchemySession) -> None:
    """
    Handle atlas deleted event by deleting an atlas from the database

    Args:
        event_data: Event data for atlas deleted
        session: Database session
    """
    try:
        event = AtlasDeletedEvent(**event_data)

        atlas = session.query(Atlas).filter(Atlas.id == event.id).first()
        if not atlas:
            logger.warning(f"Atlas with ID {event.id} not found, cannot delete")
            return

        session.delete(atlas)
        session.commit()
        logger.info(f"Deleted atlas with ID {atlas.id}")

    except ValidationError as e:
        logger.error(f"Validation error processing atlas deleted event: {e}")
    except Exception as e:
        session.rollback()
        logger.error(f"Error processing atlas deleted event: {e}")
        raise


def handle_grid_created(event_data: dict[str, Any], session: SqlAlchemySession) -> None:
    """
    Handle grid created event by creating a grid in the database

    Args:
        event_data: Event data for grid created
        session: Database session
    """
    try:
        event = GridCreatedEvent(**event_data)

        existing = session.query(Grid).filter(Grid.id == event.id).first()
        if existing:
            logger.warning(f"Grid with ID {event.id} already exists, skipping creation")
            return

        grid = Grid(
            id=event.id,
            acquisition_id=event.acquisition_id,
            name=event.name,
            status=event.status,
            data_dir=event.data_dir,
            atlas_dir=event.atlas_dir,
            scan_start_time=event.scan_start_time,
            scan_end_time=event.scan_end_time,
        )
        session.add(grid)
        session.commit()
        logger.info(f"Created grid with ID {grid.id}")

    except ValidationError as e:
        logger.error(f"Validation error processing grid created event: {e}")
    except Exception as e:
        session.rollback()
        logger.error(f"Error processing grid created event: {e}")
        raise


def handle_grid_updated(event_data: dict[str, Any], session: SqlAlchemySession) -> None:
    try:
        event = GridUpdatedEvent(**event_data)

        grid = session.query(Grid).filter(Grid.id == event.id).first()
        if not grid:
            logger.warning(f"Grid with ID {event.id} not found, cannot update")
            return

        if event.name is not None:
            grid.name = event.name
        if event.status is not None:
            grid.status = event.status
        if event.grid_id is not None:
            grid.grid_id = event.grid_id
        if event.metadata is not None:
            grid.metadata = event.metadata

        session.commit()
        logger.info(f"Updated grid with ID {grid.id}")

    except ValidationError as e:
        logger.error(f"Validation error processing grid updated event: {e}")
    except Exception as e:
        session.rollback()
        logger.error(f"Error processing grid updated event: {e}")
        raise


def handle_grid_deleted(event_data: dict[str, Any], session: SqlAlchemySession) -> None:
    try:
        event = GridDeletedEvent(**event_data)

        grid = session.query(Grid).filter(Grid.id == event.id).first()
        if not grid:
            logger.warning(f"Grid with ID {event.id} not found, cannot delete")
            return

        session.delete(grid)
        session.commit()
        logger.info(f"Deleted grid with ID {event.id}")

    except ValidationError as e:
        logger.error(f"Validation error processing grid deleted event: {e}")
    except Exception as e:
        session.rollback()
        logger.error(f"Error processing grid deleted event: {e}")
        raise


def handle_gridsquare_created(event_data: dict[str, Any], session: SqlAlchemySession) -> None:
    try:
        event = GridSquareCreatedEvent(**event_data)

        existing = session.query(GridSquare).filter(GridSquare.id == event.id).first()
        if existing:
            logger.warning(f"GridSquare with ID {event.id} already exists, skipping creation")
            return

        gridsquare = GridSquare(
            id=event.id,
            grid_id=event.grid_id,
            name=event.name,
            status=event.status,
            gridsquare_id=event.id,
            metadata=event.metadata,
        )
        session.add(gridsquare)
        session.commit()
        logger.info(f"Created gridsquare with ID {gridsquare.id}")

    except ValidationError as e:
        logger.error(f"Validation error processing gridsquare created event: {e}")
    except Exception as e:
        session.rollback()
        logger.error(f"Error processing gridsquare created event: {e}")
        raise


def handle_gridsquare_updated(event_data: dict[str, Any], session: SqlAlchemySession) -> None:
    try:
        event = GridSquareUpdatedEvent(**event_data)

        gridsquare = session.query(GridSquare).filter(GridSquare.id == event.id).first()
        if not gridsquare:
            logger.warning(f"GridSquare with ID {event.id} not found, cannot update")
            return

        if event.name is not None:
            gridsquare.name = event.name
        if event.status is not None:
            gridsquare.status = event.status
        if event.grid_id is not None:
            gridsquare.grid_id = event.grid_id
        if event.gridsquare_id is not None:
            gridsquare.gridsquare_id = event.gridsquare_id
        if event.metadata is not None:
            gridsquare.metadata = event.metadata

        session.commit()
        logger.info(f"Updated gridsquare with ID {gridsquare.id}")

    except ValidationError as e:
        logger.error(f"Validation error processing gridsquare updated event: {e}")
    except Exception as e:
        session.rollback()
        logger.error(f"Error processing gridsquare updated event: {e}")
        raise


def handle_gridsquare_deleted(event_data: dict[str, Any], session: SqlAlchemySession) -> None:
    try:
        event = GridSquareDeletedEvent(**event_data)

        gridsquare = session.query(GridSquare).filter(GridSquare.id == event.id).first()
        if not gridsquare:
            logger.warning(f"GridSquare with ID {event.id} not found, cannot delete")
            return

        session.delete(gridsquare)
        session.commit()
        logger.info(f"Deleted gridsquare with ID {event.id}")

    except ValidationError as e:
        logger.error(f"Validation error processing gridsquare deleted event: {e}")
    except Exception as e:
        session.rollback()
        logger.error(f"Error processing gridsquare deleted event: {e}")
        raise


def handle_foilhole_created(event_data: dict[str, Any], session: SqlAlchemySession) -> None:
    try:
        event = FoilHoleCreatedEvent(**event_data)

        existing = session.query(FoilHole).filter(FoilHole.id == event.id).first()
        if existing:
            logger.warning(f"FoilHole with ID {event.id} already exists, skipping creation")
            return

        foilhole = FoilHole(
            id=event.id,
            gridsquare_id=event.gridsquare_id,
            status=event.status,
            foilhole_id=event.id,
            center_x=event.center_x,
            center_y=event.center_y,
            quality=event.quality,
            rotation=event.rotation,
            size_width=event.size_width,
            size_height=event.size_height,
            x_location=event.x_location,
            y_location=event.y_location,
            x_stage_position=event.x_stage_position,
            y_stage_position=event.y_stage_position,
            diameter=event.diameter,
            is_near_grid_bar=event.is_near_grid_bar if hasattr(event, "is_near_grid_bar") else False,
        )
        session.add(foilhole)
        session.commit()
        logger.info(f"Created foilhole with ID {foilhole.id}")

    except ValidationError as e:
        logger.error(f"Validation error processing foilhole created event: {e}")
    except Exception as e:
        session.rollback()
        logger.error(f"Error processing foilhole created event: {e}")
        raise


def handle_foilhole_updated(event_data: dict[str, Any], session: SqlAlchemySession) -> None:
    try:
        event = FoilHoleUpdatedEvent(**event_data)

        foilhole = session.query(FoilHole).filter(FoilHole.id == event.id).first()
        if not foilhole:
            logger.warning(f"FoilHole with ID {event.id} not found, cannot update")
            return

        if event.status is not None:
            foilhole.status = event.status
        if event.gridsquare_id is not None:
            foilhole.gridsquare_id = event.gridsquare_id
        if event.foilhole_id is not None:
            foilhole.foilhole_id = event.foilhole_id
        if event.center_x is not None:
            foilhole.center_x = event.center_x
        if event.center_y is not None:
            foilhole.center_y = event.center_y
        if event.quality is not None:
            foilhole.quality = event.quality
        if event.rotation is not None:
            foilhole.rotation = event.rotation
        if event.size_width is not None:
            foilhole.size_width = event.size_width
        if event.size_height is not None:
            foilhole.size_height = event.size_height
        if event.x_location is not None:
            foilhole.x_location = event.x_location
        if event.y_location is not None:
            foilhole.y_location = event.y_location
        if event.x_stage_position is not None:
            foilhole.x_stage_position = event.x_stage_position
        if event.y_stage_position is not None:
            foilhole.y_stage_position = event.y_stage_position
        if event.diameter is not None:
            foilhole.diameter = event.diameter
        if hasattr(event, "is_near_grid_bar") and event.is_near_grid_bar is not None:
            foilhole.is_near_grid_bar = event.is_near_grid_bar

        session.commit()
        logger.info(f"Updated foilhole with ID {foilhole.id}")

    except ValidationError as e:
        logger.error(f"Validation error processing foilhole updated event: {e}")
    except Exception as e:
        session.rollback()
        logger.error(f"Error processing foilhole updated event: {e}")
        raise


def handle_foilhole_deleted(event_data: dict[str, Any], session: SqlAlchemySession) -> None:
    try:
        event = FoilHoleDeletedEvent(**event_data)

        foilhole = session.query(FoilHole).filter(FoilHole.id == event.id).first()
        if not foilhole:
            logger.warning(f"FoilHole with ID {event.id} not found, cannot delete")
            return

        session.delete(foilhole)
        session.commit()
        logger.info(f"Deleted foilhole with ID {event.id}")

    except ValidationError as e:
        logger.error(f"Validation error processing foilhole deleted event: {e}")
    except Exception as e:
        session.rollback()
        logger.error(f"Error processing foilhole deleted event: {e}")
        raise


def handle_micrograph_created(event_data: dict[str, Any], session: SqlAlchemySession) -> None:
    try:
        event = MicrographCreatedEvent(**event_data)

        existing = session.query(Micrograph).filter(Micrograph.id == event.id).first()
        if existing:
            logger.warning(f"Micrograph with ID {event.id} already exists, skipping creation")
            return

        micrograph = Micrograph(
            id=event.id,
            foilhole_id=event.foilhole_id,
            status=event.status,
            micrograph_id=event.id,
            location_id=event.location_id if hasattr(event, "location_id") else None,
            high_res_path=event.high_res_path if hasattr(event, "high_res_path") else None,
            manifest_file=event.manifest_file if hasattr(event, "manifest_file") else None,
            acquisition_datetime=event.acquisition_datetime if hasattr(event, "acquisition_datetime") else None,
            defocus=event.defocus if hasattr(event, "defocus") else None,
            detector_name=event.detector_name if hasattr(event, "detector_name") else None,
            energy_filter=event.energy_filter if hasattr(event, "energy_filter") else None,
            phase_plate=event.phase_plate if hasattr(event, "phase_plate") else None,
            image_size_x=event.image_size_x if hasattr(event, "image_size_x") else None,
            image_size_y=event.image_size_y if hasattr(event, "image_size_y") else None,
            binning_x=event.binning_x if hasattr(event, "binning_x") else None,
            binning_y=event.binning_y if hasattr(event, "binning_y") else None,
            total_motion=event.total_motion if hasattr(event, "total_motion") else None,
            average_motion=event.average_motion if hasattr(event, "average_motion") else None,
            ctf_max_resolution_estimate=event.ctf_max_resolution_estimate if hasattr(event, "ctf_max_resolution_estimate") else None,
        )
        session.add(micrograph)
        session.commit()
        logger.info(f"Created micrograph with ID {micrograph.id}")

    except ValidationError as e:
        logger.error(f"Validation error processing micrograph created event: {e}")
    except Exception as e:
        session.rollback()
        logger.error(f"Error processing micrograph created event: {e}")
        raise


def handle_micrograph_updated(event_data: dict[str, Any], session: SqlAlchemySession) -> None:
    try:
        event = MicrographUpdatedEvent(**event_data)

        micrograph = session.query(Micrograph).filter(Micrograph.id == event.id).first()
        if not micrograph:
            logger.warning(f"Micrograph with ID {event.id} not found, cannot update")
            return

        if event.status is not None:
            micrograph.status = event.status
        if event.foilhole_id is not None:
            micrograph.foilhole_id = event.foilhole_id
        if event.micrograph_id is not None:
            micrograph.micrograph_id = event.micrograph_id
        if event.location_id is not None:
            micrograph.location_id = event.location_id
        if event.high_res_path is not None:
            micrograph.high_res_path = event.high_res_path
        if event.manifest_file is not None:
            micrograph.manifest_file = event.manifest_file
        if event.acquisition_datetime is not None:
            micrograph.acquisition_datetime = event.acquisition_datetime
        if event.defocus is not None:
            micrograph.defocus = event.defocus
        if event.detector_name is not None:
            micrograph.detector_name = event.detector_name
        if event.energy_filter is not None:
            micrograph.energy_filter = event.energy_filter
        if event.phase_plate is not None:
            micrograph.phase_plate = event.phase_plate
        if event.image_size_x is not None:
            micrograph.image_size_x = event.image_size_x
        if event.image_size_y is not None:
            micrograph.image_size_y = event.image_size_y
        if event.binning_x is not None:
            micrograph.binning_x = event.binning_x
        if event.binning_y is not None:
            micrograph.binning_y = event.binning_y
        if event.total_motion is not None:
            micrograph.total_motion = event.total_motion
        if event.average_motion is not None:
            micrograph.average_motion = event.average_motion
        if event.ctf_max_resolution_estimate is not None:
            micrograph.ctf_max_resolution_estimate = event.ctf_max_resolution_estimate

        session.commit()
        logger.info(f"Updated micrograph with ID {micrograph.id}")

    except ValidationError as e:
        logger.error(f"Validation error processing micrograph updated event: {e}")
    except Exception as e:
        session.rollback()
        logger.error(f"Error processing micrograph updated event: {e}")
        raise


def handle_micrograph_deleted(event_data: dict[str, Any], session: SqlAlchemySession) -> None:
    try:
        event = MicrographDeletedEvent(**event_data)

        micrograph = session.query(Micrograph).filter(Micrograph.id == event.id).first()
        if not micrograph:
            logger.warning(f"Micrograph with ID {event.id} not found, cannot delete")
            return

        session.delete(micrograph)
        session.commit()
        logger.info(f"Deleted micrograph with ID {event.id}")

    except ValidationError as e:
        logger.error(f"Validation error processing micrograph deleted event: {e}")
    except Exception as e:
        session.rollback()
        logger.error(f"Error processing micrograph deleted event: {e}")
        raise


# Create a mapping from event types to their handler functions
def get_event_handlers() -> dict[str, Callable]:
    """
    Get a mapping of event types to their handler functions

    Returns:
        Dict[str, Callable]: Mapping of event type strings to handler functions
    """
    return {
        MessageQueueEventType.ACQUISITION_CREATED.value: handle_acquisition_created,
        MessageQueueEventType.ACQUISITION_UPDATED.value: handle_acquisition_updated,
        MessageQueueEventType.ACQUISITION_DELETED.value: handle_acquisition_deleted,
        MessageQueueEventType.ATLAS_CREATED.value: handle_atlas_created,
        MessageQueueEventType.ATLAS_UPDATED.value: handle_atlas_updated,
        MessageQueueEventType.ATLAS_DELETED.value: handle_atlas_deleted,
        MessageQueueEventType.GRID_CREATED.value: handle_grid_created,
        MessageQueueEventType.GRID_SQUARE_CREATED.value: handle_gridsquare_created,
        MessageQueueEventType.FOIL_HOLE_CREATED.value: handle_foilhole_created,
        MessageQueueEventType.MICROGRAPH_CREATED.value: handle_micrograph_created,
        # TODO: Add handlers for all other event types
    }


def on_message(ch, method, properties, body):
    """
    Callback function for processing RabbitMQ messages

    Args:
        ch: Channel object
        method: Method object
        properties: Properties object
        body: Message body
    """
    try:
        message = json.loads(body.decode())
        logger.info(f"Received message: {message}")

        if "event_type" not in message:
            logger.warning(f"Message missing 'event_type' field: {message}")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
            return

        event_type = message["event_type"]

        event_handlers = get_event_handlers()
        if event_type not in event_handlers:
            logger.warning(f"No handler registered for event type: {event_type}")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
            return

        with SqlAlchemySession(db_engine) as session:
            handler = event_handlers[event_type]
            handler(message, session)

        ch.basic_ack(delivery_tag=method.delivery_tag)
        logger.info(f"Successfully processed {event_type} event")

    except json.JSONDecodeError:
        logger.error(f"Failed to decode JSON message: {body.decode()}")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
    except Exception as e:
        logger.error(f"Error processing message: {e}")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)


def main():
    """Main function to run the consumer"""
    try:
        # Start consuming messages with the on_message callback
        rmq_consumer.consume(on_message, prefetch_count=1)
    except KeyboardInterrupt:
        logger.info("Consumer stopped by user")
    except Exception as e:
        logger.error(f"Error in consumer: {e}")


if __name__ == "__main__":
    main()
