"""TestClient coverage for the /atlas-tiles and /atlases/{uuid}/tiles endpoints (issue #258)."""

from .conftest import set_db_row


def _tile_payload(uuid: str = "tile-1", atlas_uuid: str = "atlas-1", **overrides) -> dict:
    base = {
        "uuid": uuid,
        "atlas_uuid": atlas_uuid,
        "tile_id": "t-1",
        "position_x": 0,
        "position_y": 0,
        "size_x": 100,
        "size_y": 100,
    }
    base.update(overrides)
    return base


class TestListAtlasTiles:
    def test_returns_empty_list(self, client):
        set_db_row(client, [])
        resp = client.get("/atlas-tiles")
        assert resp.status_code == 200
        assert resp.json() == []


class TestGetAtlasTile:
    def test_404_when_not_found(self, client):
        set_db_row(client, None)
        resp = client.get("/atlas-tiles/missing")
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Atlas tile not found"

    def test_happy_path(self, client):
        from smartem_backend.model.database import AtlasTile

        set_db_row(client, AtlasTile(uuid="tile-1", atlas_uuid="atlas-1", tile_id="t-1"))
        resp = client.get("/atlas-tiles/tile-1")
        assert resp.status_code == 200
        assert resp.json()["uuid"] == "tile-1"


class TestUpdateAtlasTile:
    def test_happy_path_publishes(self, client, stub_publisher):
        from smartem_backend.model.database import AtlasTile

        set_db_row(client, AtlasTile(uuid="tile-1", atlas_uuid="atlas-1", tile_id="t-1"))
        calls = stub_publisher("publish_atlas_tile_updated")

        resp = client.put("/atlas-tiles/tile-1", json={"position_x": 42})
        assert resp.status_code == 200
        client._db.commit.assert_called_once()
        assert calls == [{"uuid": "tile-1", "id": "t-1", "atlas_uuid": "atlas-1"}]

    def test_404_when_not_found(self, client, stub_publisher):
        set_db_row(client, None)
        calls = stub_publisher("publish_atlas_tile_updated")
        resp = client.put("/atlas-tiles/missing", json={"position_x": 1})
        assert resp.status_code == 404
        assert calls == []


class TestDeleteAtlasTile:
    def test_happy_path_publishes(self, client, stub_publisher):
        from smartem_backend.model.database import AtlasTile

        set_db_row(client, AtlasTile(uuid="tile-1", atlas_uuid="atlas-1"))
        calls = stub_publisher("publish_atlas_tile_deleted")

        resp = client.delete("/atlas-tiles/tile-1")
        assert resp.status_code == 204
        assert calls == [{"uuid": "tile-1"}]

    def test_404_when_not_found(self, client, stub_publisher):
        set_db_row(client, None)
        calls = stub_publisher("publish_atlas_tile_deleted")
        resp = client.delete("/atlas-tiles/missing")
        assert resp.status_code == 404
        assert calls == []


class TestListAtlasTilesByAtlas:
    def test_returns_empty_list(self, client):
        set_db_row(client, [])
        resp = client.get("/atlases/atlas-1/tiles")
        assert resp.status_code == 200
        assert resp.json() == []


class TestCreateAtlasTileForAtlas:
    def test_happy_path_persists_and_publishes(self, client, stub_publisher):
        calls = stub_publisher("publish_atlas_tile_created")

        resp = client.post("/atlases/atlas-1/tiles", json=_tile_payload())
        assert resp.status_code == 201
        body = resp.json()
        assert body["uuid"] == "tile-1"
        assert body["atlas_uuid"] == "atlas-1"
        client._db.add.assert_called_once()
        client._db.commit.assert_called_once()
        assert calls == [{"uuid": "tile-1", "id": "t-1", "atlas_uuid": "atlas-1"}]

    def test_missing_uuid_returns_422(self, client, stub_publisher):
        calls = stub_publisher("publish_atlas_tile_created")
        resp = client.post("/atlases/atlas-1/tiles", json={"tile_id": "t-1"})
        assert resp.status_code == 422
        client._db.add.assert_not_called()
        assert calls == []
