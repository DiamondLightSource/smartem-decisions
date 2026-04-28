"""TestClient coverage for the /micrographs and /foilholes/{uuid}/micrographs endpoints (issue #258)."""

from .conftest import set_db_row


def _micrograph_payload(uuid: str = "mic-1", **overrides) -> dict:
    base = {
        "uuid": uuid,
        "micrograph_id": "mic-id-1",
        "foilhole_id": "fh-id-1",
    }
    base.update(overrides)
    return base


class TestListMicrographs:
    def test_returns_empty_list(self, client):
        set_db_row(client, [])
        resp = client.get("/micrographs")
        assert resp.status_code == 200
        assert resp.json() == []


class TestGetMicrograph:
    def test_404_when_not_found(self, client):
        set_db_row(client, None)
        resp = client.get("/micrographs/missing")
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Micrograph not found"

    def test_happy_path(self, client):
        from smartem_backend.model.database import Micrograph

        set_db_row(
            client, Micrograph(uuid="mic-1", foilhole_uuid="fh-1", foilhole_id="fh-id-1", micrograph_id="mic-id-1")
        )
        resp = client.get("/micrographs/mic-1")
        assert resp.status_code == 200
        assert resp.json()["uuid"] == "mic-1"


class TestUpdateMicrograph:
    def test_happy_path_publishes(self, client, stub_publisher):
        from smartem_backend.model.database import Micrograph

        set_db_row(
            client, Micrograph(uuid="mic-1", foilhole_uuid="fh-1", foilhole_id="fh-id-1", micrograph_id="mic-id-1")
        )
        calls = stub_publisher("publish_micrograph_updated")

        resp = client.put("/micrographs/mic-1", json={"defocus": 1.5})
        assert resp.status_code == 200
        client._db.commit.assert_called_once()
        assert len(calls) == 1
        assert calls[0]["uuid"] == "mic-1"
        assert calls[0]["foilhole_uuid"] == "fh-1"
        assert calls[0]["micrograph_id"] == "mic-id-1"

    def test_404_when_not_found(self, client, stub_publisher):
        set_db_row(client, None)
        calls = stub_publisher("publish_micrograph_updated")
        resp = client.put("/micrographs/missing", json={"defocus": 1.0})
        assert resp.status_code == 404
        assert calls == []


class TestDeleteMicrograph:
    def test_happy_path_publishes(self, client, stub_publisher):
        from smartem_backend.model.database import Micrograph

        set_db_row(
            client, Micrograph(uuid="mic-1", foilhole_uuid="fh-1", foilhole_id="fh-id-1", micrograph_id="mic-id-1")
        )
        calls = stub_publisher("publish_micrograph_deleted")

        resp = client.delete("/micrographs/mic-1")
        assert resp.status_code == 204
        assert calls == [{"uuid": "mic-1"}]

    def test_404_when_not_found(self, client, stub_publisher):
        set_db_row(client, None)
        calls = stub_publisher("publish_micrograph_deleted")
        resp = client.delete("/micrographs/missing")
        assert resp.status_code == 404
        assert calls == []


class TestListFoilHoleMicrographs:
    def test_returns_empty_list(self, client):
        set_db_row(client, [])
        resp = client.get("/foilholes/fh-1/micrographs")
        assert resp.status_code == 200
        assert resp.json() == []


class TestCreateFoilHoleMicrograph:
    def test_happy_path_publishes(self, client, stub_publisher):
        calls = stub_publisher("publish_micrograph_created")

        resp = client.post("/foilholes/fh-1/micrographs", json=_micrograph_payload())
        assert resp.status_code == 201
        body = resp.json()
        assert body["uuid"] == "mic-1"
        assert body["foilhole_uuid"] == "fh-1"
        client._db.add.assert_called_once()
        client._db.commit.assert_called_once()
        assert len(calls) == 1
        assert calls[0]["uuid"] == "mic-1"
        assert calls[0]["foilhole_uuid"] == "fh-1"
        assert calls[0]["foilhole_id"] == "fh-id-1"

    def test_missing_uuid_returns_422(self, client, stub_publisher):
        calls = stub_publisher("publish_micrograph_created")
        resp = client.post("/foilholes/fh-1/micrographs", json={"foilhole_id": "fh-id-1"})
        assert resp.status_code == 422
        client._db.add.assert_not_called()
        assert calls == []

    def test_path_foilhole_uuid_wins_over_body(self, client, stub_publisher):
        calls = stub_publisher("publish_micrograph_created")
        payload = _micrograph_payload(foilhole_uuid="other-fh")

        resp = client.post("/foilholes/fh-1/micrographs", json=payload)
        assert resp.status_code == 201
        assert resp.json()["foilhole_uuid"] == "fh-1"
        assert calls[0]["foilhole_uuid"] == "fh-1"
