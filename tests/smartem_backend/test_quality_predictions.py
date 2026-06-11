"""TestClient coverage for /quality_predictions and the gridsquare-nested GETs (issue #258)."""

from ._async_db_stub import make_execute_result
from .conftest import set_db_row


def _qp_payload(**overrides) -> dict:
    base = {
        "value": 0.42,
        "prediction_model_name": "model-a",
        "gridsquare_uuid": "gs-1",
    }
    base.update(overrides)
    return base


def _gridsquare_then(rows):
    from smartem_backend.model.database import GridSquare

    results = iter(
        [
            make_execute_result(GridSquare(uuid="gs-1", grid_uuid="grid-1", gridsquare_id="gs-id-1")),
            make_execute_result(rows),
        ]
    )
    return lambda *a, **kw: next(results)


class TestGetGridSquareQualityPredictions:
    def test_404_when_gridsquare_missing(self, client):
        set_db_row(client, None)
        resp = client.get("/gridsquares/missing/quality_predictions")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    def test_returns_dict_shaped_time_series(self, client):
        client._db.execute.side_effect = _gridsquare_then([])
        resp = client.get("/gridsquares/gs-1/quality_predictions")
        assert resp.status_code == 200
        assert resp.json() == {}


class TestGetGridSquareFoilHoleQualityPredictions:
    def test_404_when_gridsquare_missing(self, client):
        set_db_row(client, None)
        resp = client.get("/gridsquares/missing/foilhole_quality_predictions")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    def test_returns_dict_shaped_time_series(self, client):
        client._db.execute.side_effect = _gridsquare_then([])
        resp = client.get("/gridsquares/gs-1/foilhole_quality_predictions")
        assert resp.status_code == 200
        assert resp.json() == {}


class TestCreateQualityPrediction:
    def test_404_when_gridsquare_missing(self, client):
        client._db.execute.return_value = make_execute_result(None)
        resp = client.post("/quality_predictions", json=_qp_payload(gridsquare_uuid="missing"))
        assert resp.status_code == 404
        assert "GridSquare" in resp.json()["detail"]
        client._db.add.assert_not_called()

    def test_404_when_foilhole_missing(self, client):
        client._db.execute.return_value = make_execute_result(None)
        resp = client.post(
            "/quality_predictions",
            json=_qp_payload(gridsquare_uuid=None, foilhole_uuid="missing"),
        )
        assert resp.status_code == 404
        assert "FoilHole" in resp.json()["detail"]
        client._db.add.assert_not_called()

    def test_404_when_model_missing(self, client):
        from smartem_backend.model.database import GridSquare

        results = iter(
            [
                make_execute_result(GridSquare(uuid="gs-1", grid_uuid="grid-1", gridsquare_id="gs-id-1")),
                make_execute_result(None),
            ]
        )
        client._db.execute.side_effect = lambda *a, **kw: next(results)

        resp = client.post("/quality_predictions", json=_qp_payload(prediction_model_name="missing"))
        assert resp.status_code == 404
        assert "Prediction model" in resp.json()["detail"]
        client._db.add.assert_not_called()

    def test_missing_required_returns_422(self, client):
        resp = client.post("/quality_predictions", json={"value": 0.5})
        assert resp.status_code == 422
        client._db.add.assert_not_called()
