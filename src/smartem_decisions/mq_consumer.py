#!/usr/bin/env python

import argparse
import json
import logging
import signal
import sys
import time
from collections.abc import Callable
from datetime import datetime
from typing import Any

import pika
from dotenv import load_dotenv
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session as SqlAlchemySession

from smartem_decisions.log_manager import LogConfig, LogManager
from smartem_decisions.model.database import (
    Acquisition,
    Atlas,
    FoilHole,
    Grid,
    GridSquare,
    Micrograph,
)
from smartem_decisions.model.entity_status import (
    AcquisitionStatus,
    FoilHoleStatus,
    GridSquareStatus,
    GridStatus,
    MicrographStatus,
)
from smartem_decisions.model.mq_event import (
    AcquisitionCreatedEvent,
    AcquisitionDeletedEvent,
    AcquisitionUpdatedEvent,
    AtlasCreatedEvent,
    AtlasDeletedEvent,
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
    MessageQueueEventType,
    MicrographCreatedEvent,
    MicrographDeletedEvent,
    MicrographUpdatedEvent,
)
from smartem_decisions.utils import (
    load_conf,
    rmq_consumer,
    setup_postgres_connection,
)

load_dotenv(override=False)  # Don't override existing env vars as these might be coming from k8s
conf = load_conf()
db_engine = setup_postgres_connection()

# Initialize logger with default ERROR level (will be reconfigured in main())
log_manager = LogManager.get_instance("smartem_decisions")
logger = log_manager.configure(LogConfig(level=logging.ERROR, console=True))


def handle_acquisition_created(event_data: dict[str, Any], session: SqlAlchemySession) -> None:
    """
    Handle acquisition created event by creating an acquisition in the database

    Args:
        event_data: Event data for acquisition created
        session: Database session
    """
    try:
        event = AcquisitionCreatedEvent(**event_data)

        # noinspection PyTypeChecker
        existing = session.execute(select(Acquisition).where(Acquisition.uuid == event.uuid)).scalar_one_or_none()
        if existing:
            logger.warning(f"Acquisition with UUID {event.uuid} already exists, skipping creation")
            return

        acquisition = Acquisition(
            uuid=event.uuid,
            id=event.id,
            name=event.name,
            status=AcquisitionStatus(event.status),
            start_time=event.start_time,
            end_time=event.end_time,
            metadata=event.metadata,
        )
        session.add(acquisition)
        session.commit()
        logger.info(f"Created acquisition with UUID {acquisition.uuid}")

    except ValidationError as e:
        logger.error(f"Validation error processing acquisition created event: {e}")
    except Exception as e:
        session.rollback()
        logger.error(f"Error processing acquisition created event: {e}")


def handle_acquisition_updated(event_data: dict[str, Any], session: SqlAlchemySession) -> None:
    """
    Handle acquisition updated event by updating an acquisition in the database

    Args:
        event_data: Event data for acquisition updated
        session: Database session
    """
    try:
        event = AcquisitionUpdatedEvent(**event_data)

        acquisition = session.execute(select(Acquisition).where(Acquisition.uuid == event.uuid)).scalar_one_or_none()
        if not acquisition:
            logger.warning(f"Acquisition with UUID {event.uuid} not found, cannot update")
            return

        if event.name is not None:
            acquisition.name = event.name
        if event.status is not None:
            acquisition.status = AcquisitionStatus(event.status)
        if event.epu_id is not None:
            acquisition.id = event.epu_id
        if event.start_time is not None:
            acquisition.start_time = datetime.fromisoformat(event.start_time)
        if event.end_time is not None:
            acquisition.end_time = datetime.fromisoformat(event.end_time)
        if event.metadata is not None:
            # TODO change data model to avoid use of "metadata"
            #  Use setattr to avoid conflicts with the class-level metadata attribute, which is
            #  a special class-level attribute used to configure tables.
            acquisition.metadata = event.metadata

        session.commit()
        logger.info(f"Updated acquisition with UUID {acquisition.uuid}")

    except ValidationError as e:
        logger.error(f"Validation error processing acquisition updated event: {e}")
    except Exception as e:
        session.rollback()
        logger.error(f"Error processing acquisition updated event: {e}")


