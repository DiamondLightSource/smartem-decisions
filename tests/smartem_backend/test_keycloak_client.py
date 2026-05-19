"""Unit tests for the agent-side Keycloak client and configuration loader."""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest
import requests

from smartem_backend.keycloak_client import (
    KeycloakClient,
    KeycloakConfig,
    load_keycloak_config,
)


def _make_config() -> KeycloakConfig:
    return KeycloakConfig(
        url="http://keycloak.test",
        realm="dls",
        client_id="SmartEM_Agent",
        client_secret="secret-here",
    )


def _make_token_response(access_token: str = "tok-1", expires_in: int = 300) -> MagicMock:
    response = MagicMock()
    response.status_code = 200
    response.raise_for_status = MagicMock()
    response.json.return_value = {"access_token": access_token, "expires_in": expires_in}
    return response


class TestConfigLoading:
    def test_load_happy_path(self, tmp_path):
        config_file = tmp_path / "agent.env"
        config_file.write_text(
            "KEYCLOAK_URL=http://kc.local\n"
            "KEYCLOAK_REALM=dls\n"
            "KEYCLOAK_CLIENT_ID=SmartEM_Agent\n"
            "KEYCLOAK_CLIENT_SECRET=s3cret\n"
        )
        config = load_keycloak_config(config_file)
        assert config.url == "http://kc.local"
        assert config.realm == "dls"
        assert config.client_id == "SmartEM_Agent"
        assert config.client_secret == "s3cret"

    def test_load_ignores_comments_and_blanks(self, tmp_path):
        config_file = tmp_path / "agent.env"
        config_file.write_text(
            "# This is a comment\n"
            "\n"
            "KEYCLOAK_URL=http://kc.local\n"
            "   # indented comment\n"
            "KEYCLOAK_REALM=dls\n"
            "KEYCLOAK_CLIENT_ID=SmartEM_Agent\n"
            "KEYCLOAK_CLIENT_SECRET=s3cret\n"
        )
        config = load_keycloak_config(config_file)
        assert config.url == "http://kc.local"

    def test_load_strips_whitespace_around_values(self, tmp_path):
        config_file = tmp_path / "agent.env"
        config_file.write_text(
            "KEYCLOAK_URL =   http://kc.local  \n"
            "KEYCLOAK_REALM=dls\n"
            "KEYCLOAK_CLIENT_ID=SmartEM_Agent\n"
            "KEYCLOAK_CLIENT_SECRET=s3cret\n"
        )
        config = load_keycloak_config(config_file)
        assert config.url == "http://kc.local"

    def test_missing_file_raises_file_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="not found"):
            load_keycloak_config(tmp_path / "does-not-exist.env")

    def test_missing_required_value_raises_value_error(self, tmp_path):
        config_file = tmp_path / "agent.env"
        config_file.write_text(
            "KEYCLOAK_URL=http://kc.local\n"
            "KEYCLOAK_REALM=dls\n"
            "KEYCLOAK_CLIENT_ID=SmartEM_Agent\n"
            # KEYCLOAK_CLIENT_SECRET missing
        )
        with pytest.raises(ValueError, match="KEYCLOAK_CLIENT_SECRET"):
            load_keycloak_config(config_file)

    def test_empty_required_value_raises_value_error(self, tmp_path):
        config_file = tmp_path / "agent.env"
        config_file.write_text(
            "KEYCLOAK_URL=http://kc.local\n"
            "KEYCLOAK_REALM=\n"
            "KEYCLOAK_CLIENT_ID=SmartEM_Agent\n"
            "KEYCLOAK_CLIENT_SECRET=s3cret\n"
        )
        with pytest.raises(ValueError, match="KEYCLOAK_REALM"):
            load_keycloak_config(config_file)


class TestTokenFetch:
    def test_token_url_composed_from_config(self):
        client = KeycloakClient(_make_config())
        assert client._token_url == "http://keycloak.test/realms/dls/protocol/openid-connect/token"

    def test_token_url_strips_trailing_slash(self):
        config = KeycloakConfig(
            url="http://keycloak.test/", realm="dls", client_id="X", client_secret="Y"
        )
        client = KeycloakClient(config)
        assert client._token_url == "http://keycloak.test/realms/dls/protocol/openid-connect/token"

    def test_get_token_posts_client_credentials_grant(self):
        client = KeycloakClient(_make_config())
        with patch.object(client._session, "post") as mock_post:
            mock_post.return_value = _make_token_response("access-tok")
            token = client.get_token()
        assert token == "access-tok"
        call = mock_post.call_args
        assert call.args[0] == client._token_url
        assert call.kwargs["data"] == {
            "grant_type": "client_credentials",
            "client_id": "SmartEM_Agent",
            "client_secret": "secret-here",
        }

    def test_cached_token_returned_when_still_valid(self):
        client = KeycloakClient(_make_config(), refresh_buffer_seconds=30)
        with patch.object(client._session, "post") as mock_post:
            mock_post.return_value = _make_token_response("tok-1", expires_in=300)
            client.get_token()
            mock_post.reset_mock()
            second = client.get_token()
        assert second == "tok-1"
        mock_post.assert_not_called()

    def test_refresh_when_within_buffer_of_expiry(self):
        client = KeycloakClient(_make_config(), refresh_buffer_seconds=30)
        with patch.object(client._session, "post") as mock_post:
            mock_post.return_value = _make_token_response("tok-1", expires_in=300)
            client.get_token()
            # Simulate clock moving close to expiry (within the 30s buffer)
            client._token_expires_at = time.time() + 10
            mock_post.return_value = _make_token_response("tok-2", expires_in=300)
            second = client.get_token()
        assert second == "tok-2"

    def test_invalidate_forces_refetch(self):
        client = KeycloakClient(_make_config())
        with patch.object(client._session, "post") as mock_post:
            mock_post.return_value = _make_token_response("tok-1", expires_in=300)
            client.get_token()
            client.invalidate()
            mock_post.return_value = _make_token_response("tok-2", expires_in=300)
            second = client.get_token()
        assert second == "tok-2"

    def test_http_error_from_keycloak_surfaces(self):
        client = KeycloakClient(_make_config())
        with patch.object(client._session, "post") as mock_post:
            mock_post.side_effect = requests.HTTPError("401")
            with pytest.raises(requests.HTTPError):
                client.get_token()

    def test_network_error_surfaces(self):
        client = KeycloakClient(_make_config())
        with patch.object(client._session, "post") as mock_post:
            mock_post.side_effect = requests.ConnectionError("unreachable")
            with pytest.raises(requests.ConnectionError):
                client.get_token()

    def test_missing_access_token_in_response_raises(self):
        client = KeycloakClient(_make_config())
        with patch.object(client._session, "post") as mock_post:
            response = MagicMock()
            response.raise_for_status = MagicMock()
            response.json.return_value = {}  # no access_token
            mock_post.return_value = response
            with pytest.raises(KeyError):
                client.get_token()

    def test_default_expires_in_used_when_absent(self):
        client = KeycloakClient(_make_config())
        with patch.object(client._session, "post") as mock_post:
            response = MagicMock()
            response.raise_for_status = MagicMock()
            response.json.return_value = {"access_token": "tok"}  # no expires_in
            mock_post.return_value = response
            client.get_token()
        # Default is 300s, expiry should be ~now+300
        assert client._token_expires_at > time.time() + 250
        assert client._token_expires_at < time.time() + 350


class TestContextManager:
    def test_context_manager_closes_session(self):
        client = KeycloakClient(_make_config())
        with patch.object(client._session, "close") as mock_close:
            with client:
                pass
        mock_close.assert_called_once()
