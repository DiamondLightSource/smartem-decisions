"""Keycloak token management for service-to-service OAuth2 authentication.

Implements the OAuth 2.0 client_credentials grant (RFC 6749 Section 4.4). The
agent POSTs its confidential client_id and client_secret to Keycloak's token
endpoint, receives an access token, caches it in memory, proactively refreshes
shortly before expiry, and re-fetches on demand when a request returns 401.

The client_credentials grant does not issue refresh tokens; each refresh is a
full re-POST of the credentials.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import requests


@dataclass(frozen=True)
class KeycloakConfig:
    """Four values required to obtain a Keycloak access token."""

    url: str
    realm: str
    client_id: str
    client_secret: str


def load_keycloak_config(path: Path) -> KeycloakConfig:
    """Parse a dotenv-style file containing the four required KEYCLOAK_* values.

    The file format is one `KEY=VALUE` per line. Comments (lines starting with
    `#`) and blank lines are ignored. Whitespace around the key and value is
    stripped. Quoting is not interpreted.

    Raises:
        FileNotFoundError: if the path does not exist.
        ValueError: if any of the four required values is missing or empty.
    """
    if not path.exists():
        raise FileNotFoundError(
            f"Keycloak configuration file not found at {path}. "
            "Pass --config to specify an alternative location."
        )

    values: dict[str, str] = {}
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        key, sep, value = line.partition("=")
        if not sep:
            continue
        values[key.strip()] = value.strip()

    required = ["KEYCLOAK_URL", "KEYCLOAK_REALM", "KEYCLOAK_CLIENT_ID", "KEYCLOAK_CLIENT_SECRET"]
    missing = [k for k in required if not values.get(k)]
    if missing:
        raise ValueError(
            f"Keycloak configuration at {path} is missing or has empty values for: {', '.join(missing)}"
        )

    return KeycloakConfig(
        url=values["KEYCLOAK_URL"],
        realm=values["KEYCLOAK_REALM"],
        client_id=values["KEYCLOAK_CLIENT_ID"],
        client_secret=values["KEYCLOAK_CLIENT_SECRET"],
    )


class KeycloakClient:
    """Fetches and caches Keycloak access tokens via the client_credentials grant."""

    def __init__(
        self,
        config: KeycloakConfig,
        refresh_buffer_seconds: int = 30,
        timeout: float = 10.0,
        logger: logging.Logger | None = None,
    ):
        self._config = config
        self._token_url = (
            f"{config.url.rstrip('/')}/realms/{config.realm}/protocol/openid-connect/token"
        )
        self._refresh_buffer = refresh_buffer_seconds
        self._timeout = timeout
        self._session = requests.Session()
        self._token: str | None = None
        self._token_expires_at: float = 0.0
        self._logger = logger or logging.getLogger(__name__)

    @property
    def client_id(self) -> str:
        return self._config.client_id

    def get_token(self) -> str:
        """Return a valid access token, fetching or refreshing as needed."""
        now = time.time()
        if self._token and (now + self._refresh_buffer) < self._token_expires_at:
            return self._token
        return self._fetch_token()

    def invalidate(self) -> None:
        """Drop the cached token so the next `get_token` call fetches afresh.
        Use after a 401 from the backend to force a refresh-and-retry.
        """
        self._token = None
        self._token_expires_at = 0.0

    def close(self) -> None:
        try:
            self._session.close()
        except Exception as e:
            self._logger.warning("Error closing Keycloak session: %s", e)

    def _fetch_token(self) -> str:
        try:
            response = self._session.post(
                self._token_url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self._config.client_id,
                    "client_secret": self._config.client_secret,
                },
                timeout=self._timeout,
            )
            response.raise_for_status()
        except requests.RequestException as e:
            self._logger.error("Keycloak token fetch failed: %s", e)
            raise

        try:
            data = response.json()
            access_token = data["access_token"]
            expires_in = int(data.get("expires_in", 300))
        except (ValueError, KeyError) as e:
            self._logger.error("Keycloak token response malformed: %s", e)
            raise

        self._token = access_token
        self._token_expires_at = time.time() + expires_in

        expiry_iso = datetime.fromtimestamp(self._token_expires_at, tz=UTC).isoformat()
        now_iso = datetime.now(tz=UTC).isoformat()
        self._logger.info(
            "Keycloak token fetched (client_id=%s, expires_at=%s, system_time_now=%s)",
            self._config.client_id,
            expiry_iso,
            now_iso,
        )
        return access_token

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