def handle_acquisition_deleted(event_data: dict[str, Any], session: SqlAlchemySession) -> None:
    """
    Handle acquisition deleted event by deleting an acquisition from the database

    Args:
        event_data: Event data for acquisition deleted
        session: Database session
    """
    try:
        event = AcquisitionDeletedEvent(**event_data)

        acquisition = session.execute(select(Acquisition).where(Acquisition.uuid == event.uuid)).scalar_one_or_none()
        if not acquisition:
            logger.warning(f"Acquisition with UUID {event.uuid} not found, cannot delete")
            return

        session.delete(acquisition)
        session.commit()
        logger.info(f"Deleted acquisition with UUID {event.uuid}")

    except ValidationError as e:
        logger.error(f"Validation error processing acquisition deleted event: {e}")
    except Exception as e:
        session.rollback()
        logger.error(f"Error processing acquisition deleted event: {e}")


def handle_atlas_created(event_data: dict[str, Any], session: SqlAlchemySession) -> None:
    """
    Handle atlas created event by creating an atlas in the database

    Args:
        event_data: Event data for atlas created
        session: Database session
    """
    try:
        event = AtlasCreatedEvent(**event_data)

        existing = session.execute(select(Atlas).where(Atlas.uuid == event.uuid)).scalar_one_or_none()
        if existing:
            logger.warning(f"Atlas with UUID {event.uuid} already exists, skipping creation")
            return

        atlas = Atlas(
            id=event.id, name=event.name, grid_id=event.grid_id, pixel_size=event.pixel_size, metadata=event.metadata
        )
        session.add(atlas)
        session.commit()
        logger.info(f"Created atlas with UUID {atlas.uuid}")

    except ValidationError as e:
        logger.error(f"Validation error processing atlas created event: {e}")
    except Exception as e:
        session.rollback()
        logger.error(f"Error processing atlas created event: {e}")


def handle_atlas_updated(event_data: dict[str, Any], session: SqlAlchemySession) -> None:
    """
    Handle atlas updated event by updating an atlas in the database

    Args:
        event_data: Event data for atlas updated
        session: Database session
    """
    try:
        event = AtlasUpdatedEvent(**event_data)

        atlas = session.execute(select(Atlas).where(Atlas.uuid == event.uuid)).scalar_one_or_none()
        if not atlas:
            logger.warning(f"Atlas with UUID {event.uuid} not found, cannot update")
            return

        if event.name is not None:
            atlas.name = event.name
        if event.grid_id is not None:
            atlas.grid_id = event.grid_id  # TODO debug
        if event.pixel_size is not None:
            atlas.pixel_size = event.pixel_size
        if event.metadata is not None:
            # TODO change data model to avoid use of "metadata"
            #  Use setattr to avoid conflicts with the class-level metadata attribute, which is
            #  a special class-level attribute used to configure tables.
            atlas.metadata = event.metadata

        session.commit()
        logger.info(f"Updated atlas with UUID {atlas.uuid}")

    except ValidationError as e:
        logger.error(f"Validation error processing atlas updated event: {e}")
    except Exception as e:
        session.rollback()
        logger.error(f"Error processing atlas updated event: {e}")


def handle_atlas_deleted(event_data: dict[str, Any], session: SqlAlchemySession) -> None:
    """
    Handle atlas deleted event by deleting an atlas from the database

    Args:
        event_data: Event data for atlas deleted
        session: Database session
    """
    try:
        event = AtlasDeletedEvent(**event_data)

        atlas = session.execute(select(Atlas).where(Atlas.uuid == event.uuid)).scalar_one_or_none()
        if not atlas:
            logger.warning(f"Atlas with UUID {event.uuid} not found, cannot delete")
            return

        session.delete(atlas)
        session.commit()
        logger.info(f"Deleted atlas with UUID {atlas.uuid}")

    except ValidationError as e:
        logger.error(f"Validation error processing atlas deleted event: {e}")
    except Exception as e:
        session.rollback()
        logger.error(f"Error processing atlas deleted event: {e}")


