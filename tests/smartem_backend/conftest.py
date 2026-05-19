"""Shared fixtures for FastAPI TestClient-based endpoint tests.

The pattern (established in `test_processing_feedback_endpoints.py` and
`test_batch_gridsquare_creation.py`):

- Set `SKIP_DB_INIT=true` before importing api_server so the SQLAlchemy
  engine is never built.
- Override `get_db` with a `make_async_db()` mock; tests assert on
  `db.add` / `db.commit` / `db.execute` and tweak `db.execute.return_value`
  for not-found / no-row cases.
- Tests monkeypatch the individual `publish_*` helpers they care about.

This conftest lifts the boilerplate out of each new test file. Do NOT
import `api_server` at module level here - the SKIP_DB_INIT env var must
be set first, and the existing per-file pattern (set env var, then import)
is the cleanest way to keep that ordering explicit at the test-file level.
"""

import os

os.environ.setdefault("SKIP_DB_INIT", "true")

import pytest
from fastapi.testclient import TestClient

from smartem_backend import api_server
from smartem_backend.api_server import app, get_db
from smartem_backend.auth import verify_token

from ._async_db_stub import make_async_db, make_execute_result


@pytest.fixture
def db():
    """Fresh AsyncSession-shaped mock per test."""
    return make_async_db()


@pytest.fixture
def client(db):
    """TestClient with `get_db` overridden and `verify_token` bypassed.

    The verify_token override returns a stub claims dict so the global FastAPI
    auth dependency is satisfied without any real token-issuing machinery. Tests
    that exercise the real auth dependency should use `real_auth_client`.

    The mock db is reachable as `client._db`.
    """
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[verify_token] = lambda: {"sub": "test-user", "azp": "SmartEM_User"}
    try:
        with TestClient(app) as tc:
            tc._db = db
            yield tc
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(verify_token, None)


@pytest.fixture
def real_auth_client(db):
    """TestClient with `get_db` overridden but the real `verify_token` dependency
    is left in place. Used in `test_auth.py` to exercise the actual auth path.
    """
    app.dependency_overrides[get_db] = lambda: db
    try:
        with TestClient(app) as tc:
            tc._db = db
            yield tc
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def stub_publisher(monkeypatch):
    """Factory for stubbing `api_server.publish_*` helpers with a shared call log.

    Usage:
        calls = stub_publisher("publish_acquisition_created")
        ...
        assert calls[0]["uuid"] == "acq-1"

    The factory returns a list that future invocations append a kwargs-dict to.
    Returns True by default (publish succeeded). Use `stub_publisher(..., return_value=False)`
    to simulate publish failure.
    """

    def _factory(name: str, return_value: bool = True) -> list:
        calls: list[dict] = []

        async def _fake(*args, **kwargs):
            entry = {"args": args, **kwargs} if args else kwargs
            calls.append(entry)
            return return_value

        monkeypatch.setattr(api_server, name, _fake)
        return calls

    return _factory


def set_db_row(client: TestClient, row) -> None:
    """Convenience: have the next `db.execute(...).scalars().first()/one()` return `row`."""
    client._db.execute.return_value = make_execute_result(row)
