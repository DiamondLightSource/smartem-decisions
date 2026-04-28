"""TestClient coverage for the /atlases and /grids/{uuid}/atlas endpoints (issue #258)."""

from .conftest import set_db_row


def _atlas_payload(uuid: str = "atlas-1", grid_uuid: str = "grid-1", **overrides) -> dict:
    base = {
        "uuid": uuid,
        "atlas_id": "a-1",
        "grid_uuid": grid_uuid,
        "name": "test-atlas",
    }
    base.update(overrides)
    return base


class TestListAtlases:
    def test_returns_empty_list(self, client):
        set_db_row(client, [])
        resp = client.get("/atlases")
        assert resp.status_code == 200
        assert resp.json() == []


class TestGetAtlas:
    def test_404_when_not_found(self, client):
        set_db_row(client, None)
        resp = client.get("/atlases/missing")
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Atlas not found"

    def test_happy_path_returns_atlas(self, client):
        from smartem_backend.model.database import Atlas

        set_db_row(client, Atlas(uuid="atlas-1", atlas_id="a-1", grid_uuid="grid-1", name="x"))
        resp = client.get("/atlases/atlas-1")
        assert resp.status_code == 200
        assert resp.json()["uuid"] == "atlas-1"


class TestUpdateAtlas:
    def test_happy_path_publishes(self, client, stub_publisher):
        from smartem_backend.model.database import Atlas

        existing = Atlas(uuid="atlas-1", atlas_id="a-1", grid_uuid="grid-1", name="old")
        set_db_row(client, existing)
        calls = stub_publisher("publish_atlas_updated")

        resp = client.put("/atlases/atlas-1", json={"name": "new"})
        assert resp.status_code == 200
        client._db.commit.assert_called_once()
        assert calls == [{"uuid": "atlas-1", "id": "a-1", "grid_uuid": "grid-1"}]

    def test_404_when_not_found(self, client, stub_publisher):
        set_db_row(client, None)
        calls = stub_publisher("publish_atlas_updated")
        resp = client.put("/atlases/missing", json={"name": "x"})
        assert resp.status_code == 404
        assert calls == []


class TestDeleteAtlas:
    def test_happy_path_publishes(self, client, stub_publisher):
        from smartem_backend.model.database import Atlas

        set_db_row(client, Atlas(uuid="atlas-1", atlas_id="a-1", grid_uuid="grid-1", name="x"))
        calls = stub_publisher("publish_atlas_deleted")

        resp = client.delete("/atlases/atlas-1")
        assert resp.status_code == 204
        assert calls == [{"uuid": "atlas-1"}]

    def test_404_when_not_found(self, client, stub_publisher):
        set_db_row(client, None)
        calls = stub_publisher("publish_atlas_deleted")
        resp = client.delete("/atlases/missing")
        assert resp.status_code == 404
        assert calls == []


class TestGetGridAtlas:
    def test_404_when_no_atlas_for_grid(self, client):
        set_db_row(client, None)
        resp = client.get("/grids/grid-1/atlas")
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Atlas not found for this grid"

    def test_happy_path(self, client):
        from smartem_backend.model.database import Atlas

        set_db_row(client, Atlas(uuid="atlas-1", atlas_id="a-1", grid_uuid="grid-1", name="x"))
        resp = client.get("/grids/grid-1/atlas")
        assert resp.status_code == 200
        assert resp.json()["grid_uuid"] == "grid-1"


class TestCreateGridAtlas:
    def test_happy_path_persists_and_publishes(self, client, stub_publisher):
        calls = stub_publisher("publish_atlas_created")

        resp = client.post("/grids/grid-1/atlas", json=_atlas_payload())
        assert resp.status_code == 201
        body = resp.json()
        assert body["uuid"] == "atlas-1"
        assert body["grid_uuid"] == "grid-1"
        client._db.add.assert_called_once()
        client._db.commit.assert_called_once()
        assert calls == [{"uuid": "atlas-1", "id": "a-1", "grid_uuid": "grid-1"}]

    def test_with_tiles_creates_tiles_and_publishes_each(self, client, stub_publisher):
        atlas_calls = stub_publisher("publish_atlas_created")
        tile_calls = stub_publisher("publish_atlas_tile_created")

        payload = _atlas_payload()
        payload["tiles"] = [
            {"uuid": "tile-1", "atlas_uuid": "atlas-1", "tile_id": "t-1"},
            {"uuid": "tile-2", "atlas_uuid": "atlas-1", "tile_id": "t-2"},
        ]
        resp = client.post("/grids/grid-1/atlas", json=payload)
        assert resp.status_code == 201
        assert len(atlas_calls) == 1
        assert len(tile_calls) == 2
        assert client._db.commit.call_count == 3

    def test_missing_required_returns_422(self, client, stub_publisher):
        calls = stub_publisher("publish_atlas_created")
        resp = client.post("/grids/grid-1/atlas", json={"uuid": "atlas-1"})
        assert resp.status_code == 422
        client._db.add.assert_not_called()
        assert calls == []


class TestGetGridAtlasImage:
    def test_404_when_grid_not_found(self, client):
        set_db_row(client, None)
        resp = client.get("/grids/missing/atlas_image")
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Grid not found"