def handle_grid_created(event_data: dict[str, Any], session: SqlAlchemySession, channel, delivery_tag) -> bool:
    """
    Handle grid created event by creating a grid in the database

    Args:
        event_data: Event data for grid created
        session: Database session
        channel: RabbitMQ channel
        delivery_tag: Message delivery tag

    Returns:
        bool: True if successful, False if failed (already NACKed)
    """
    try:
        event = GridCreatedEvent(**event_data)

        # Check if parent acquisition exists
        if event.acquisition_uuid:
            acquisition = session.execute(
                select(Acquisition).where(Acquisition.uuid == event.acquisition_uuid)
            ).scalar_one_or_none()

            if not acquisition:
                logger.info(
                    f"Parent acquisition {event.acquisition_uuid} not found for grid {event.uuid}, requeuing..."
                )
                channel.basic_nack(delivery_tag=delivery_tag, requeue=True)
                return False

        # noinspection PyTypeChecker
        existing = session.execute(select(Grid).where(Grid.uuid == event.uuid)).scalar_one_or_none()
        if existing:
            logger.warning(f"Grid with UUID {event.uuid} already exists, skipping creation")
            return True

        grid = Grid(
            uuid=event.uuid,
            # id=event.id, TODO add organic ID at data intake parsing level
            acquisition_uuid=event.acquisition_uuid,
            name=event.name,
            status=GridStatus(event.status),
            data_dir=event.data_dir,
            atlas_dir=event.atlas_dir,
            scan_start_time=event.scan_start_time,
            scan_end_time=event.scan_end_time,
        )
        session.add(grid)
        session.commit()
        logger.info(f"Created grid with UUID {grid.uuid}")
        return True

    except ValidationError as e:
        logger.error(f"Validation error processing grid created event: {e}")
        channel.basic_nack(delivery_tag=delivery_tag, requeue=False)
        return False
    except Exception as e:
        session.rollback()
        logger.error(f"Error processing grid created event: {e}")
        channel.basic_nack(delivery_tag=delivery_tag, requeue=False)
        return False


def handle_grid_updated(event_data: dict[str, Any], session: SqlAlchemySession) -> None:
    try:
        event = GridUpdatedEvent(**event_data)

        grid = session.execute(select(Grid).where(Grid.uuid == event.uuid)).scalar_one_or_none()
        if not grid:
            logger.warning(f"Grid with UUID {event.uuid} not found, cannot update")
            return

        if event.name is not None:
            grid.name = event.name
        if event.status is not None:
            grid.status = GridStatus(event.status)
        if event.grid_id is not None:
            grid.grid_id = event.grid_id
        if event.metadata is not None:
            # TODO change data model to avoid use of "metadata"
            #  Use setattr to avoid conflicts with the class-level metadata attribute, which is
            #  a special class-level attribute used to configure tables.
            grid.metadata = event.metadata

        session.commit()
        logger.info(f"Updated grid with UUID {grid.uuid}")

    except ValidationError as e:
        logger.error(f"Validation error processing grid updated event: {e}")
    except Exception as e:
        session.rollback()
        logger.error(f"Error processing grid updated event: {e}")


def handle_grid_deleted(event_data: dict[str, Any], session: SqlAlchemySession) -> None:
    try:
        event = GridDeletedEvent(**event_data)

        grid = session.execute(select(Grid).where(Grid.uuid == event.uuid)).scalar_one_or_none()
        if not grid:
            logger.warning(f"Grid with UUID {event.uuid} not found, cannot delete")
            return

        session.delete(grid)
        session.commit()
        logger.info(f"Deleted grid with UUID {event.uuid}")

    except ValidationError as e:
        logger.error(f"Validation error processing grid deleted event: {e}")
    except Exception as e:
        session.rollback()
        logger.error(f"Error processing grid deleted event: {e}")


