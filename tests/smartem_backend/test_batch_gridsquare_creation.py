"""Tests for the bulk grid-square creation endpoint (issue #249).

Uses the same TestClient + dependency-override pattern established in
test_processing_feedback_endpoints.py. The DB is stubbed via MagicMock — we
assert on which ORM entities got added and which publish helper was called
with what payload. No Postgres, no RabbitMQ.
"""

import os
from unittest.mock import MagicMock

os.environ["SKIP_DB_INIT"] = "true"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from smartem_backend import api_server
from smartem_backend.api_server import app, get_db


def _gs(uuid: str, gridsquare_id: str = "gs-1", lowmag: bool = False) -> dict:
    return {
        "uuid": uuid,
        "gridsquare_id": gridsquare_id,
        "grid_uuid": "grid-abc",
        "lowmag": lowmag,
    }


@pytest.fixture
def publish_calls():
    return []


@pytest.fixture
def client(publish_calls, monkeypatch):
    def _fake_batch_publish(entries):
        publish_calls.append(list(entries))
        return True

    monkeypatch.setattr(api_server, "publish_gridsquares_created_batch", _fake_batch_publish)

    db = MagicMock()
    # Grid lookup returns a truthy object by default (grid exists)
    db.query.return_value.filter.return_value.first.return_value = object()

    app.dependency_overrides[get_db] = lambda: db
    try:
        with TestClient(app) as tc:
            tc._db = db
            yield tc
    finally:
        app.dependency_overrides.pop(get_db, None)


ENDPOINT = "/grids/grid-abc/gridsquares/batch"


class TestBatchCreateHappyPath:
    def test_inserts_all_and_publishes_batch(self, client, publish_calls):
        payload = {"gridsquares": [_gs("u-1"), _gs("u-2", lowmag=True), _gs("u-3")]}
        resp = client.post(ENDPOINT, json=payload)

        assert resp.status_code == 201
        body = resp.json()
        assert [gs["uuid"] for gs in body["gridsquares"]] == ["u-1", "u-2", "u-3"]

        # Single add_all call with 3 entities, single commit
        client._db.add_all.assert_called_once()
        added = client._db.add_all.call_args.args[0]
        assert len(added) == 3
        client._db.commit.assert_called_once()

        # Single batch publish with the right entries in the right order
        assert len(publish_calls) == 1
        assert publish_calls[0] == [
            ("u-1", "grid-abc", "gs-1", False),
            ("u-2", "grid-abc", "gs-1", True),
            ("u-3", "grid-abc", "gs-1", False),
        ]

    def test_empty_list_rejected(self, client):
        resp = client.post(ENDPOINT, json={"gridsquares": []})
        assert resp.status_code == 422

    def test_response_shape_matches_single_create_contract(self, client):
        resp = client.post(ENDPOINT, json={"gridsquares": [_gs("u-1")]})
        body = resp.json()["gridsquares"][0]
        assert body["uuid"] == "u-1"
        assert body["grid_uuid"] == "grid-abc"
        # status defaults to NONE (serialised via use_enum_values)
        assert body["status"] == "none"


class TestValidation:
    def test_duplicate_uuids_rejected(self, client):
        payload = {"gridsquares": [_gs("u-1"), _gs("u-1")]}
        resp = client.post(ENDPOINT, json=payload)
        assert resp.status_code == 422
        assert "duplicate" in resp.json()["detail"].lower()
        client._db.add_all.assert_not_called()

    def test_oversize_batch_rejected(self, client, monkeypatch):
        monkeypatch.setattr(api_server, "GRIDSQUARE_CREATE_BATCH_MAX", 2)
        payload = {"gridsquares": [_gs(f"u-{i}") for i in range(3)]}
        resp = client.post(ENDPOINT, json=payload)
        assert resp.status_code == 422
        assert "exceeds limit of 2" in resp.json()["detail"]
        client._db.add_all.assert_not_called()

    def test_missing_required_field_422(self, client):
        # uuid missing
        resp = client.post(ENDPOINT, json={"gridsquares": [{"gridsquare_id": "x", "grid_uuid": "grid-abc"}]})
        assert resp.status_code == 422


class TestErrorPaths:
    def test_grid_not_found_returns_404(self, client):
        client._db.query.return_value.filter.return_value.first.return_value = None
        resp = client.post(ENDPOINT, json={"gridsquares": [_gs("u-1")]})
        assert resp.status_code == 404
        client._db.add_all.assert_not_called()

    def test_integrity_error_returns_409_and_rolls_back(self, client):
        client._db.commit.side_effect = IntegrityError("insert", {}, Exception("duplicate key"))
        resp = client.post(ENDPOINT, json={"gridsquares": [_gs("u-1")]})
        assert resp.status_code == 409
        client._db.rollback.assert_called_once()

    def test_publish_failure_logged_but_not_fatal(self, client, monkeypatch):
        monkeypatch.setattr(api_server, "publish_gridsquares_created_batch", lambda _entries: False)
        resp = client.post(ENDPOINT, json={"gridsquares": [_gs("u-1")]})
        assert resp.status_code == 201
