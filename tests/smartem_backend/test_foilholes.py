"""TestClient coverage for the /foilholes and /gridsquares/{uuid}/foilholes endpoints (issue #258)."""

from .conftest import set_db_row


def _foilhole_payload(uuid: str = "fh-1", gridsquare_uuid: str = "gs-1", **overrides) -> dict:
    base = {
        "uuid": uuid,
        "foilhole_id": "fh-id-1",
        "gridsquare_uuid": gridsquare_uuid,
        "gridsquare_id": "gs-id-1",
    }
    base.update(overrides)
    return base


class TestListFoilHoles:
    def test_returns_empty_list(self, client):
        set_db_row(client, [])
        resp = client.get("/foilholes")
        assert resp.status_code == 200
        assert resp.json() == []


class TestGetFoilHole:
    def test_404_when_not_found(self, client):
        set_db_row(client, None)
        resp = client.get("/foilholes/missing")
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Foil Hole not found"

    def test_happy_path(self, client):
        from smartem_backend.model.database import FoilHole

        set_db_row(
            client, FoilHole(uuid="fh-1", foilhole_id="fh-id-1", gridsquare_uuid="gs-1", gridsquare_id="gs-id-1")
        )
        resp = client.get("/foilholes/fh-1")
        assert resp.status_code == 200
        assert resp.json()["uuid"] == "fh-1"


class TestUpdateFoilHole:
    def test_happy_path_publishes(self, client, stub_publisher):
        from smartem_backend.model.database import FoilHole

        set_db_row(
            client, FoilHole(uuid="fh-1", foilhole_id="fh-id-1", gridsquare_uuid="gs-1", gridsquare_id="gs-id-1")
        )
        calls = stub_publisher("publish_foilhole_updated")

        resp = client.put("/foilholes/fh-1", json={"quality": 0.85})
        assert resp.status_code == 200
        client._db.commit.assert_called_once()
        assert calls == [
            {"uuid": "fh-1", "foilhole_id": "fh-id-1", "gridsquare_uuid": "gs-1", "gridsquare_id": "gs-id-1"}
        ]

    def test_404_when_not_found(self, client, stub_publisher):
        set_db_row(client, None)
        calls = stub_publisher("publish_foilhole_updated")
        resp = client.put("/foilholes/missing", json={"quality": 0.5})
        assert resp.status_code == 404
        assert calls == []


class TestDeleteFoilHole:
    def test_happy_path_publishes(self, client, stub_publisher):
        from smartem_backend.model.database import FoilHole

        set_db_row(
            client, FoilHole(uuid="fh-1", foilhole_id="fh-id-1", gridsquare_uuid="gs-1", gridsquare_id="gs-id-1")
        )
        calls = stub_publisher("publish_foilhole_deleted")

        resp = client.delete("/foilholes/fh-1")
        assert resp.status_code == 204
        assert calls == [{"uuid": "fh-1"}]

    def test_404_when_not_found(self, client, stub_publisher):
        set_db_row(client, None)
        calls = stub_publisher("publish_foilhole_deleted")
        resp = client.delete("/foilholes/missing")
        assert resp.status_code == 404
        assert calls == []


class TestListGridSquareFoilHoles:
    def test_returns_empty_list(self, client):
        set_db_row(client, [])
        resp = client.get("/gridsquares/gs-1/foilholes")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_on_square_only_query_param_accepted(self, client):
        set_db_row(client, [])
        resp = client.get("/gridsquares/gs-1/foilholes?on_square_only=true")
        assert resp.status_code == 200
        assert resp.json() == []


class TestCreateGridSquareFoilHoles:
    def test_happy_path_publishes_each(self, client, stub_publisher):
        calls = stub_publisher("publish_foilhole_created")

        resp = client.post(
            "/gridsquares/gs-1/foilholes",
            json=[_foilhole_payload("fh-1"), _foilhole_payload("fh-2")],
        )
        assert resp.status_code == 201
        body = resp.json()
        assert len(body) == 2
        assert {item["uuid"] for item in body} == {"fh-1", "fh-2"}
        client._db.commit.assert_called_once()
        assert len(calls) == 2

    def test_empty_list_returns_201_with_no_publishes(self, client, stub_publisher):
        calls = stub_publisher("publish_foilhole_created")
        resp = client.post("/gridsquares/gs-1/foilholes", json=[])
        assert resp.status_code == 201
        assert resp.json() == []
        assert calls == []

    def test_missing_required_fields_returns_422(self, client, stub_publisher):
        calls = stub_publisher("publish_foilhole_created")
        resp = client.post("/gridsquares/gs-1/foilholes", json=[{"uuid": "fh-1"}])
        assert resp.status_code == 422
        assert calls == []
