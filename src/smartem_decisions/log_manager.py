import json
import logging
import logging.handlers
import os
import sys
from dataclasses import dataclass, field

import graypy
from dotenv import load_dotenv

from src.smartem_decisions._version import __version__


# TODO: use or loose
def _monkeypatch_graypy() -> None:
    """
    Monkeypatch a helper class into graypy to support log levels in Graylog.
    This translates Python integer level numbers to syslog levels.
    """

    class PythonLevelToSyslogConverter:
        @staticmethod
        def get(level, _):
            match level:
                case level if level < 20:
                    return 7  # DEBUG
                case level if level < 25:
                    return 6  # INFO
                case level if level < 30:
                    return 5  # NOTICE
                case level if level < 40:
                    return 4  # WARNING
                case level if level < 50:
                    return 3  # ERROR
                case level if level < 60:
                    return 2  # CRITICAL
                case _:
                    return 1  # ALERT

    graypy.handler.SYSLOG_LEVELS = PythonLevelToSyslogConverter()


# Custom GELF HTTP handler to fix graypy's issue with ssl parameter
class FixedGELFHTTPHandler(graypy.handler.BaseGELFHandler):
    """
    A replacement for GELFHTTPHandler that properly handles the ssl parameter.

    This implementation fixes the issue with the ssl parameter in graypy's original
    GELFHTTPHandler by directly inheriting from BaseGELFHandler and implementing
    the correct HTTP functionality.
    """

    def __init__(self, host, port=12202, compress=False, path="/", ssl=False, timeout=5.0, **kwargs):
        # Initialize the base handler
        super().__init__(compress=compress, **kwargs)

        # Set HTTP-specific attributes
        self.host = host
        self.port = port
        self.path = path
        self.ssl = ssl
        self.proto = "https" if ssl else "http"
        self.url = f"{self.proto}://{self.host}:{self.port}{self.path}"
        self.timeout = timeout

        # Define HTTP headers
        self.headers = {"Content-Type": "application/json"}

    def emit(self, record):
        """
        Emit a record by sending it as a GELF message via HTTP/HTTPS.
        """
        try:
            # Get the message dict using the correct method name from BaseGELFHandler
            message_dict = self._make_gelf_dict(record)

            # Convert to JSON
            message = json.dumps(message_dict).encode("utf-8")

            # Send via HTTP or HTTPS
            if self.ssl:
                import http.client

                connection = http.client.HTTPSConnection(self.host, self.port, timeout=self.timeout)
            else:
                import http.client

                connection = http.client.HTTPConnection(self.host, self.port, timeout=self.timeout)

            # Send the request
            connection.request("POST", self.path, message, self.headers)

            # Get response and close connection
            response = connection.getresponse()
            connection.close()

            if response.status != 202:
                raise ValueError(f"HTTP error: {response.status} {response.reason}")

        except Exception:
            self.handleError(record)


@dataclass
class LogConfig:
    level: int = logging.INFO
    console: bool = True
    file_path: str | None = None
    file_max_size: int = 10_485_760  # 10MB
    file_backup_count: int = 5
    # Graylog configuration
    graylog_host: str | None = None
    graylog_port: int | None = None
    graylog_protocol: str = "udp"  # "udp", "tcp", "http", "amqp", or "redis"
    graylog_facility: str | None = None  # Optional facility name
    graylog_source: str | None = None  # Optional source identifier
    graylog_extra_fields: dict = field(default_factory=dict)  # Additional GELF fields
    graylog_debugging: bool = False  # Enable debug output from graypy
    graylog_tls: bool = False  # Enable TLS/SSL for TCP and HTTP
    # Formatting
    format_string: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    handlers: list = field(default_factory=list, init=False)


