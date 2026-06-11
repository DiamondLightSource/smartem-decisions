"""TestClient coverage for the /gridsquares and /grids/{uuid}/gridsquares endpoints (issue #258)."""

from .conftest import set_db_row


def _gs_payload(uuid: str = "gs-1", grid_uuid: str = "grid-1", **overrides) -> dict:
    base = {
        "uuid": uuid,
        "gridsquare_id": "gs-id-1",
        "grid_uuid": grid_uuid,
    }
    base.update(overrides)
    return base


class TestListGridSquares:
    def test_returns_empty_list(self, client):
        set_db_row(client, [])
        resp = client.get("/gridsquares")
        assert resp.status_code == 200
        assert resp.json() == []


class TestGetGridSquare:
    def test_404_when_not_found(self, client):
        set_db_row(client, None)
        resp = client.get("/gridsquares/missing")
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Grid Square not found"

    def test_happy_path(self, client):
        from smartem_backend.model.database import GridSquare

        set_db_row(client, GridSquare(uuid="gs-1", grid_uuid="grid-1", gridsquare_id="gs-id-1"))
        resp = client.get("/gridsquares/gs-1")
        assert resp.status_code == 200
        assert resp.json()["uuid"] == "gs-1"


class TestUpdateGridSquare:
    def test_happy_path_publishes(self, client, stub_publisher):
        from smartem_backend.model.database import GridSquare
        from smartem_backend.model.entity_status import GridSquareStatus

        set_db_row(
            client, GridSquare(uuid="gs-1", grid_uuid="grid-1", gridsquare_id="gs-id-1", status=GridSquareStatus.NONE)
        )
        calls = stub_publisher("publish_gridsquare_updated")

        resp = client.put("/gridsquares/gs-1", json={"defocus": 1.5})
        assert resp.status_code == 200
        client._db.commit.assert_called_once()
        assert calls == [{"uuid": "gs-1", "grid_uuid": "grid-1", "gridsquare_id": "gs-id-1"}]

    def test_lowmag_publishes_lowmag_event(self, client, stub_publisher):
        from smartem_backend.model.database import GridSquare
        from smartem_backend.model.entity_status import GridSquareStatus

        set_db_row(
            client, GridSquare(uuid="gs-1", grid_uuid="grid-1", gridsquare_id="gs-id-1", status=GridSquareStatus.NONE)
        )
        regular = stub_publisher("publish_gridsquare_updated")
        lowmag = stub_publisher("publish_gridsquare_lowmag_updated")

        resp = client.put("/gridsquares/gs-1", json={"lowmag": True, "defocus": 1.0})
        assert resp.status_code == 200
        assert regular == []
        assert lowmag == [{"uuid": "gs-1", "grid_uuid": "grid-1", "gridsquare_id": "gs-id-1"}]

    def test_404_when_not_found(self, client, stub_publisher):
        set_db_row(client, None)
        calls = stub_publisher("publish_gridsquare_updated")
        resp = client.put("/gridsquares/missing", json={"defocus": 1.0})
        assert resp.status_code == 404
        assert calls == []


class TestDeleteGridSquare:
    def test_happy_path_publishes(self, client, stub_publisher):
        from smartem_backend.model.database import GridSquare

        set_db_row(client, GridSquare(uuid="gs-1", grid_uuid="grid-1", gridsquare_id="gs-id-1"))
        calls = stub_publisher("publish_gridsquare_deleted")

        resp = client.delete("/gridsquares/gs-1")
        assert resp.status_code == 204
        assert calls == [{"uuid": "gs-1"}]

    def test_404_when_not_found(self, client, stub_publisher):
        set_db_row(client, None)
        calls = stub_publisher("publish_gridsquare_deleted")
        resp = client.delete("/gridsquares/missing")
        assert resp.status_code == 404
        assert calls == []


class TestListGridGridSquares:
    def test_returns_empty_list(self, client):
        set_db_row(client, [])
        resp = client.get("/grids/grid-1/gridsquares")
        assert resp.status_code == 200
        assert resp.json() == []


