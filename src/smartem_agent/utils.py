from base64 import urlsafe_b64encode
from uuid import uuid4


def generate_uuid():
    """Generate a URL-safe UUID string"""
    return urlsafe_b64encode(uuid4().bytes).decode("ascii").rstrip("=")
