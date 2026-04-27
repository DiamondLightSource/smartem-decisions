import logging
import os

import yaml
from dotenv import load_dotenv
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlmodel import create_engine

from smartem_backend.log_manager import LogConfig, LogManager


def load_conf() -> dict | None:
    config_path = os.getenv("SMARTEM_BACKEND_CONFIG") or os.path.join(os.path.dirname(__file__), "appconfig.yml")
    try:
        with open(config_path) as f:
            conf = yaml.safe_load(f)
        return conf
    except FileNotFoundError:
        # Use basic logging since logger might not be configured yet
        print(f"Warning: Configuration file not found at {config_path}")
    except yaml.YAMLError as e:
        print(f"Warning: Error parsing YAML file: {e}")
    except Exception as e:
        print(f"Warning: An unexpected error occurred: {e}")
    return None


def get_log_file_path(conf: dict | None = None) -> str | None:
    """
    Get the log file path with validation and fallback handling.

    Args:
        conf: Configuration dictionary (if None, will load from config file)

    Returns:
        str | None: Valid log file path or None for test environments
    """
    # Don't create file handlers in test environment to avoid resource warnings
    if "pytest" in os.environ.get("_", "") or "PYTEST_CURRENT_TEST" in os.environ:
        return None

    if conf is None:
        conf = load_conf()

    # Get log file path from config or use default
    log_file = conf.get("app", {}).get("log_file", "smartem_backend-core.log") if conf else "smartem_backend-core.log"

    # Validate and ensure directory exists
    if log_file:
        log_dir = os.path.dirname(os.path.abspath(log_file))
        try:
            # Create directory if it doesn't exist
            if log_dir and not os.path.exists(log_dir):
                os.makedirs(log_dir, exist_ok=True)

            # Test if we can write to the directory
            test_file = os.path.join(log_dir or ".", ".write_test")
            with open(test_file, "w") as f:
                f.write("test")
            os.remove(test_file)

            return log_file
        except (OSError, PermissionError) as e:
            print(f"Warning: Cannot write to log directory {log_dir}: {e}")
            print("Falling back to current directory")
            return "smartem_backend-core.log"

    return "smartem_backend-core.log"


def setup_logger(level: int = logging.INFO, conf: dict | None = None):
    """
    Set up logger with consolidated configuration logic.

    Args:
        level: Logging level (default: INFO)
        conf: Configuration dictionary (if None, will load from config file)

    Returns:
        Configured logger instance
    """
    file_path = get_log_file_path(conf)

    return LogManager.get_instance("smartem_backend").configure(
        LogConfig(
            level=level,
            console=True,
            file_path=file_path,
        )
    )


logger = setup_logger()

# Global singleton engine instances. The sync engine is still required for
# CLI tools, Alembic migrations, and the agent data cleanup service. The async
# engine drives the FastAPI application and the RabbitMQ consumer.
_db_engine: Engine | None = None
_async_db_engine: AsyncEngine | None = None


def _load_postgres_env() -> dict[str, str]:
    load_dotenv(override=False)  # Don't override existing env vars as these might be coming from k8s
    required_env_vars = ["POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_HOST", "POSTGRES_PORT", "POSTGRES_DB"]
    env_vars = {}
    for key in required_env_vars:
        value = os.getenv(key)
        if value is None:
            logger.error(f"Error: Required environment variable '{key}' is not set")
            exit(1)
        env_vars[key] = value
    return env_vars


def _load_pool_config() -> dict[str, int | bool]:
    config = load_conf()
    db_config = config.get("database", {}) if config else {}
    return {
        "pool_size": db_config.get("pool_size", 10),
        "max_overflow": db_config.get("max_overflow", 20),
        "pool_timeout": db_config.get("pool_timeout", 30),
        "pool_recycle": db_config.get("pool_recycle", 3600),
        "pool_pre_ping": db_config.get("pool_pre_ping", True),
    }


def _sync_postgres_url() -> str:
    env = _load_postgres_env()
    return (
        f"postgresql+psycopg2://{env['POSTGRES_USER']}:{env['POSTGRES_PASSWORD']}"
        f"@{env['POSTGRES_HOST']}:{env['POSTGRES_PORT']}/{env['POSTGRES_DB']}"
    )


def _async_postgres_url() -> str:
    env = _load_postgres_env()
    return (
        f"postgresql+asyncpg://{env['POSTGRES_USER']}:{env['POSTGRES_PASSWORD']}"
        f"@{env['POSTGRES_HOST']}:{env['POSTGRES_PORT']}/{env['POSTGRES_DB']}"
    )


def get_asyncpg_dsn() -> str:
    """Return a DSN suitable for `asyncpg.connect()` (no SQLAlchemy driver suffix).

    Used for dedicated asyncpg connections that need bare-driver behaviour, e.g.
    LISTEN/NOTIFY listeners that live outside the SQLAlchemy session pool.
    """
    env = _load_postgres_env()
    return (
        f"postgresql://{env['POSTGRES_USER']}:{env['POSTGRES_PASSWORD']}"
        f"@{env['POSTGRES_HOST']}:{env['POSTGRES_PORT']}/{env['POSTGRES_DB']}"
    )


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
    pool = _load_pool_config()
    _db_engine = create_engine(
        _sync_postgres_url(),
        echo=echo,
        pool_size=pool["pool_size"],
        max_overflow=pool["max_overflow"],
        pool_timeout=pool["pool_timeout"],
        pool_recycle=pool["pool_recycle"],
        pool_pre_ping=pool["pool_pre_ping"],
    )
    logger.info(f"Created sync database engine with pool_size={pool['pool_size']}, max_overflow={pool['max_overflow']}")
    return _db_engine


def setup_postgres_async_connection(echo=False, force_new=False) -> AsyncEngine:
    """Get or create the singleton asyncpg-backed AsyncEngine used by the API server and consumer.

    The sync engine in setup_postgres_connection coexists for CLI tools and Alembic migrations.
    """
    global _async_db_engine
    if _async_db_engine is not None and not force_new:
        return _async_db_engine
    pool = _load_pool_config()
    _async_db_engine = create_async_engine(
        _async_postgres_url(),
        echo=echo,
        pool_size=pool["pool_size"],
        max_overflow=pool["max_overflow"],
        pool_timeout=pool["pool_timeout"],
        pool_recycle=pool["pool_recycle"],
        pool_pre_ping=pool["pool_pre_ping"],
    )
    logger.info(
        f"Created async database engine with pool_size={pool['pool_size']}, max_overflow={pool['max_overflow']}"
    )
    return _async_db_engine


def get_db_engine() -> Engine:
    """Get the singleton sync database engine. Creates it if it doesn't exist."""
    return setup_postgres_connection()


def get_async_db_engine() -> AsyncEngine:
    """Get the singleton async database engine. Creates it if it doesn't exist."""
    return setup_postgres_async_connection()


# Load application configuration once for consumers that need config-driven behaviour
# (e.g., api_server.py reads app_config["app"]["gridsquare_create_batch_max"]).
app_config = load_conf()
