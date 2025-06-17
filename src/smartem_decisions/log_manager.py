import logging
import logging.handlers
import sys
from dataclasses import dataclass, field


@dataclass
class LogConfig:
    level: int = logging.INFO
    console: bool = True
    file_path: str | None = None
    file_max_size: int = 10_485_760  # 10MB
    file_backup_count: int = 5
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

        return self.logger


def setup_logger():
    return LogManager.get_instance("smartem_decisions").configure(
        LogConfig(
            level=logging.INFO,
            console=True,
            file_path="smartem_decisions-core.log",  # TODO define in app config
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
