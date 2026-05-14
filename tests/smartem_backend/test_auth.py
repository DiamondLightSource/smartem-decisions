"""Tests for the Keycloak JWT verification dependency.

These cover the gating and routing behaviour. End-to-end signature verification
against a live Keycloak is exercised in staging - constructing a fake JWKS here
adds machinery without adding confidence in the small validate-and-decode call.
"""

import os

import pytest

from .conftest import app, client  # noqa: F401 - re-export fixture


@pytest.fixture(autouse=True)
def reset_auth_env(monkeypatch):
    """Ensure each test starts with KEYCLOAK_AUTH_REQUIRED unset (effectively false)."""
    monkeypatch.delenv("KEYCLOAK_AUTH_REQUIRED", raising=False)
    monkeypatch.delenv("KEYCLOAK_URL", raising=False)


class TestAuthDisabledByDefault:
    def test_unauthenticated_status_call_succeeds(self, client):
        # Disabled-by-default behaviour is implicitly covered by the rest of the
        # backend test suite, which all runs without an Authorization header and
        # expects normal responses. This case just pins the contract explicitly.
        response = client.get("/status")
        assert response.status_code == 200


class TestAuthRequired:
    @pytest.fixture(autouse=True)
    def enable_auth(self, monkeypatch):
        monkeypatch.setenv("KEYCLOAK_AUTH_REQUIRED", "true")
        monkeypatch.setenv("KEYCLOAK_URL", "http://keycloak-service:8080")
        # Reset cached JWKS client so it picks up env on next request.
        import smartem_backend.auth as auth_module
        monkeypatch.setattr(auth_module, "_jwks_client", None)

    def test_exempt_path_no_token_succeeds(self, client):
        assert client.get("/status").status_code == 200
        assert client.get("/health").status_code in (200, 503)
        assert client.get("/openapi.json").status_code == 200

    def test_protected_endpoint_without_token_returns_401(self, client):
        response = client.get("/acquisitions")
        assert response.status_code == 401
        assert response.headers.get("www-authenticate") == "Bearer"
        assert "Authorization" in response.json()["detail"]

    def test_protected_endpoint_with_malformed_token_returns_401(self, client):
        response = client.get(
            "/acquisitions",
            headers={"Authorization": "Bearer not-a-real-jwt"},
        )
        assert response.status_code == 401
        assert response.headers.get("www-authenticate") == "Bearer"

    def test_non_bearer_scheme_returns_401(self, client):
        response = client.get(
            "/acquisitions",
            headers={"Authorization": "Basic dXNlcjpwYXNz"},
        )
        assert response.status_code == 401

    def test_empty_bearer_returns_401(self, client):
        response = client.get("/acquisitions", headers={"Authorization": "Bearer "})
        assert response.status_code == 401


class TestConfigHelpers:
    def test_issuer_from_env(self, monkeypatch):
        monkeypatch.setenv("KEYCLOAK_URL", "https://identity-test.diamond.ac.uk/")
        monkeypatch.setenv("KEYCLOAK_REALM", "dls")
        from smartem_backend import auth

        assert auth._issuer() == "https://identity-test.diamond.ac.uk/realms/dls"
        assert auth._jwks_url() == (
            "https://identity-test.diamond.ac.uk/realms/dls/protocol/openid-connect/certs"
        )

    def test_jwks_client_requires_url(self, monkeypatch):
        monkeypatch.delenv("KEYCLOAK_URL", raising=False)
        from smartem_backend import auth

        monkeypatch.setattr(auth, "_jwks_client", None)
        with pytest.raises(RuntimeError, match="KEYCLOAK_URL"):
            auth._get_jwks_client()


_ = os  # silence unused-import lint when env helpers aren't touched