def handle_gridsquare_created(event_data: dict[str, Any], session: SqlAlchemySession, channel, delivery_tag) -> bool:
    try:
        event = GridSquareCreatedEvent(**event_data)

        # Check if parent grid exists
        if event.grid_uuid:
            grid = session.execute(select(Grid).where(Grid.uuid == event.grid_uuid)).scalar_one_or_none()

            if not grid:
                logger.info(f"Parent grid {event.grid_uuid} not found for gridsquare {event.uuid}, requeuing...")
                channel.basic_nack(delivery_tag=delivery_tag, requeue=True)
                return False

        existing = session.execute(select(GridSquare).where(GridSquare.uuid == event.uuid)).scalar_one_or_none()
        if existing:
            logger.warning(f"GridSquare with UUID {event.uuid} already exists, skipping creation")
            return True

        gridsquare = GridSquare(
            uuid=event.uuid,
            grid_uuid=event.grid_uuid,
            name=event.name,
            status=GridSquareStatus(event.status),
            id="",  # TODO natural ID if present
            metadata=event.metadata,
        )
        session.add(gridsquare)
        session.commit()
        logger.info(f"Created gridsquare with UUID {gridsquare.uuid}")
        return True

    except ValidationError as e:
        logger.error(f"Validation error processing gridsquare created event: {e}")
        channel.basic_nack(delivery_tag=delivery_tag, requeue=False)
        return False
    except Exception as e:
        session.rollback()
        logger.error(f"Error processing gridsquare created event: {e}")
        channel.basic_nack(delivery_tag=delivery_tag, requeue=False)
        return False


def handle_gridsquare_updated(event_data: dict[str, Any], session: SqlAlchemySession) -> None:
    try:
        event = GridSquareUpdatedEvent(**event_data)

        gridsquare = session.execute(select(GridSquare).where(GridSquare.uuid == event.uuid)).scalar_one_or_none()
        if not gridsquare:
            logger.warning(f"GridSquare with UUID {event.uuid} not found, cannot update")
            return

        if event.name is not None:
            gridsquare.name = event.name
        if event.status is not None:
            gridsquare.status = GridSquareStatus(event.status)
        if event.grid_uuid is not None:
            gridsquare.grid_uuid = event.grid_uuid
        if event.gridsquare_id is not None:
            gridsquare.gridsquare_id = event.gridsquare_id
        if event.metadata is not None:
            # TODO change data model to avoid use of "metadata"
            #  Use setattr to avoid conflicts with the class-level metadata attribute, which is
            #  a special class-level attribute used to configure tables.
            gridsquare.metadata = event.metadata

        session.commit()
        logger.info(f"Updated gridsquare with UUID {gridsquare.uuid}")

    except ValidationError as e:
        logger.error(f"Validation error processing gridsquare updated event: {e}")
    except Exception as e:
        session.rollback()
        logger.error(f"Error processing gridsquare updated event: {e}")


def handle_gridsquare_deleted(event_data: dict[str, Any], session: SqlAlchemySession) -> None:
    try:
        event = GridSquareDeletedEvent(**event_data)

        gridsquare = session.execute(select(GridSquare).where(GridSquare.uuid == event.uuid)).scalar_one_or_none()
        if not gridsquare:
            logger.warning(f"GridSquare with UUID {event.uuid} not found, cannot delete")
            return

        session.delete(gridsquare)
        session.commit()
        logger.info(f"Deleted gridsquare with UUID {event.uuid}")

    except ValidationError as e:
        logger.error(f"Validation error processing gridsquare deleted event: {e}")
    except Exception as e:
        session.rollback()
        logger.error(f"Error processing gridsquare deleted event: {e}")


