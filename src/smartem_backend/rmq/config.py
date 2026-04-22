import logging
import os

from dotenv import load_dotenv

logger = logging.getLogger(__name__)


def load_rmq_connection_url() -> str:
    """Build an AMQP connection URL from environment variables.

    aio-pika's connect_robust accepts a URL string. Using a URL keeps the
    credential encoding (urlencoded password) and TLS settings in one place
    rather than scattered across a dict. Loaded via python-dotenv so local
    development picks up .env without breaking kubernetes which injects env
    vars directly.
    """
    load_dotenv(override=False)

    required = ["RABBITMQ_HOST", "RABBITMQ_PORT", "RABBITMQ_USER", "RABBITMQ_PASSWORD"]
    missing = [key for key in required if os.getenv(key) is None]
    if missing:
        raise RuntimeError(f"Missing required RabbitMQ env vars: {missing}")

    from urllib.parse import quote

    host = os.environ["RABBITMQ_HOST"]
    port = int(os.environ["RABBITMQ_PORT"])
    user = quote(os.environ["RABBITMQ_USER"], safe="")
    password = quote(os.environ["RABBITMQ_PASSWORD"], safe="")
    vhost = quote(os.getenv("RABBITMQ_VHOST", "/"), safe="")

    return f"amqp://{user}:{password}@{host}:{port}/{vhost}"


def load_rmq_topology() -> tuple[str, str]:
    """Return (exchange, queue/routing_key) from appconfig plus env override."""
    from smartem_backend.utils import load_conf

    config = load_conf()
    if config and "rabbitmq" in config:
        queue_name = config["rabbitmq"]["queue_name"]
    else:
        queue_name = "smartem_backend"
    exchange = os.getenv("RABBITMQ_EXCHANGE") or ""
    return exchange, queue_name