class TestCreateGridGridSquare:
    def test_happy_path_publishes_regular(self, client, stub_publisher):
        regular = stub_publisher("publish_gridsquare_created")
        lowmag = stub_publisher("publish_gridsquare_lowmag_created")

        resp = client.post("/grids/grid-1/gridsquares", json=_gs_payload())
        assert resp.status_code == 201
        body = resp.json()
        assert body["uuid"] == "gs-1"
        assert body["grid_uuid"] == "grid-1"
        client._db.add.assert_called_once()
        client._db.commit.assert_called_once()
        assert regular == [{"uuid": "gs-1", "grid_uuid": "grid-1", "gridsquare_id": "gs-id-1"}]
        assert lowmag == []

    def test_lowmag_publishes_lowmag_event(self, client, stub_publisher):
        regular = stub_publisher("publish_gridsquare_created")
        lowmag = stub_publisher("publish_gridsquare_lowmag_created")

        resp = client.post("/grids/grid-1/gridsquares", json=_gs_payload(lowmag=True))
        assert resp.status_code == 201
        assert regular == []
        assert lowmag == [{"uuid": "gs-1", "grid_uuid": "grid-1", "gridsquare_id": "gs-id-1"}]

    def test_missing_uuid_returns_422(self, client, stub_publisher):
        calls = stub_publisher("publish_gridsquare_created")
        resp = client.post("/grids/grid-1/gridsquares", json={"gridsquare_id": "gs-id-1"})
        assert resp.status_code == 422
        client._db.add.assert_not_called()
        assert calls == []

    def test_path_grid_uuid_wins_over_body(self, client, stub_publisher):
        calls = stub_publisher("publish_gridsquare_created")
        payload = _gs_payload(grid_uuid="other-grid")

        resp = client.post("/grids/grid-1/gridsquares", json=payload)
        assert resp.status_code == 201
        assert resp.json()["grid_uuid"] == "grid-1"
        assert calls[0]["grid_uuid"] == "grid-1"


class TestGridSquareRegistered:
    def test_happy_path_publishes(self, client, stub_publisher):
        from smartem_backend.model.database import GridSquare

        set_db_row(client, GridSquare(uuid="gs-1", grid_uuid="grid-1", gridsquare_id="gs-id-1"))
        calls = stub_publisher("publish_gridsquare_registered")

        resp = client.post("/gridsquares/gs-1/registered")
        assert resp.status_code == 200
        assert resp.json() is True
        assert len(calls) == 1
        client._db.commit.assert_called_once()

    def test_404_when_gridsquare_missing(self, client, stub_publisher):
        set_db_row(client, None)
        calls = stub_publisher("publish_gridsquare_registered")
        resp = client.post("/gridsquares/missing/registered")
        assert resp.status_code == 404
        assert calls == []


class TestGetGridSquareImage:
    def test_404_when_gridsquare_not_found(self, client):
        set_db_row(client, None)
        resp = client.get("/gridsquares/missing/gridsquare_image")
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Grid square not found"

    def test_404_when_image_path_missing(self, client):
        from smartem_backend.model.database import GridSquare

        set_db_row(client, GridSquare(uuid="gs-1", grid_uuid="grid-1", gridsquare_id="gs-id-1", image_path=None))
        resp = client.get("/gridsquares/gs-1/gridsquare_image")
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Grid square image unknown"

    def test_renders_png_and_caches(self, client, tmp_path, monkeypatch):
        import numpy as np
        import tifffile

        from smartem_backend import api_server
        from smartem_backend.model.database import GridSquare

        cache_dir = tmp_path / "cache"
        monkeypatch.setattr(api_server, "IMAGE_CACHE_DIR", cache_dir)
        source = tmp_path / "square.tiff"
        tifffile.imwrite(source, np.arange(16, dtype=np.uint16).reshape(4, 4))

        set_db_row(
            client,
            GridSquare(uuid="gs-1", grid_uuid="grid-1", gridsquare_id="gs-id-1", image_path=str(source)),
        )
        resp = client.get("/gridsquares/gs-1/gridsquare_image")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "image/png"
        assert resp.content[:8] == b"\x89PNG\r\n\x1a\n"
        cached = list(cache_dir.glob("*.png"))
        assert len(cached) == 1

        resp2 = client.get("/gridsquares/gs-1/gridsquare_image")
        assert resp2.status_code == 200
        assert list(cache_dir.glob("*.png")) == cached