def handle_foilhole_created(event_data: dict[str, Any], session: SqlAlchemySession, channel, delivery_tag) -> bool:
    try:
        event = FoilHoleCreatedEvent(**event_data)

        # Check if parent gridsquare exists
        if event.gridsquare_uuid:
            gridsquare = session.execute(
                select(GridSquare).where(GridSquare.uuid == event.gridsquare_uuid)
            ).scalar_one_or_none()

            if not gridsquare:
                logger.info(
                    f"Parent gridsquare {event.gridsquare_uuid} not found for foilhole {event.uuid}, requeuing..."
                )
                channel.basic_nack(delivery_tag=delivery_tag, requeue=True)
                return False

        existing = session.execute(select(FoilHole).where(FoilHole.uuid == event.uuid)).scalar_one_or_none()
        if existing:
            logger.warning(f"FoilHole with UUID {event.uuid} already exists, skipping creation")
            return True

        foilhole = FoilHole(
            uuid=event.uuid,
            gridsquare_uuid=event.gridsquare_uuid,
            gridsquare_id=event.gridsquare_id,
            foilhole_id=event.foilhole_id,
            status=FoilHoleStatus(event.status) if event.status else FoilHoleStatus.NONE,
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
        logger.info(f"Created foilhole with UUID {foilhole.uuid}")
        return True

    except ValidationError as e:
        logger.error(f"Validation error processing foilhole created event: {e}")
        channel.basic_nack(delivery_tag=delivery_tag, requeue=False)
        return False
    except Exception as e:
        session.rollback()
        logger.error(f"Error processing foilhole created event: {e}")
        channel.basic_nack(delivery_tag=delivery_tag, requeue=False)
        return False


def handle_foilhole_updated(event_data: dict[str, Any], session: SqlAlchemySession) -> None:
    try:
        event = FoilHoleUpdatedEvent(**event_data)

        foilhole = session.execute(select(FoilHole).where(FoilHole.uuid == event.uuid)).scalar_one_or_none()
        if not foilhole:
            logger.warning(f"FoilHole with UUID {event.uuid} not found, cannot update")
            return

        if event.status is not None:
            foilhole.status = FoilHoleStatus(event.status)
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
            foilhole.diameter = event.diameter  # TODO
        if hasattr(event, "is_near_grid_bar") and event.is_near_grid_bar is not None:
            foilhole.is_near_grid_bar = event.is_near_grid_bar

        session.commit()
        logger.info(f"Updated foilhole with UUID {foilhole.uuid}")

    except ValidationError as e:
        logger.error(f"Validation error processing foilhole updated event: {e}")
    except Exception as e:
        session.rollback()
        logger.error(f"Error processing foilhole updated event: {e}")


def handle_foilhole_deleted(event_data: dict[str, Any], session: SqlAlchemySession) -> None:
    try:
        event = FoilHoleDeletedEvent(**event_data)

        foilhole = session.execute(select(FoilHole).where(FoilHole.uuid == event.uuid)).scalar_one_or_none()
        if not foilhole:
            logger.warning(f"FoilHole with UUID {event.id} not found, cannot delete")
            return

        session.delete(foilhole)
        session.commit()
        logger.info(f"Deleted foilhole with UUID {event.id}")

    except ValidationError as e:
        logger.error(f"Validation error processing foilhole deleted event: {e}")
    except Exception as e:
        session.rollback()
        logger.error(f"Error processing foilhole deleted event: {e}")


def handle_micrograph_created(event_data: dict[str, Any], session: SqlAlchemySession, channel, delivery_tag) -> bool:
    try:
        event = MicrographCreatedEvent(**event_data)

        # Check if parent foilhole exists
        if event.foilhole_uuid:
            foilhole = session.execute(
                select(FoilHole).where(FoilHole.uuid == event.foilhole_uuid)
            ).scalar_one_or_none()

            if not foilhole:
                logger.info(
                    f"Parent foilhole {event.foilhole_uuid} not found for micrograph {event.uuid}, requeuing..."
                )
                channel.basic_nack(delivery_tag=delivery_tag, requeue=True)
                return False

        existing = session.execute(select(Micrograph).where(Micrograph.uuid == event.uuid)).scalar_one_or_none()
        if existing:
            logger.warning(f"Micrograph with UUID {event.uuid} already exists, skipping creation")
            return True

        micrograph = Micrograph(
            uuid=event.uuid,
            micrograph_id=event.uuid,  # TODO
            foilhole_uuid=event.foilhole_uuid,
            foilhole_id=event.foilhole_id,
            location_id=event.location_id if hasattr(event, "location_id") else None,
            status=MicrographStatus(event.status)
            if hasattr(event, "status") and event.status is not None
            else MicrographStatus.NONE,
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
            ctf_max_resolution_estimate=event.ctf_max_resolution_estimate
            if hasattr(event, "ctf_max_resolution_estimate")
            else None,
        )
        session.add(micrograph)
        session.commit()
        logger.info(f"Created micrograph with UUID {micrograph.uuid}")
        return True

    except ValidationError as e:
        logger.error(f"Validation error processing micrograph created event: {e}")
        channel.basic_nack(delivery_tag=delivery_tag, requeue=False)
        return False
    except Exception as e:
        session.rollback()
        logger.error(f"Error processing micrograph created event: {e}")
        channel.basic_nack(delivery_tag=delivery_tag, requeue=False)
        return False


def handle_micrograph_updated(event_data: dict[str, Any], session: SqlAlchemySession) -> None:
    try:
        event = MicrographUpdatedEvent(**event_data)

        micrograph = session.execute(select(Micrograph).where(Micrograph.uuid == event.uuid)).scalar_one_or_none()
        if not micrograph:
            logger.warning(f"Micrograph with UUID {event.uuid} not found, cannot update")
            return

        if event.status is not None:
            micrograph.status = MicrographStatus(event.status)
        if hasattr(event, "foilhole_uuid") and event.foilhole_uuid is not None:
            micrograph.foilhole_uuid = event.foilhole_uuid
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
        if hasattr(event, "number_of_particles_picked") and event.number_of_particles_picked is not None:
            micrograph.number_of_particles_picked = event.number_of_particles_picked
        if hasattr(event, "number_of_particles_selected") and event.number_of_particles_selected is not None:
            micrograph.number_of_particles_selected = event.number_of_particles_selected
        if hasattr(event, "number_of_particles_rejected") and event.number_of_particles_rejected is not None:
            micrograph.number_of_particles_rejected = event.number_of_particles_rejected
        if hasattr(event, "selection_distribution") and event.selection_distribution is not None:
            micrograph.selection_distribution = event.selection_distribution
        if hasattr(event, "pick_distribution") and event.pick_distribution is not None:
            micrograph.pick_distribution = event.pick_distribution

        session.commit()
        logger.info(f"Updated micrograph with UUID {micrograph.uuid}")

    except ValidationError as e:
        logger.error(f"Validation error processing micrograph updated event: {e}")
    except Exception as e:
        session.rollback()
        logger.error(f"Error processing micrograph updated event: {e}")


def handle_micrograph_deleted(event_data: dict[str, Any], session: SqlAlchemySession) -> None:
    try:
        event = MicrographDeletedEvent(**event_data)

        micrograph = session.execute(select(Micrograph).where(Micrograph.uuid == event.uuid)).scalar_one_or_none()
        if not micrograph:
            logger.warning(f"Micrograph with UUID {event.uuid} not found, cannot delete")
            return

        session.delete(micrograph)
        session.commit()
        logger.info(f"Deleted micrograph with UUID {event.uuid}")

    except ValidationError as e:
        logger.error(f"Validation error processing micrograph deleted event: {e}")
    except Exception as e:
        session.rollback()
        logger.error(f"Error processing micrograph deleted event: {e}")


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
        MessageQueueEventType.GRID_UPDATED.value: handle_grid_updated,
        MessageQueueEventType.GRID_DELETED.value: handle_grid_deleted,
        MessageQueueEventType.GRIDSQUARE_CREATED.value: handle_gridsquare_created,
        MessageQueueEventType.GRIDSQUARE_UPDATED.value: handle_gridsquare_updated,
        MessageQueueEventType.GRIDSQUARE_DELETED.value: handle_gridsquare_deleted,
        MessageQueueEventType.FOILHOLE_CREATED.value: handle_foilhole_created,
        MessageQueueEventType.FOILHOLE_UPDATED.value: handle_foilhole_updated,
        MessageQueueEventType.FOILHOLE_DELETED.value: handle_foilhole_deleted,
        MessageQueueEventType.MICROGRAPH_CREATED.value: handle_micrograph_created,
        MessageQueueEventType.MICROGRAPH_UPDATED.value: handle_micrograph_updated,
        MessageQueueEventType.MICROGRAPH_DELETED.value: handle_micrograph_deleted,
        # TODO: Add handlers for all other event types as needed
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
    # Get retry count from message headers only once
    retry_count = 0
    if properties.headers and "x-retry-count" in properties.headers:
        retry_count = properties.headers["x-retry-count"]

    # Default event_type
    event_type = "unknown"

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

            # For handlers that support the new signature (parent validation)
            if event_type in [
                MessageQueueEventType.GRID_CREATED.value,
                MessageQueueEventType.FOILHOLE_CREATED.value,
                MessageQueueEventType.GRIDSQUARE_CREATED.value,
                MessageQueueEventType.MICROGRAPH_CREATED.value,
            ]:
                success = handler(message, session, ch, method.delivery_tag)
                if success:
                    ch.basic_ack(delivery_tag=method.delivery_tag)
                # Handler will have already NACKed if it failed
            else:
                # Legacy handlers - just call them and ACK
                handler(message, session)
                ch.basic_ack(delivery_tag=method.delivery_tag)
        logger.debug(f"Successfully processed {event_type} event")

    except json.JSONDecodeError:
        logger.error(f"Failed to decode JSON message: {body.decode()}")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

    except Exception as e:
        logger.error(f"Error processing message: {e}")

        if retry_count >= 3:
            logger.warning(f"Message failed after {retry_count} retries, dropping message")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        else:
            # Republish with incremented retry count
            headers = properties.headers or {}
            headers["x-retry-count"] = retry_count + 1

            logger.debug(f"Republishing message with retry count {retry_count + 1}, event_type: {event_type}")

            try:
                ch.basic_publish(
                    exchange="",
                    routing_key=method.routing_key,
                    body=body,
                    properties=pika.BasicProperties(headers=headers),
                )
                ch.basic_ack(delivery_tag=method.delivery_tag)
            except Exception as republish_error:
                logger.error(f"Failed to republish message: {republish_error}")
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)


