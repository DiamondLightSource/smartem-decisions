"""Regression guards for the atlas RabbitMQ event field contract (issue #254).

`publish_atlas_created` used to receive `id=db_atlas.name` while the paired
`publish_atlas_updated` received `id=db_atlas.atlas_id`. Downstream consumers
saw two different things under the same nominal `id` field. The fix is trivial
(use `atlas_id` in both) but there is no test asserting the contract, so the
bug could regress silently. These tests lock the contract in place.
"""

import os
from unittest.mock import MagicMock

os.environ["SKIP_DB_INIT"] = "true"

import pytest
from fastapi.testclient import TestClient

from smartem_backend import api_server
from smartem_backend.api_server import app, get_db


@pytest.fixture
def captured():
    return {}


@pytest.fixture
def client(captured, monkeypatch):
    def _capture(name):
        def _inner(**kwargs):
            captured[name] = kwargs
            return True

        return _inner

    monkeypatch.setattr(api_server, "publish_atlas_created", _capture("atlas_created"))
    monkeypatch.setattr(api_server, "publish_atlas_updated", _capture("atlas_updated"))

    db = MagicMock()
    app.dependency_overrides[get_db] = lambda: db
    try:
        with TestClient(app) as tc:
            tc._db = db
            yield tc
    finally:
        app.dependency_overrides.pop(get_db, None)


def _atlas_payload(**overrides) -> dict:
    base = {
        "uuid": "atlas-uuid-1",
        "grid_uuid": "grid-uuid-1",
        "atlas_id": "ATLAS_001",
        "name": "Session 42 atlas",
    }
    base.update(overrides)
    return base


class TestAtlasCreatedEventContract:
    """`id` in the ATLAS_CREATED event must carry `atlas_id`, not `name`."""

    def test_id_is_atlas_id_not_name(self, client, captured):
        payload = _atlas_payload(atlas_id="ATLAS_001", name="some-display-name")
        resp = client.post("/grids/grid-uuid-1/atlas", json=payload)
        assert resp.status_code == 201, resp.text

        call = captured.get("atlas_created")
        assert call is not None, "publish_atlas_created was not called"
        assert call["id"] == "ATLAS_001"
        assert call["id"] != "some-display-name"
        assert call["uuid"] == "atlas-uuid-1"
        assert call["grid_uuid"] == "grid-uuid-1"
