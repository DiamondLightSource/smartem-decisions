"""Tests for the Keycloak Bearer-token integration in SmartEMAPIClient.

These verify that requests carry an Authorization header when a KeycloakClient
is configured, that a 401 triggers a single refresh-and-retry, and that the
client is backwards compatible when no KeycloakClient is provided.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from smartem_backend.api_client import SmartEMAPIClient


def _ok_response(json_body=None, status: int = 200) -> MagicMock:
    response = MagicMock()
    response.status_code = status
    response.raise_for_status = MagicMock()
    response.json.return_value = json_body if json_body is not None else {"status": "ok"}
    return response


def _unauthorized_response() -> MagicMock:
    response = MagicMock()
    response.status_code = 401
    response.raise_for_status = MagicMock()
    response.json.return_value = {"detail": "unauthorized"}
    return response


class TestBackwardCompatibility:
    def test_no_keycloak_client_no_auth_header(self):
        client = SmartEMAPIClient("http://api.test")
        client._session = MagicMock()
        client._session.request.return_value = _ok_response()

        client._request("get", "status")

        call = client._session.request.call_args
        headers = call.kwargs.get("headers")
        # When no keycloak client is configured, headers should be None or empty
        assert not headers or "Authorization" not in headers


class TestBearerAttachment:
    def test_authorization_header_set_from_keycloak_client(self):
        kc = MagicMock()
        kc.get_token.return_value = "abc.def.ghi"

        client = SmartEMAPIClient("http://api.test", keycloak_client=kc)
        client._session = MagicMock()
        client._session.request.return_value = _ok_response()

        client._request("get", "status")

        call = client._session.request.call_args
        headers = call.kwargs.get("headers") or {}
        assert headers.get("Authorization") == "Bearer abc.def.ghi"

    def test_token_fetched_per_request(self):
        kc = MagicMock()
        kc.get_token.return_value = "tok"
        client = SmartEMAPIClient("http://api.test", keycloak_client=kc)
        client._session = MagicMock()
        client._session.request.return_value = _ok_response()

        client._request("get", "status")
        client._request("get", "status")

        assert kc.get_token.call_count == 2


class TestRefreshOn401:
    def test_401_triggers_invalidate_and_retry_once(self):
        kc = MagicMock()
        kc.get_token.side_effect = ["stale-tok", "fresh-tok"]

        client = SmartEMAPIClient("http://api.test", keycloak_client=kc)
        client._session = MagicMock()
        client._session.request.side_effect = [_unauthorized_response(), _ok_response()]

        client._request("get", "status")

        kc.invalidate.assert_called_once()
        assert kc.get_token.call_count == 2
        assert client._session.request.call_count == 2
        # Second call must have used the fresh token
        second_call = client._session.request.call_args_list[1]
        assert second_call.kwargs.get("headers", {}).get("Authorization") == "Bearer fresh-tok"

    def test_second_401_after_refresh_surfaces_as_http_error(self):
        import requests

        kc = MagicMock()
        kc.get_token.side_effect = ["stale-tok", "still-bad-tok"]

        first_401 = _unauthorized_response()
        second_401 = _unauthorized_response()
        # The production error path reads e.response.status_code, so the mocked
        # HTTPError must carry a response attribute - matching the real
        # raise_for_status behaviour.
        second_401.raise_for_status.side_effect = requests.HTTPError("401", response=second_401)

        client = SmartEMAPIClient("http://api.test", keycloak_client=kc)
        client._session = MagicMock()
        client._session.request.side_effect = [first_401, second_401]

        with pytest.raises(requests.HTTPError):
            client._request("get", "status")

        kc.invalidate.assert_called_once()
        assert client._session.request.call_count == 2

    def test_no_refresh_when_no_keycloak_client(self):
        """A 401 with no KeycloakClient configured should not loop or retry."""
        import requests

        unauthorized = _unauthorized_response()
        unauthorized.raise_for_status.side_effect = requests.HTTPError("401", response=unauthorized)

        client = SmartEMAPIClient("http://api.test")
        client._session = MagicMock()
        client._session.request.return_value = unauthorized

        with pytest.raises(requests.HTTPError):
            client._request("get", "status")

        # Only one call - no refresh-and-retry
        assert client._session.request.call_count == 1
