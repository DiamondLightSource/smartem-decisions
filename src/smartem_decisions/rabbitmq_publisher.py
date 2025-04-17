import json

from enum import Enum
from typing import Any

import pika
from pydantic import BaseModel

from src.smartem_decisions.log_manager import logger

class EventType(str, Enum):
    ACQUISITION_CREATED = "acquisition.created"
    ACQUISITION_UPDATED = "acquisition.updated"
    ACQUISITION_DELETED = "acquisition.deleted"

    ATLAS_CREATED = "atlas.created"
    ATLAS_UPDATED = "atlas.updated"
    ATLAS_DELETED = "atlas.deleted"

    ATLAS_TILE_CREATED = "atlas_tile.created"
    ATLAS_TILE_UPDATED = "atlas_tile.updated"
    ATLAS_TILE_DELETED = "atlas_tile.deleted"

    GRID_CREATED = "grid.created"
    GRID_UPDATED = "grid.updated"
    GRID_DELETED = "grid.deleted"

    GRID_SQUARE_CREATED = "grid_square.created"
    GRID_SQUARE_UPDATED = "grid_square.updated"
    GRID_SQUARE_DELETED = "grid_square.deleted"

    FOIL_HOLE_CREATED = "foil_hole.created"
    FOIL_HOLE_UPDATED = "foil_hole.updated"
    FOIL_HOLE_DELETED = "foil_hole.deleted"

    MICROGRAPH_CREATED = "micrograph.created"
    MICROGRAPH_UPDATED = "micrograph.updated"
    MICROGRAPH_DELETED = "micrograph.deleted"


class MessagePayload(BaseModel):
    """Base class for message payloads"""
    pass


class RabbitMQPublisher:
    """
    Publisher class for sending messages to RabbitMQ
    """

    def __init__(self, connection_params: dict[str, Any], exchange: str = "", queue: str = "smartem_decisions"):
        """
        Initialize RabbitMQ publisher

        Args:
            connection_params: Dictionary with RabbitMQ connection parameters
            exchange: Exchange name to use (default is direct exchange "")
            queue: Queue name to publish to
        """
        self.connection_params = connection_params
        self.exchange = exchange
        self.queue = queue
        self._connection = None
        self._channel = None

    def connect(self) -> None:
        """Establish connection to RabbitMQ server"""
        if self._connection is None or self._connection.is_closed:
            try:
                self._connection = pika.BlockingConnection(
                    pika.ConnectionParameters(**self.connection_params)
                )
                self._channel = self._connection.channel()

                # Declare queue with durable=True to ensure it survives broker restarts
                self._channel.queue_declare(queue=self.queue, durable=True)

                logger.info(f"Connected to RabbitMQ and declared queue '{self.queue}'")
            except Exception as e:
                logger.error(f"Failed to connect to RabbitMQ: {str(e)}")
                raise

    def close(self) -> None:
        """Close the connection to RabbitMQ"""
        if self._connection and self._connection.is_open:
            self._connection.close()
            self._connection = None
            self._channel = None
            logger.info("Closed connection to RabbitMQ")

    def publish_event(self, event_type: EventType, payload: BaseModel | dict[str, Any]) -> bool:
        """
        Publish an event to RabbitMQ

        Args:
            event_type: Type of event from EventType enum
            payload: Event payload, either as Pydantic model or dictionary

        Returns:
            bool: True if message was published successfully
        """
        try:
            self.connect()

            # Convert Pydantic model to dict if needed
            if isinstance(payload, BaseModel):
                payload_dict = payload.model_dump()
            else:
                payload_dict = payload

            # Create message with event_type and payload
            message = {
                "event_type": event_type.value,
                **payload_dict
            }

            # Convert message to JSON
            message_json = json.dumps(message)

            # Publish message with delivery_mode=2 (persistent)
            self._channel.basic_publish(
                exchange=self.exchange,
                routing_key=self.queue,
                body=message_json,
                properties=pika.BasicProperties(
                    delivery_mode=2,  # Make message persistent
                    content_type='application/json'
                )
            )

            logger.info(f"Published {event_type.value} event to RabbitMQ")
            return True

        except Exception as e:
            logger.error(f"Failed to publish {event_type.value} event: {str(e)}")
            return False

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