class LogManager:
    _instances = {}  # Class variable to store singleton instances by name

    @classmethod
    def get_instance(cls, name: str = "app") -> "LogManager":
        if name not in cls._instances:
            cls._instances[name] = cls(name)
        return cls._instances[name]

    def __init__(self, name: str = "app"):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)
        self.handlers = []
        self.name = name

    def configure(self, config: LogConfig) -> logging.Logger:
        # Remove existing handlers
        for handler in self.handlers:
            self.logger.removeHandler(handler)
        self.handlers.clear()

        formatter = logging.Formatter(config.format_string)

        # Console handler
        if config.console:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(config.level)
            console_handler.setFormatter(formatter)
            self.logger.addHandler(console_handler)
            self.handlers.append(console_handler)

        # File handler with rotation
        if config.file_path:
            file_handler = logging.handlers.RotatingFileHandler(
                config.file_path, maxBytes=config.file_max_size, backupCount=config.file_backup_count
            )
            file_handler.setLevel(config.level)
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)
            self.handlers.append(file_handler)

        # Graylog handler using graypy
        if config.graylog_host and config.graylog_port:
            # _monkeypatch_graypy() TODO: use or loose

            # Set up common parameters
            facility = config.graylog_facility or self.name

            # Define base parameters for all handlers
            base_kwargs = {
                "facility": facility,
                "debugging_fields": config.graylog_debugging,
                "extra_fields": config.graylog_extra_fields.copy(),  # Make a copy to avoid modifying original
            }

            # Add source to extra_fields since it's not directly supported by BaseGELFHandler
            if config.graylog_source:
                base_kwargs["extra_fields"]["source"] = config.graylog_source

            # Configure protocol-specific handlers
            if config.graylog_protocol.lower() == "tcp":
                graylog_handler = graypy.GELFTCPHandler(
                    host=config.graylog_host, port=config.graylog_port, **base_kwargs
                )
            elif config.graylog_protocol.lower() == "http":
                graylog_handler = FixedGELFHTTPHandler(
                    host=config.graylog_host,
                    port=config.graylog_port,
                    ssl=config.graylog_tls,
                    compress=False,
                    path="/",
                    **base_kwargs,
                )
            elif config.graylog_protocol.lower() == "amqp":
                raise NotImplementedError(
                    "AMQP protocol requires additional configuration. Implement with graypy.AMQPHandler if needed."
                )
            elif config.graylog_protocol.lower() == "redis":
                raise NotImplementedError(
                    "Redis protocol requires additional configuration. "
                    "Implement with graypy.GELFRedisHandler if needed."
                )
            else:  # Default to UDP
                graylog_handler = graypy.GELFUDPHandler(
                    host=config.graylog_host, port=config.graylog_port, **base_kwargs
                )

            graylog_handler.setLevel(config.level)
            self.logger.addHandler(graylog_handler)
            self.handlers.append(graylog_handler)

        return self.logger


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

    return LogManager.get_instance("smartem_decisions").configure(
        LogConfig(
            level=logging.INFO,
            console=True,
            file_path="smartem_decisions-core.log",  # TODO define in app config
            graylog_host=env_vars["GRAYLOG_HOST"],
            graylog_port=int(env_vars["GRAYLOG_UDP_PORT"]),
            graylog_protocol="udp",
            graylog_facility="smartem_decisions-core",  # TODO define in app config
            graylog_extra_fields={"environment": "development", "version": __version__},
        )
    )


logger = setup_logger()

# Usage example
if __name__ == "__main__":
    # Initialize log manager
    log_manager = LogManager.get_instance("smartem_decisions")

    # Console only
    logger = log_manager.configure(LogConfig(level=logging.INFO, console=True))
    logger.info("Console logging")

    # Console + File
    logger = log_manager.configure(LogConfig(level=logging.DEBUG, console=True, file_path="app.log"))
    logger.debug("Console and file logging")

    # All handlers including Graylog with UDP
    logger = log_manager.configure(
        LogConfig(
            level=logging.WARNING,
            console=True,
            file_path="app.log",
            graylog_host="localhost",
            graylog_port=12201,
            graylog_protocol="udp",
            graylog_facility="my_application",
            graylog_extra_fields={"environment": "development", "version": "1.0.0"},
        )
    )
    logger.warning("Logging everywhere")

    # Example with TCP
    logger = log_manager.configure(
        LogConfig(
            level=logging.ERROR, console=True, graylog_host="localhost", graylog_port=12202, graylog_protocol="tcp"
        )
    )
    logger.error("TCP logging to Graylog")

    # Example with HTTP and TLS
    logger = log_manager.configure(
        LogConfig(
            level=logging.ERROR,
            console=True,
            graylog_host="localhost",
            graylog_port=12202,
            graylog_protocol="http",
            graylog_tls=True,
        )
    )
    logger.error("Secure HTTP logging to Graylog")
