import os

import yaml
from dotenv import load_dotenv
from sqlalchemy.engine import Engine
from sqlmodel import create_engine

from smartem_decisions.log_manager import logger
from smartem_decisions.rabbitmq import RabbitMQConsumer, RabbitMQPublisher


def load_conf():
    config_path = os.path.join(os.path.dirname(__file__), "appconfig.yml")
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
