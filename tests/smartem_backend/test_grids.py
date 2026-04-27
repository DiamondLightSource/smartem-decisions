"""TestClient coverage for the /grids and /acquisitions/{uuid}/grids endpoints (issue #258)."""

from .conftest import set_db_row


def _grid_payload(uuid: str = "grid-1", **overrides) -> dict:
    base = {
        "uuid": uuid,
        "name": "test-grid",
        "acquisition_uuid": "acq-1",
    }
    base.update(overrides)
    return base


class TestListGrids:
    def test_returns_empty_list(self, client):
        set_db_row(client, [])
        resp = client.get("/grids")
        assert resp.status_code == 200
        assert resp.json() == []


class TestGetGrid:
    def test_404_when_not_found(self, client):
        set_db_row(client, None)
        resp = client.get("/grids/missing")
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Grid not found"


class TestUpdateGrid:
    def test_happy_path_publishes(self, client, stub_publisher):
        from smartem_backend.model.database import Grid
        from smartem_backend.model.entity_status import GridStatus

        existing = Grid(
            uuid="grid-1",
            acquisition_uuid="acq-1",
            name="old",
            status=GridStatus.NONE,
        )
        set_db_row(client, existing)
        calls = stub_publisher("publish_grid_updated")

        resp = client.put("/grids/grid-1", json={"name": "new"})

        assert resp.status_code == 200
        client._db.commit.assert_called_once()
        assert calls == [{"uuid": "grid-1", "acquisition_uuid": "acq-1"}]

    def test_404_when_not_found(self, client, stub_publisher):
        set_db_row(client, None)
        calls = stub_publisher("publish_grid_updated")
        resp = client.put("/grids/missing", json={"name": "x"})
        assert resp.status_code == 404
        assert calls == []


class TestDeleteGrid:
    def test_happy_path_publishes(self, client, stub_publisher):
        from smartem_backend.model.database import Grid

        set_db_row(client, Grid(uuid="grid-1", acquisition_uuid="acq-1", name="g"))
        calls = stub_publisher("publish_grid_deleted")

        resp = client.delete("/grids/grid-1")
        assert resp.status_code == 204
        assert calls == [{"uuid": "grid-1"}]

    def test_404_when_not_found(self, client, stub_publisher):
        set_db_row(client, None)
        calls = stub_publisher("publish_grid_deleted")
        resp = client.delete("/grids/missing")
        assert resp.status_code == 404
        assert calls == []


class TestListAcquisitionGrids:
    def test_returns_empty_list(self, client):
        set_db_row(client, [])
        resp = client.get("/acquisitions/acq-1/grids")
        assert resp.status_code == 200
        assert resp.json() == []


class TestCreateAcquisitionGrid:
    def test_happy_path_persists_and_publishes(self, client, stub_publisher):
        calls = stub_publisher("publish_grid_created")

        resp = client.post("/acquisitions/acq-1/grids", json=_grid_payload())

        assert resp.status_code == 201
        body = resp.json()
        assert body["uuid"] == "grid-1"
        assert body["acquisition_uuid"] == "acq-1"
        assert body["status"] == "none"

        client._db.add.assert_called_once()
        client._db.commit.assert_called_once()
        assert calls == [{"uuid": "grid-1", "acquisition_uuid": "acq-1"}]

    def test_missing_required_field_returns_422(self, client, stub_publisher):
        calls = stub_publisher("publish_grid_created")
        resp = client.post("/acquisitions/acq-1/grids", json={"uuid": "grid-1"})
        assert resp.status_code == 422
        client._db.add.assert_not_called()
        assert calls == []


class TestGridRegistered:
    def test_publishes_and_returns_success(self, client, stub_publisher):
        calls = stub_publisher("publish_grid_registered")
        resp = client.post("/grids/grid-1/registered")
        assert resp.status_code == 200
        assert resp.json() is True
        assert len(calls) == 1
