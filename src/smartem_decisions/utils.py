import os

import yaml
from dotenv import load_dotenv
from sqlmodel import create_engine

from src.smartem_decisions.log_manager import logger
from src.smartem_decisions.rabbitmq import RabbitMQConsumer, RabbitMQPublisher


def load_conf():
    config_path = os.path.join(os.path.dirname(__file__), "config.yaml")
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


def setup_postgres_connection():
    load_dotenv()
    required_env_vars = ["POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_PORT", "POSTGRES_DB"]

    env_vars = {}
    for key in required_env_vars:
        value = os.getenv(key)
        if value is None:
            logger.error(f"Error: Required environment variable '{key}' is not set")
            exit(1)
        env_vars[key] = value

    engine = create_engine(
        f"postgresql+psycopg2://{env_vars['POSTGRES_USER']}:{env_vars['POSTGRES_PASSWORD']}@"
        f"localhost:{env_vars['POSTGRES_PORT']}/{env_vars['POSTGRES_DB']}",
        echo=True,  # TODO test if possible to feed this output through our logger
    )
    return engine


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
