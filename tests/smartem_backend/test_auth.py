"""Tests for the Keycloak JWT verification dependency.

These cover the routing and claim-validation behaviour. End-to-end signature
verification against a live Keycloak is exercised in staging - constructing a
fake JWKS here adds machinery without adding confidence in the small
validate-and-decode call.
"""

import pytest


@pytest.fixture(autouse=True)
def keycloak_env(monkeypatch):
    """Auth always runs; KEYCLOAK_URL must be set or the JWKS client raises.

    Also resets the cached JWKS client so each test picks up env on next request,
    and clears any leftover azp allow-list from prior tests.
    """
    monkeypatch.setenv("KEYCLOAK_URL", "http://keycloak-service:8080")
    monkeypatch.delenv("KEYCLOAK_ALLOWED_AZP", raising=False)
    import smartem_backend.auth as auth_module

    monkeypatch.setattr(auth_module, "_jwks_client", None)


class TestAuthValidation:
    def test_exempt_path_no_token_succeeds(self, real_auth_client):
        assert real_auth_client.get("/status").status_code == 200
        assert real_auth_client.get("/health").status_code in (200, 503)
        assert real_auth_client.get("/openapi.json").status_code == 200

    def test_protected_endpoint_without_token_returns_401(self, real_auth_client):
        response = real_auth_client.get("/acquisitions")
        assert response.status_code == 401
        assert response.headers.get("www-authenticate") == "Bearer"
        assert "Authorization" in response.json()["detail"]

    def test_protected_endpoint_with_malformed_token_returns_401(self, real_auth_client):
        response = real_auth_client.get(
            "/acquisitions",
            headers={"Authorization": "Bearer not-a-real-jwt"},
        )
        assert response.status_code == 401
        assert response.headers.get("www-authenticate") == "Bearer"

    def test_non_bearer_scheme_returns_401(self, real_auth_client):
        response = real_auth_client.get(
            "/acquisitions",
            headers={"Authorization": "Basic dXNlcjpwYXNz"},
        )
        assert response.status_code == 401

    def test_empty_bearer_returns_401(self, real_auth_client):
        response = real_auth_client.get("/acquisitions", headers={"Authorization": "Bearer "})
        assert response.status_code == 401


class TestAzpAllowList:
    """The azp (authorised party) claim is the OAuth client a token was issued
    to. When `KEYCLOAK_ALLOWED_AZP` is set, only tokens with one of those `azp`
    values are accepted. End-to-end check is exercised in staging; here we
    pin the parser and the decision logic.
    """

    def test_empty_env_means_no_check(self, monkeypatch):
        monkeypatch.setenv("KEYCLOAK_ALLOWED_AZP", "")
        from smartem_backend import auth

        assert auth._allowed_azps() == frozenset()

    def test_unset_env_means_no_check(self, monkeypatch):
        monkeypatch.delenv("KEYCLOAK_ALLOWED_AZP", raising=False)
        from smartem_backend import auth

        assert auth._allowed_azps() == frozenset()

    def test_single_value_parsed(self, monkeypatch):
        monkeypatch.setenv("KEYCLOAK_ALLOWED_AZP", "SmartEM_Agent")
        from smartem_backend import auth

        assert auth._allowed_azps() == frozenset({"SmartEM_Agent"})

    def test_comma_separated_parsed_and_trimmed(self, monkeypatch):
        monkeypatch.setenv("KEYCLOAK_ALLOWED_AZP", " SmartEM_User , SmartEM_Agent ")
        from smartem_backend import auth

        assert auth._allowed_azps() == frozenset({"SmartEM_User", "SmartEM_Agent"})

    def test_disallowed_azp_rejected_post_decode(self, monkeypatch):
        """The post-decode azp check raises 401 when the claim's azp is not on
        the allow-list. We bypass the JWKS/signature dance by stubbing the
        signing-key lookup and jwt.decode."""
        monkeypatch.setenv("KEYCLOAK_ALLOWED_AZP", "SmartEM_User,SmartEM_Agent")
        from smartem_backend import auth

        class _FakeKey:
            key = "fake-key"

        class _FakeJWKSClient:
            def get_signing_key_from_jwt(self, token):
                return _FakeKey()

        monkeypatch.setattr(auth, "_jwks_client", _FakeJWKSClient())
        monkeypatch.setattr(auth.jwt, "decode", lambda *a, **kw: {"sub": "u", "azp": "EvilClient"})

        with pytest.raises(auth.HTTPException) as exc:
            auth._verify("any-token")
        assert exc.value.status_code == 401
        assert "azp" in exc.value.detail.lower()

    def test_allowed_azp_accepted_post_decode(self, monkeypatch):
        monkeypatch.setenv("KEYCLOAK_ALLOWED_AZP", "SmartEM_Agent")
        from smartem_backend import auth

        class _FakeKey:
            key = "fake-key"

        class _FakeJWKSClient:
            def get_signing_key_from_jwt(self, token):
                return _FakeKey()

        monkeypatch.setattr(auth, "_jwks_client", _FakeJWKSClient())
        claims = {"sub": "u", "azp": "SmartEM_Agent"}
        monkeypatch.setattr(auth.jwt, "decode", lambda *a, **kw: claims)

        assert auth._verify("any-token") == claims


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


class TestLeeway:
    def test_leeway_passed_to_jwt_decode(self, monkeypatch):
        """The configured leeway must reach `jwt.decode` so modest clock skew
        between hosts doesn't immediately invalidate tokens."""
        from smartem_backend import auth

        captured: dict = {}

        class _FakeKey:
            key = "fake-key"

        class _FakeJWKSClient:
            def get_signing_key_from_jwt(self, token):
                return _FakeKey()

        def _capture_decode(token, key, **kwargs):
            captured.update(kwargs)
            return {"sub": "u", "azp": "x"}

        monkeypatch.setattr(auth, "_jwks_client", _FakeJWKSClient())
        monkeypatch.setattr(auth.jwt, "decode", _capture_decode)

        auth._verify("any-token")
        assert captured.get("leeway") == auth.JWT_LEEWAY_SECONDS
