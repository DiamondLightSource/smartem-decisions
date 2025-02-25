import json
import logging
import sys
from datetime import datetime


class JSONFormatter(logging.Formatter):
    def format(self, record):
        if isinstance(record.msg, dict):
            log_entry = record.msg
        else:
            log_entry = {
                "message": record.msg,
                "level": record.levelname,
                "timestamp": datetime.now().isoformat()
            }
        return json.dumps(log_entry, indent=2)


def setup_logging(log_file: str | None, verbose: bool):
    json_formatter = JSONFormatter()
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO if not verbose else logging.DEBUG)

    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(json_formatter)
        root_logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(json_formatter)
    root_logger.addHandler(console_handler)


if __name__ == "__main__":
    print("This module is not meant to be run directly. Import and use its components instead.")
    sys.exit(1)
