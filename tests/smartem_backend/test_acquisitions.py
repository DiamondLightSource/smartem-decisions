"""TestClient coverage for the /acquisitions endpoints (issue #258)."""

from .conftest import set_db_row


def _payload(uuid: str = "acq-1", **overrides) -> dict:
    base = {
        "uuid": uuid,
        "name": "test-acquisition",
        "instrument_id": "inst-1",
        "computer_name": "test-host",
    }
    base.update(overrides)
    return base


class TestListAcquisitions:
    def test_returns_empty_list_when_no_rows(self, client):
        set_db_row(client, [])
        resp = client.get("/acquisitions")
        assert resp.status_code == 200
        assert resp.json() == []


class TestCreateAcquisition:
    def test_happy_path_persists_and_publishes(self, client, stub_publisher):
        calls = stub_publisher("publish_acquisition_created")
        resp = client.post("/acquisitions", json=_payload())

        assert resp.status_code == 201
        body = resp.json()
        assert body["uuid"] == "acq-1"
        assert body["name"] == "test-acquisition"
        assert body["status"] == "started"

        client._db.add.assert_called_once()
        client._db.commit.assert_called_once()
        assert len(calls) == 1
        assert calls[0]["uuid"] == "acq-1"
        assert calls[0]["status"] == "started"

    def test_missing_uuid_returns_422(self, client, stub_publisher):
        calls = stub_publisher("publish_acquisition_created")
        resp = client.post("/acquisitions", json={"name": "no-uuid"})
        assert resp.status_code == 422
        client._db.add.assert_not_called()
        assert calls == []

    def test_publish_failure_still_returns_201(self, client, stub_publisher):
        stub_publisher("publish_acquisition_created", return_value=False)
        resp = client.post("/acquisitions", json=_payload())
        assert resp.status_code == 201


class TestGetAcquisition:
    def test_404_when_not_found(self, client):
        set_db_row(client, None)
        resp = client.get("/acquisitions/missing")
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Acquisition not found"


class TestUpdateAcquisition:
    def test_happy_path_persists_and_publishes(self, client, stub_publisher):
        from smartem_backend.model.database import Acquisition
        from smartem_backend.model.entity_status import AcquisitionStatus

        existing = Acquisition(
            uuid="acq-1",
            id=42,
            name="old",
            status=AcquisitionStatus.STARTED,
            instrument_id="inst-1",
            computer_name="test-host",
        )
        set_db_row(client, existing)
        calls = stub_publisher("publish_acquisition_updated")

        resp = client.put("/acquisitions/acq-1", json={"name": "new"})

        assert resp.status_code == 200
        client._db.commit.assert_called_once()
        assert len(calls) == 1
        assert calls[0]["uuid"] == "acq-1"
        assert calls[0]["id"] == 42

    def test_404_when_not_found(self, client, stub_publisher):
        set_db_row(client, None)
        calls = stub_publisher("publish_acquisition_updated")
        resp = client.put("/acquisitions/missing", json={"name": "x"})
        assert resp.status_code == 404
        client._db.commit.assert_not_called()
        assert calls == []


class TestDeleteAcquisition:
    def test_happy_path_returns_204_and_publishes(self, client, stub_publisher):
        from smartem_backend.model.database import Acquisition

        existing = Acquisition(uuid="acq-1", name="to-delete")
        set_db_row(client, existing)
        calls = stub_publisher("publish_acquisition_deleted")

        resp = client.delete("/acquisitions/acq-1")

        assert resp.status_code == 204
        client._db.delete.assert_awaited_once()
        client._db.commit.assert_called_once()
        assert calls == [{"uuid": "acq-1"}]

    def test_404_when_not_found(self, client, stub_publisher):
        set_db_row(client, None)
        calls = stub_publisher("publish_acquisition_deleted")
        resp = client.delete("/acquisitions/missing")
        assert resp.status_code == 404
        client._db.delete.assert_not_called()
        assert calls == []
