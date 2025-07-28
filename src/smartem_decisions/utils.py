import json
import logging
import os
from collections.abc import Callable
from datetime import datetime
from typing import Any

import pika
import yaml
from dotenv import load_dotenv
from pydantic import BaseModel
from sqlalchemy.engine import Engine
from sqlmodel import create_engine

from smartem_decisions.log_manager import LogConfig, LogManager
from smartem_decisions.model.mq_event import MessageQueueEventType


def load_conf() -> dict | None:
    config_path = os.getenv("SMARTEM_DECISIONS_CONFIG") or os.path.join(os.path.dirname(__file__), "appconfig.yaml")
    logger_file_path = (
        None
        if "pytest" in os.environ.get("_", "") or "PYTEST_CURRENT_TEST" in os.environ
        else "smartem_decisions-core.log"
    )
    logger = LogManager.get_instance("smartem_decisions").configure(
        LogConfig(
            level=logging.INFO,
            console=True,
            file_path=logger_file_path,
        )
    )
    try:
        with open(config_path) as f:
            conf = yaml.safe_load(f)
        return conf
    except FileNotFoundError:
        logger.error(f"Configuration file not found at {config_path}")
    except yaml.YAMLError as e:
        logger.error(f"Error parsing YAML file: {e}")
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
    return None


def setup_logger():
    # Don't create file handlers in test environment to avoid resource warnings
    import os

    conf = load_conf()
    file_path = (
        None
        if "pytest" in os.environ.get("_", "") or "PYTEST_CURRENT_TEST" in os.environ
        else conf["app"]["log_file"]
        if conf and conf.get("app", {}).get("log_file")
        else "smartem_decisions-core.log"
    )

    return LogManager.get_instance("smartem_decisions").configure(
        LogConfig(
            level=logging.INFO,
            console=True,
            file_path=file_path,
        )
    )


logger = setup_logger()

# Global singleton engine instance
_db_engine: Engine | None = None


def setup_postgres_connection(echo=False, force_new=False) -> Engine:
    """
    Get or create a singleton database engine with connection pooling.

    Args:
        echo: Enable SQL logging
        force_new: Force creation of new engine (for testing)

    Returns:
        SQLAlchemy Engine instance
    """
    global _db_engine

    # Return existing engine unless forced to create new one
    if _db_engine is not None and not force_new:
        return _db_engine
    load_dotenv(override=False)  # Don't override existing env vars as these might be coming from k8s
    required_env_vars = ["POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_HOST", "POSTGRES_PORT", "POSTGRES_DB"]

    env_vars = {}
    for key in required_env_vars:
        value = os.getenv(key)
        if value is None:
            logger.error(f"Error: Required environment variable '{key}' is not set")
            exit(1)
        env_vars[key] = value

    # Load database configuration from appconfig.yml with defaults
    config = load_conf()
    db_config = config.get("database", {}) if config else {}

    pool_size = db_config.get("pool_size", 10)
    max_overflow = db_config.get("max_overflow", 20)
    pool_timeout = db_config.get("pool_timeout", 30)
    pool_recycle = db_config.get("pool_recycle", 3600)
    pool_pre_ping = db_config.get("pool_pre_ping", True)

    # Create engine with connection pooling
    _db_engine = create_engine(
        f"postgresql+psycopg2://{env_vars['POSTGRES_USER']}:{env_vars['POSTGRES_PASSWORD']}@"
        f"{env_vars['POSTGRES_HOST']}:{env_vars['POSTGRES_PORT']}/{env_vars['POSTGRES_DB']}",
        echo=echo,
        # Connection pool settings from config
        pool_size=pool_size,  # Number of connections to maintain in pool
        max_overflow=max_overflow,  # Additional connections beyond pool_size
        pool_timeout=pool_timeout,  # Seconds to wait for connection from pool
        pool_recycle=pool_recycle,  # Seconds after which connection is recreated
        pool_pre_ping=pool_pre_ping,  # Validate connections before use
    )

    logger.info(f"Created database engine with pool_size={pool_size}, max_overflow={max_overflow}")
    return _db_engine


def get_db_engine() -> Engine:
    """
    Get the singleton database engine. Creates it if it doesn't exist.

    Returns:
        SQLAlchemy Engine instance
    """
    return setup_postgres_connection()


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
                    credentials_dict = self.connection_params["credentials"]
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


def setup_rabbitmq(queue_name=None, exchange=None):
    """
    Create RabbitMQ publisher and consumer instances using configuration settings

    Args:
        queue_name: Optional queue name override (if None, load from config)
        exchange: Optional exchange name override (if None, use default "")

    Returns:
        tuple: (RabbitMQPublisher instance, RabbitMQConsumer instance)
    """
    # Load config to get queue_name and routing_key
    config = load_conf()

    if not queue_name and config and "rabbitmq" in config:
        queue_name = config["rabbitmq"]["queue_name"]
        routing_key = config["rabbitmq"]["routing_key"]
    else:
        # Default to "smartem_decisions" if config not available
        queue_name = queue_name or "smartem_decisions"
        routing_key = queue_name  # Use queue_name as routing_key by default

    exchange = exchange or ""  # Default to direct exchange if not specified

    # Create publisher and consumer with the same connection settings
    publisher = RabbitMQPublisher(connection_params=None, exchange=exchange, queue=routing_key)
    consumer = RabbitMQConsumer(connection_params=None, exchange=exchange, queue=queue_name)

    return publisher, consumer


# Load application configuration. TODO do once and share the singleton conf with rest of codebase
app_config = load_conf()

# Create RabbitMQ connections (available as singletons throughout the application)
rmq_publisher, rmq_consumer = setup_rabbitmq(
    queue_name=app_config["rabbitmq"]["queue_name"] if app_config and "rabbitmq" in app_config else None,
    exchange="",  # Using default direct exchange
)
