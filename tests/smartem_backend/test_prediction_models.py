"""TestClient coverage for the /prediction_models endpoints (issue #258)."""

from .conftest import set_db_row


def _payload(name: str = "model-a", **overrides) -> dict:
    base = {"name": name, "description": "test model"}
    base.update(overrides)
    return base


class TestListPredictionModels:
    def test_returns_empty_list(self, client):
        set_db_row(client, [])
        resp = client.get("/prediction_models")
        assert resp.status_code == 200
        assert resp.json() == []


class TestGetPredictionModel:
    def test_404_when_not_found(self, client):
        set_db_row(client, None)
        resp = client.get("/prediction_models/missing")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    def test_happy_path_returns_model(self, client):
        from smartem_backend.model.database import QualityPredictionModel

        set_db_row(client, QualityPredictionModel(name="model-a", description="desc"))
        resp = client.get("/prediction_models/model-a")
        assert resp.status_code == 200
        assert resp.json()["name"] == "model-a"


class TestCreatePredictionModel:
    def test_happy_path_when_name_unique(self, client):
        set_db_row(client, None)  # no existing
        resp = client.post("/prediction_models", json=_payload())
        assert resp.status_code == 201
        assert resp.json()["name"] == "model-a"
        client._db.add.assert_called_once()
        client._db.commit.assert_called_once()

    def test_409_when_name_already_exists(self, client):
        from smartem_backend.model.database import QualityPredictionModel

        set_db_row(client, QualityPredictionModel(name="model-a"))
        resp = client.post("/prediction_models", json=_payload())
        assert resp.status_code == 409
        client._db.add.assert_not_called()

    def test_missing_name_returns_422(self, client):
        resp = client.post("/prediction_models", json={"description": "no name"})
        assert resp.status_code == 422


class TestUpdatePredictionModel:
    def test_happy_path(self, client):
        from smartem_backend.model.database import QualityPredictionModel

        set_db_row(client, QualityPredictionModel(name="model-a", description="old"))
        resp = client.put("/prediction_models/model-a", json={"description": "new"})
        assert resp.status_code == 200
        client._db.commit.assert_called_once()

    def test_404_when_not_found(self, client):
        set_db_row(client, None)
        resp = client.put("/prediction_models/missing", json={"description": "x"})
        assert resp.status_code == 404
        client._db.commit.assert_not_called()


class TestDeletePredictionModel:
    def test_happy_path_returns_204(self, client):
        from smartem_backend.model.database import QualityPredictionModel

        set_db_row(client, QualityPredictionModel(name="model-a"))
        resp = client.delete("/prediction_models/model-a")
        assert resp.status_code == 204
        client._db.delete.assert_awaited_once()
        client._db.commit.assert_called_once()

    def test_404_when_not_found(self, client):
        set_db_row(client, None)
        resp = client.delete("/prediction_models/missing")
        assert resp.status_code == 404
        client._db.delete.assert_not_called()
