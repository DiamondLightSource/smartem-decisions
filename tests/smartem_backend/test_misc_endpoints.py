"""TestClient coverage for /status, /health, /quality_metrics, /grid/{uuid}/model_weights (issue #258)."""

import pytest

from smartem_backend import api_server

from ._async_db_stub import make_execute_result
from .conftest import set_db_row


class TestGetStatus:
    def test_returns_ok(self, client):
        resp = client.get("/status")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body["service"] == "SmartEM Decisions API"
        assert "configuration" in body
        assert "endpoints" in body
        assert body["endpoints"]["health"] == "/health"


class TestGetVersion:
    def test_returns_service_and_version(self, client):
        resp = client.get("/version")
        assert resp.status_code == 200
        body = resp.json()
        assert body["service"] == "smartem-decisions"
        assert isinstance(body["version"], str) and body["version"]


class TestGetHealth:
    @pytest.fixture
    def patch_health_checks(self, monkeypatch):
        async def _ok_db():
            return {"status": "ok", "details": "stubbed"}

        def _ok_mq():
            return {"status": "ok", "details": "stubbed"}

        monkeypatch.setattr(api_server, "check_database_health", _ok_db)
        monkeypatch.setattr(api_server, "check_rabbitmq_health", _ok_mq)
        return monkeypatch

    def test_returns_ok_when_all_services_ok(self, client, patch_health_checks):
        resp = client.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body["services"]["database"]["status"] == "ok"
        assert body["services"]["event_broker"]["status"] == "ok"

    def test_503_when_db_degraded(self, client, monkeypatch):
        async def _bad_db():
            return {"status": "error", "details": "down"}

        def _ok_mq():
            return {"status": "ok", "details": "stubbed"}

        monkeypatch.setattr(api_server, "check_database_health", _bad_db)
        monkeypatch.setattr(api_server, "check_rabbitmq_health", _ok_mq)
        resp = client.get("/health")
        assert resp.status_code == 503
        body = resp.json()
        assert body["detail"]["status"] == "degraded"
        assert body["detail"]["services"]["database"]["status"] == "error"


class TestGetQualityMetrics:
    def test_happy_path_with_no_data(self, client):
        client._db.execute.return_value = make_execute_result(None)
        resp = client.get("/quality_metrics")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_predictions"] == 0
        assert body["models_count"] == 0
        assert body["average_quality"] is None
        assert body["min_quality"] is None
        assert body["max_quality"] is None

    def test_happy_path_with_aggregates(self, client):
        results = iter(
            [
                make_execute_result(42),
                make_execute_result(0.5),
                make_execute_result(0.1),
                make_execute_result(0.9),
                make_execute_result(3),
            ]
        )
        client._db.execute.side_effect = lambda *a, **kw: next(results)

        resp = client.get("/quality_metrics")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_predictions"] == 42
        assert body["average_quality"] == 0.5
        assert body["min_quality"] == 0.1
        assert body["max_quality"] == 0.9
        assert body["models_count"] == 3


class TestGetGridModelWeights:
    def test_returns_empty_dict_when_no_weights(self, client):
        set_db_row(client, [])
        resp = client.get("/grid/grid-1/model_weights")
        assert resp.status_code == 200
        assert resp.json() == {}