def signal_handler(signum, frame):
    """Handle shutdown signals"""
    logger.info("Received shutdown signal, stopping consumer...")
    rmq_consumer.stop_consuming()
    rmq_consumer.close()
    sys.exit(0)


def main():
    """Main function to run the consumer"""
    parser = argparse.ArgumentParser(description="SmartEM Decisions MQ Consumer")
    parser.add_argument(
        "-v", "--verbose", action="count", default=0, help="Increase verbosity (-v for INFO, -vv for DEBUG)"
    )
    args = parser.parse_args()

    # Configure logging based on verbosity level
    if args.verbose >= 2:  # Debug level -vv
        log_level = logging.DEBUG
    elif args.verbose == 1:  # Info level -v
        log_level = logging.INFO
    else:  # Default - only errors
        log_level = logging.ERROR

    # Reconfigure logger with the specified verbosity level
    global logger
    logger = log_manager.configure(LogConfig(level=log_level, console=True, file_path="smartem_decisions-core.log"))

    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    while True:
        try:
            logger.info("Starting RabbitMQ consumer...")
            rmq_consumer.consume(on_message, prefetch_count=1)
        except KeyboardInterrupt:
            logger.info("Consumer stopped by user")
            break
        except Exception as e:
            logger.error(f"Error in consumer: {e}")
            logger.info("Retrying in 10 seconds...")
            time.sleep(10)

    rmq_consumer.close()


if __name__ == "__main__":
    main()
