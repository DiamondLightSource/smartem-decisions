import logging
import os

import yaml
from dotenv import load_dotenv
from sqlalchemy.engine import Engine
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


# Load application configuration once for consumers that need config-driven behaviour
# (e.g., api_server.py reads app_config["app"]["gridsquare_create_batch_max"]).
app_config = load_conf()
