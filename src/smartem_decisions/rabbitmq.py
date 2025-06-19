import json
import os
from collections.abc import Callable
from datetime import datetime
from typing import Any

import pika
from dotenv import load_dotenv
from pydantic import BaseModel

from smartem_decisions.log_manager import logger
from smartem_decisions.model.mq_event import MessageQueueEventType


class RabbitMQConnection:
    """
    Base class for RabbitMQ connection management
    """

    def __init__(
        self, connection_params: dict[str, Any] | None = None, exchange: str = "", queue: str = "smartem_decisions"
    ):
        """
        Initialize RabbitMQ connection

        Args:
            connection_params: Dictionary with RabbitMQ connection parameters. If None, load from environment variables
            exchange: Exchange name to use (default is direct exchange "")
            queue: Queue name to use
        """
        self.connection_params = connection_params or self._load_connection_params_from_env()
        self.exchange = exchange
        self.queue = queue
        self._connection = None
        self._channel = None

    @staticmethod
    def _load_connection_params_from_env() -> dict[str, Any]:
        """
        Load RabbitMQ connection parameters from environment variables

        Returns:
            dict: Connection parameters
        """
        load_dotenv(override=False)  # Don't override existing env vars as these might be coming from k8s

        required_env_vars = ["RABBITMQ_HOST", "RABBITMQ_PORT", "RABBITMQ_USER", "RABBITMQ_PASSWORD"]
        for key in required_env_vars:
            if os.getenv(key) is None:
                logger.error(f"Error: Required environment variable '{key}' is not set")
                exit(1)

        return {
            "host": os.getenv("RABBITMQ_HOST", "localhost"),
            "port": int(os.getenv("RABBITMQ_PORT", "5672")),
            "virtual_host": os.getenv("RABBITMQ_VHOST", "/"),
            "credentials": {
                "username": os.getenv("RABBITMQ_USER", "guest"),
                "password": os.getenv("RABBITMQ_PASSWORD", "guest"),
            },
        }

    def connect(self) -> None:
        """Establish connection to RabbitMQ server"""
        if self._connection is None or self._connection.is_closed:
            try:
                # Extract credentials from connection_params to create proper credential object
                if "credentials" in self.connection_params and isinstance(self.connection_params["credentials"], dict):
                    credentials_dict = self.connection_params.pop("credentials")
                    credentials = pika.PlainCredentials(
                        username=credentials_dict["username"], password=credentials_dict["password"]
                    )
                    # Create new connection params dict with proper credentials object
                    connection_params = {**self.connection_params, "credentials": credentials}
                else:
                    connection_params = self.connection_params

                self._connection = pika.BlockingConnection(pika.ConnectionParameters(**connection_params))
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

    def channel(self):
        """
        Get the channel object

        Returns:
            The current channel object
        """
        if self._channel is None:
            self.connect()
        return self._channel

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


class RabbitMQPublisher(RabbitMQConnection):
    """
    Publisher class for sending messages to RabbitMQ
    """

    def publish_event(self, event_type: MessageQueueEventType, payload: BaseModel | dict[str, Any]) -> bool:
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
            message = {"event_type": event_type.value, **payload_dict}

            # Use a custom encoder for json.dumps that handles datetime objects
            class DateTimeEncoder(json.JSONEncoder):
                def default(self, obj):
                    if isinstance(obj, datetime):
                        return obj.isoformat()
                    return super().default(obj)

            # Convert message to JSON using the custom encoder
            message_json = json.dumps(message, cls=DateTimeEncoder)

            # Publish message with delivery_mode=2 (persistent)
            self._channel.basic_publish(
                exchange=self.exchange,
                routing_key=self.queue,
                body=message_json,
                properties=pika.BasicProperties(
                    delivery_mode=2,  # Make message persistent
                    content_type="application/json",
                ),
            )

            logger.info(f"Published {event_type.value} event to RabbitMQ")
            return True

        except Exception as e:
            logger.error(f"Failed to publish {event_type.value} event: {str(e)}")
            return False


class RabbitMQConsumer(RabbitMQConnection):
    """
    Consumer class for receiving messages from RabbitMQ
    """

    def consume(self, callback: Callable, prefetch_count: int = 1) -> None:
        """
        Start consuming messages from the queue

        Args:
            callback: Callback function to process messages
            prefetch_count: Maximum number of unacknowledged messages (default: 1)
        """
        try:
            self.connect()
            self._channel.basic_qos(prefetch_count=prefetch_count)
            self._channel.basic_consume(queue=self.queue, on_message_callback=callback)

            logger.info(f"Consumer started, listening on queue '{self.queue}'")
            self._channel.start_consuming()

        except KeyboardInterrupt:
            logger.info("Consumer stopped by user")
            self.stop_consuming()
        except Exception as e:
            logger.error(f"Error in consumer: {e}")
            raise

    def stop_consuming(self) -> None:
        """Stop consuming messages"""
        if self._channel and self._channel.is_open:
            self._channel.stop_consuming()
            logger.info("Stopped consuming messages")
