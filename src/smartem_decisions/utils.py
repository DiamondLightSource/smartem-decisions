import logging
import os
import pika
import time
import yaml
from sqlmodel import create_engine
from dotenv import load_dotenv

from _version import __version__
from src.smartem_decisions.log_manager import (
    LogConfig,
    LogManager,
)


def setup_logger():
    load_dotenv()
    required_env_vars = ["GRAYLOG_HOST", "GRAYLOG_UDP_PORT"]

    env_vars = {}
    for key in required_env_vars:
        value = os.getenv(key)
        if value is None:
            print(f"Error: Required environment variable '{key}' is not set")
            exit(1)
        env_vars[key] = value

    log_manager = LogManager.get_instance("smartem_decisions")
    return log_manager.configure(LogConfig(
        level=logging.DEBUG,
        console=True,
        file_path="smartem_decisions-core.log", # TODO define in app config
        graylog_host=env_vars['GRAYLOG_HOST'],
        graylog_port=int(env_vars['GRAYLOG_UDP_PORT']),
        graylog_protocol="udp",
        graylog_facility="smartem_decisions-core", # TODO define in app config
        graylog_extra_fields={"environment": "development", "version": __version__}
    ))

logger = setup_logger()


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
        echo=True, # TODO test if possible to feed this output through our logger
    )
    return engine


def setup_rabbitmq_connection(max_retries=3, retry_delay=2):
    """
    Create and return a connection to RabbitMQ with retry logic.

    Args:
        max_retries: Maximum number of connection attempts
        retry_delay: Delay between retries in seconds

    Returns:
        A pika.BlockingConnection object

    Raises:
        pika.exceptions.AMQPConnectionError: If connection cannot be established after retries
    """

    load_dotenv()

    required_env_vars = ["RABBITMQ_HOST", "RABBITMQ_PORT", "RABBITMQ_USER", "RABBITMQ_PASSWORD"]
    env_vars = {}
    for key in required_env_vars:
        value = os.getenv(key)
        if value is None:
            logger.error(f"Error: Required environment variable '{key}' is not set")
            exit(1)
        env_vars[key] = value

    connection_params = pika.ConnectionParameters(
        host=env_vars["RABBITMQ_HOST"],
        port=int(env_vars["RABBITMQ_PORT"]),
        credentials=pika.PlainCredentials(
            env_vars["RABBITMQ_USER"],
            env_vars["RABBITMQ_PASSWORD"],
        ),
    )

    for attempt in range(max_retries):
        try:
            logger.info(f"Attempting to connect to RabbitMQ (attempt {attempt + 1}/{max_retries})...")
            connection = pika.BlockingConnection(connection_params)
            logger.info("Successfully connected to RabbitMQ")
            return connection
        except pika.exceptions.AMQPConnectionError as e:
            if attempt < max_retries - 1:
                logger.warning(f"Connection failed: {e}. Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
            else:
                logger.error(f"Failed to connect to RabbitMQ after {max_retries} attempts")
                raise
        except Exception as e:
            logger.error(f"Unexpected error while connecting to RabbitMQ: {e}")
            raise

