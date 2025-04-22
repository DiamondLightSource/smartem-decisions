#!/usr/bin/env python

import json
from typing import Dict, Any, Callable

from dotenv import load_dotenv
from sqlalchemy.orm import Session as SqlAlchemySession
from pydantic import ValidationError

from src.smartem_decisions.utils import logger
from src.smartem_decisions.utils import (
    load_conf,
    setup_postgres_connection,
    rmq_publisher,
)
from src.smartem_decisions.rabbitmq import MessageQueueEventType
from src.smartem_decisions.model.mq_event import (
    AcquisitionCreatedEvent, AcquisitionUpdatedEvent, AcquisitionDeletedEvent,
    AtlasCreatedEvent, AtlasUpdatedEvent, AtlasDeletedEvent,
)
from src.smartem_decisions.model.database import (
    Acquisition,
    Atlas,
)


load_dotenv()
conf = load_conf()
db_engine = setup_postgres_connection()


def handle_acquisition_created(event_data: Dict[str, Any], session: SqlAlchemySession) -> None:
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
            metadata=event.metadata
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


def handle_acquisition_updated(event_data: Dict[str, Any], session: SqlAlchemySession) -> None:
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
            acquisition.epu_id = event.epu_id
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


def handle_acquisition_deleted(event_data: Dict[str, Any], session: SqlAlchemySession) -> None:
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


def handle_atlas_created(event_data: Dict[str, Any], session: SqlAlchemySession) -> None:
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
            id=event.id,
            name=event.name,
            grid_id=event.grid_id,
            pixel_size=event.pixel_size,
            metadata=event.metadata
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


def handle_atlas_updated(event_data: Dict[str, Any], session: SqlAlchemySession) -> None:
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


def handle_atlas_deleted(event_data: Dict[str, Any], session: SqlAlchemySession) -> None:
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
        logger.info(f"Deleted atlas with ID {event.id}")

    except ValidationError as e:
        logger.error(f"Validation error processing atlas deleted event: {e}")
    except Exception as e:
        session.rollback()
        logger.error(f"Error processing atlas deleted event: {e}")
        raise


# Create a mapping from event types to their handler functions
def get_event_handlers() -> Dict[str, Callable]:
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
        channel = rmq_publisher.channel()

        queue_name = conf["rabbitmq"]["queue_name"]
        channel.queue_declare(queue=queue_name, durable=True)

        channel.basic_qos(prefetch_count=1)
        channel.basic_consume(queue=queue_name, on_message_callback=on_message)

        logger.info(f"Consumer started, listening on queue '{queue_name}'")
        channel.start_consuming()

    except KeyboardInterrupt:
        logger.info("Consumer stopped by user")
    except Exception as e:
        logger.error(f"Error in consumer: {e}")


if __name__ == "__main__":
    main()
