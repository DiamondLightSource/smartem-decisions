"""TestClient coverage for the /debug/* session and connection endpoints (issue #258)."""

from unittest.mock import MagicMock

import pytest

from smartem_backend import api_server

from ._async_db_stub import make_execute_result
from .conftest import set_db_row


@pytest.fixture
def stub_connection_manager(monkeypatch):
    """Replace api_server.connection_manager with a MagicMock so debug endpoints
    that delegate to it (create_session, close_session, get_connection_stats) can
    be tested without a real manager."""
    fake = MagicMock()
    monkeypatch.setattr(api_server, "connection_manager", fake)
    return fake


class TestGetActiveConnections:
    def test_returns_empty(self, client):
        set_db_row(client, [])
        resp = client.get("/debug/agent-connections")
        assert resp.status_code == 200
        assert resp.json() == {"active_connections": [], "total_count": 0}


class TestGetActiveSessions:
    def test_returns_empty(self, client):
        set_db_row(client, [])
        resp = client.get("/debug/sessions")
        assert resp.status_code == 200
        assert resp.json() == {"active_sessions": [], "total_count": 0}


class TestGetConnectionStats:
    def test_delegates_to_connection_manager(self, client, stub_connection_manager):
        stub_connection_manager.get_connection_stats.return_value = {"active": 3, "total": 5}
        resp = client.get("/debug/connection-stats")
        assert resp.status_code == 200
        assert resp.json() == {"active": 3, "total": 5}
        stub_connection_manager.get_connection_stats.assert_called_once()


class TestCreateManagedSession:
    def test_happy_path_uses_connection_manager(self, client, stub_connection_manager):
        stub_connection_manager.create_session.return_value = "sess-xyz"
        resp = client.post("/debug/sessions/create-managed", json={"agent_id": "agent-1"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["session_id"] == "sess-xyz"
        assert body["status"] == "created"
        stub_connection_manager.create_session.assert_called_once()

    def test_500_when_connection_manager_raises(self, client, stub_connection_manager):
        stub_connection_manager.create_session.side_effect = RuntimeError("boom")
        resp = client.post("/debug/sessions/create-managed", json={"agent_id": "agent-1"})
        assert resp.status_code == 500
        assert "Failed to create session" in resp.json()["detail"]


class TestCloseManagedSession:
    def test_happy_path(self, client, stub_connection_manager):
        stub_connection_manager.close_session.return_value = True
        resp = client.delete("/debug/sessions/sess-1/close")
        assert resp.status_code == 200
        body = resp.json()
        assert body["session_id"] == "sess-1"
        assert body["status"] == "closed"
        stub_connection_manager.close_session.assert_called_once_with("sess-1")

    def test_500_when_close_fails(self, client, stub_connection_manager):
        stub_connection_manager.close_session.return_value = False
        resp = client.delete("/debug/sessions/sess-1/close")
        assert resp.status_code == 500
        assert resp.json()["detail"] == "Failed to close session"


class TestCreateTestSession:
    def test_happy_path_persists(self, client):
        client._db.execute.return_value = make_execute_result(None)  # acquisition_uuid omitted, no lookup
        resp = client.post("/debug/sessions/create", json={"session_id": "sess-1", "agent_id": "agent-1"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["session_id"] == "sess-1"
        assert body["status"] == "created"
        client._db.add.assert_called_once()
        client._db.commit.assert_called_once()

    def test_404_when_acquisition_not_found(self, client):
        client._db.execute.return_value = make_execute_result(None)
        resp = client.post(
            "/debug/sessions/create",
            json={"session_id": "sess-1", "agent_id": "agent-1", "acquisition_uuid": "missing"},
        )
        assert resp.status_code == 404
        assert "missing" in resp.json()["detail"]
        client._db.add.assert_not_called()


class TestCreateTestInstruction:
    def test_happy_path(self, client):
        from smartem_backend.model.database import AgentSession

        client._db.execute.return_value = make_execute_result(AgentSession(session_id="sess-1", agent_id="agent-1"))
        resp = client.post(
            "/debug/session/sess-1/create-instruction",
            json={"instruction_type": "test.cmd", "payload": {"x": 1}},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "instruction_id" in body
        assert body["status"] == "created"
        client._db.add.assert_called_once()

    def test_404_when_session_missing(self, client):
        client._db.execute.return_value = make_execute_result(None)
        resp = client.post("/debug/session/missing/create-instruction", json={"instruction_type": "test.cmd"})
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Session not found"


class TestGetSessionInstructions:
    def test_returns_empty_list(self, client):
        set_db_row(client, [])
        resp = client.get("/debug/session/sess-1/instructions")
        assert resp.status_code == 200
        body = resp.json()
        assert body["instructions"] == []
        assert body["total_instructions"] == 0
        assert body["session_id"] == "sess-1"
