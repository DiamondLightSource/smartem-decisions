"""End-to-end checks for the processing-feedback publish endpoints (issue #250).

These endpoints are thin wrappers: they verify the micrograph exists, then call
one of the existing RabbitMQ publish helpers. Tests stub the DB dependency and
monkeypatch the publish helpers so nothing real is touched.
"""

import os
from dataclasses import dataclass
from unittest.mock import MagicMock

os.environ["SKIP_DB_INIT"] = "true"

import pytest
from fastapi.testclient import TestClient

from smartem_backend import api_server
from smartem_backend.api_server import app, get_db


@dataclass
class _Captured:
    name: str
    kwargs: dict


@pytest.fixture
def captured():
    return []


@pytest.fixture
def client(captured, monkeypatch):
    def _fake_publish(name, return_value=True):
        async def _inner(**kwargs):
            captured.append(_Captured(name=name, kwargs=kwargs))
            return return_value

        return _inner

    monkeypatch.setattr(api_server, "publish_motion_correction_completed", _fake_publish("motion_completed"))
    monkeypatch.setattr(api_server, "publish_motion_correction_registered", _fake_publish("motion_registered"))
    monkeypatch.setattr(api_server, "publish_ctf_estimation_completed", _fake_publish("ctf_completed"))
    monkeypatch.setattr(api_server, "publish_ctf_estimation_registered", _fake_publish("ctf_registered"))

    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = object()

    app.dependency_overrides[get_db] = lambda: db
    try:
        with TestClient(app) as tc:
            tc._db = db
            yield tc
    finally:
        app.dependency_overrides.pop(get_db, None)


class TestMotionCorrectionCompleted:
    endpoint = "/micrographs/abc-123/motion_correction/completed"

    def test_happy_path(self, client, captured):
        resp = client.post(self.endpoint, json={"total_motion": 1.5, "average_motion": 0.1})
        assert resp.status_code == 202
        assert resp.json() == {"published": True}
        assert len(captured) == 1
        assert captured[0].name == "motion_completed"
        assert captured[0].kwargs == {
            "micrograph_uuid": "abc-123",
            "total_motion": 1.5,
            "average_motion": 0.1,
        }

    def test_missing_micrograph_returns_404(self, client, captured):
        client._db.query.return_value.filter.return_value.first.return_value = None
        resp = client.post(self.endpoint, json={"total_motion": 1.5, "average_motion": 0.1})
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Micrograph not found"
        assert captured == []

    def test_publish_failure_returns_502(self, client, captured, monkeypatch):
        async def _fail(**_):
            return False

        monkeypatch.setattr(api_server, "publish_motion_correction_completed", _fail)
        resp = client.post(self.endpoint, json={"total_motion": 1.5, "average_motion": 0.1})
        assert resp.status_code == 502
        assert "motion_correction_completed" in resp.json()["detail"]

    def test_missing_body_field_returns_422(self, client):
        resp = client.post(self.endpoint, json={"total_motion": 1.5})
        assert resp.status_code == 422


class TestMotionCorrectionRegistered:
    endpoint = "/micrographs/abc-123/motion_correction/registered"

    def test_happy_path_with_metric_name(self, client, captured):
        resp = client.post(self.endpoint, json={"quality": True, "metric_name": "drift"})
        assert resp.status_code == 202
        assert captured[0].kwargs == {
            "micrograph_uuid": "abc-123",
            "quality": True,
            "metric_name": "drift",
        }

    def test_metric_name_optional(self, client, captured):
        resp = client.post(self.endpoint, json={"quality": False})
        assert resp.status_code == 202
        assert captured[0].kwargs == {
            "micrograph_uuid": "abc-123",
            "quality": False,
            "metric_name": None,
        }


class TestCtfEstimationCompleted:
    endpoint = "/micrographs/abc-123/ctf_estimation/completed"

    def test_happy_path(self, client, captured):
        resp = client.post(self.endpoint, json={"ctf_max_res": 3.2})
        assert resp.status_code == 202
        assert captured[0].name == "ctf_completed"
        assert captured[0].kwargs == {"micrograph_uuid": "abc-123", "ctf_max_res": 3.2}


class TestCtfEstimationRegistered:
    endpoint = "/micrographs/abc-123/ctf_estimation/registered"

    def test_happy_path(self, client, captured):
        resp = client.post(self.endpoint, json={"quality": True, "metric_name": "astigmatism"})
        assert resp.status_code == 202
        assert captured[0].name == "ctf_registered"
        assert captured[0].kwargs == {
            "micrograph_uuid": "abc-123",
            "quality": True,
            "metric_name": "astigmatism",
        }
