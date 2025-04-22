import os
import yaml
from sqlmodel import create_engine
from dotenv import load_dotenv

from src.smartem_decisions.log_manager import logger
from src.smartem_decisions.rabbitmq import RabbitMQPublisher


def load_conf():
    config_path = os.path.join(os.path.dirname(__file__), "config.yaml")
    try:
        with open(config_path, "r") as f:
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


def create_rabbitmq_publisher(
    connection_params: dict | None = None, exchange: str = "", queue: str = "smartem_decisions"
) -> RabbitMQPublisher:
    """
    Create a new RabbitMQ publisher instance

    Args:
        connection_params: Connection parameters for RabbitMQ. If None, load from environment variables
        exchange: Exchange name (default is direct exchange "")
        queue: Queue name (default is "smartem_decisions")

    Returns:
        RabbitMQPublisher: A new publisher instance
    """
    if connection_params is None:
        load_dotenv()

        required_env_vars = ["RABBITMQ_HOST", "RABBITMQ_PORT", "RABBITMQ_USER", "RABBITMQ_PASSWORD"]
        for key in required_env_vars:
            if os.getenv(key) is None:
                logger.error(f"Error: Required environment variable '{key}' is not set")
                exit(1)

        connection_params = {
            "host": os.getenv("RABBITMQ_HOST", "localhost"),
            "port": int(os.getenv("RABBITMQ_PORT", "5672")),
            "virtual_host": os.getenv("RABBITMQ_VHOST", "/"),
            "credentials": {
                "username": os.getenv("RABBITMQ_USER", "guest"),
                "password": os.getenv("RABBITMQ_PASSWORD", "guest"),
            },
        }

        # Use queue from environment if provided
        queue_from_env = os.getenv("RABBITMQ_QUEUE")
        if queue_from_env:
            queue = queue_from_env

    publisher = RabbitMQPublisher(connection_params, exchange, queue)
    return publisher


# Singleton instance that can be imported and used throughout the application
rmq_publisher = create_rabbitmq_publisher()
