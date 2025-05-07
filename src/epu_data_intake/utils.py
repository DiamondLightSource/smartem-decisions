from collections.abc import Callable
import functools
from uuid import uuid4
from base64 import urlsafe_b64encode

def generate_uuid():
    """Generate a URL-safe UUID string"""
    return urlsafe_b64encode(uuid4().bytes).decode("ascii").rstrip("=")
