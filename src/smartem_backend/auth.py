"""Keycloak JWT validation as a FastAPI dependency.

Validates `Authorization: Bearer <jwt>` against the configured Keycloak realm's
JWKS. Verification is offline - JWKS is fetched once and cached by PyJWKClient;
no per-request call to Keycloak.

Authentication is always enforced. Tokens are decoded with a small leeway to
absorb modest clock skew between hosts. If `KEYCLOAK_ALLOWED_AZP` is set, the
`azp` claim is checked against the allow-list; tokens whose `azp` is not on the
list are rejected. Exempt paths (`/status`, `/health`, etc.) bypass the check
entirely.
"""

import logging
import os

import jwt
from fastapi import HTTPException, Request, status
from jwt import PyJWKClient

logger = logging.getLogger("smartem_backend.auth")

EXEMPT_PATHS: frozenset[str] = frozenset({"/health", "/status", "/openapi.json", "/docs", "/redoc"})

# Clock skew tolerance applied to time-based JWT claims (exp, nbf, iat).
# Small enough to bound replay of expired tokens, large enough to absorb realistic NTP drift.
JWT_LEEWAY_SECONDS = 60

_jwks_client: PyJWKClient | None = None


def _verify_iss() -> bool:
    return os.getenv("KEYCLOAK_VERIFY_ISS", "true").lower() == "true"


def _keycloak_url() -> str:
    return os.getenv("KEYCLOAK_URL", "").rstrip("/")


def _realm() -> str:
    return os.getenv("KEYCLOAK_REALM", "dls")


def _issuer() -> str:
    return f"{_keycloak_url()}/realms/{_realm()}"


def _jwks_url() -> str:
    return f"{_issuer()}/protocol/openid-connect/certs"


def _allowed_azps() -> frozenset[str]:
    """Parse `KEYCLOAK_ALLOWED_AZP` (comma-separated) into a frozenset.

    Empty environment variable means "no azp check" - any valid token from the realm
    is accepted regardless of which client it was issued to.
    """
    raw = os.getenv("KEYCLOAK_ALLOWED_AZP", "")
    return frozenset(s.strip() for s in raw.split(",") if s.strip())


def _get_jwks_client() -> PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        if not _keycloak_url():
            raise RuntimeError("KEYCLOAK_URL must be set")
        _jwks_client = PyJWKClient(_jwks_url(), cache_keys=True, lifespan=600)
        logger.info("Initialised Keycloak JWKS client at %s", _jwks_url())
    return _jwks_client


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def _extract_bearer(request: Request) -> str:
    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("bearer "):
        raise _unauthorized("Missing or malformed Authorization header")
    token = auth.split(" ", 1)[1].strip()
    if not token:
        raise _unauthorized("Empty bearer token")
    return token


def _verify(token: str) -> dict:
    try:
        signing_key = _get_jwks_client().get_signing_key_from_jwt(token).key
    except jwt.PyJWKClientError as e:
        logger.warning("JWKS lookup failed: %s", e)
        raise _unauthorized("Cannot resolve signing key") from e
    except jwt.PyJWTError as e:
        logger.warning("Could not parse token header: %s", e)
        raise _unauthorized("Invalid token") from e

    options = {"verify_iss": _verify_iss(), "verify_aud": False}
    decode_kwargs: dict = {
        "algorithms": ["RS256"],
        "options": options,
        "leeway": JWT_LEEWAY_SECONDS,
    }
    if _verify_iss():
        decode_kwargs["issuer"] = _issuer()

    try:
        claims = jwt.decode(token, signing_key, **decode_kwargs)
    except jwt.ExpiredSignatureError as e:
        raise _unauthorized("Token expired") from e
    except jwt.PyJWTError as e:
        logger.warning("Token validation failed: %s", e)
        raise _unauthorized("Invalid token") from e

    allowed = _allowed_azps()
    if allowed:
        azp = claims.get("azp")
        if azp not in allowed:
            logger.warning("Token rejected: azp %r not in allow-list", azp)
            raise _unauthorized("Token azp not permitted")

    return claims


async def verify_token(request: Request) -> dict | None:
    """Route dependency. Returns claims when validation succeeded, or None for
    exempt paths. Raises 401 on validation failure.
    """
    if request.url.path in EXEMPT_PATHS:
        return None
    return _verify(_extract_bearer(request))
