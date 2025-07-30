import logging
from base64 import urlsafe_b64encode
from uuid import uuid4


def generate_uuid():
    """Generate a URL-safe UUID string"""
    return urlsafe_b64encode(uuid4().bytes).decode("ascii").rstrip("=")


def get_logger(name: str = "smartem") -> logging.Logger:
    """Get a configured logger instance for shared use across components"""
    logger = logging.getLogger(name)
    if not logger.handlers:
        # Only configure if not already configured
        handler = logging.StreamHandler()
        formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger
