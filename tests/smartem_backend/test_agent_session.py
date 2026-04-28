"""TestClient coverage for agent/session endpoints — heartbeat, logs, instructions stream (issue #258)."""

from datetime import datetime

from ._async_db_stub import make_execute_result


class TestAgentHeartbeat:
    def test_happy_path_updates_connection_and_session(self, client):
        from smartem_backend.model.database import AgentConnection, AgentSession

        connection = AgentConnection(
            connection_id="conn-1",
            session_id="sess-1",
            agent_id="agent-1",
            status="active",
        )
        session = AgentSession(session_id="sess-1", agent_id="agent-1")
        results = iter([make_execute_result(connection), make_execute_result(session)])
        client._db.execute.side_effect = lambda *a, **kw: next(results)

        resp = client.post("/agent/agent-1/session/sess-1/heartbeat")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "success"
        assert body["agent_id"] == "agent-1"
        assert body["connection_id"] == "conn-1"
        assert client._db.commit.await_count == 2

    def test_404_when_no_active_connection(self, client):
        client._db.execute.return_value = make_execute_result(None)
        resp = client.post("/agent/agent-1/session/sess-1/heartbeat")
        assert resp.status_code == 404
        assert "active connection" in resp.json()["detail"].lower()


class TestIngestAgentLogs:
    @staticmethod
    def _log_batch(count: int = 2) -> dict:
        now = datetime.now().isoformat()
        return {
            "logs": [
                {"timestamp": now, "level": "INFO", "logger_name": "test", "message": f"msg-{i}"} for i in range(count)
            ]
        }

    def test_happy_path_persists_each_log(self, client):
        from smartem_backend.model.database import AgentSession

        client._db.execute.return_value = make_execute_result(AgentSession(session_id="sess-1", agent_id="agent-1"))

        resp = client.post("/agent/agent-1/session/sess-1/logs", json=self._log_batch(3))
        assert resp.status_code == 200
        assert resp.json() == {"stored": 3}
        assert client._db.add.call_count == 3
        client._db.commit.assert_called_once()

    def test_404_when_session_not_found(self, client):
        client._db.execute.return_value = make_execute_result(None)
        resp = client.post("/agent/agent-1/session/sess-1/logs", json=self._log_batch())
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Session not found"

    def test_403_when_session_belongs_to_other_agent(self, client):
        from smartem_backend.model.database import AgentSession

        client._db.execute.return_value = make_execute_result(AgentSession(session_id="sess-1", agent_id="other-agent"))

        resp = client.post("/agent/agent-1/session/sess-1/logs", json=self._log_batch())
        assert resp.status_code == 403
        assert "agent" in resp.json()["detail"].lower()

    def test_caps_logs_to_500(self, client):
        from smartem_backend.model.database import AgentSession

        client._db.execute.return_value = make_execute_result(AgentSession(session_id="sess-1", agent_id="agent-1"))

        big_batch = self._log_batch(600)
        resp = client.post("/agent/agent-1/session/sess-1/logs", json=big_batch)
        assert resp.status_code == 200
        assert resp.json() == {"stored": 500}
        assert client._db.add.call_count == 500


class TestStreamInstructionsValidation:
    def test_session_not_found_emits_error_event(self, client):
        client._db.execute.return_value = make_execute_result(None)
        with client.stream("GET", "/agent/agent-1/session/missing/instructions/stream") as resp:
            assert resp.status_code == 200
            content = b"".join(resp.iter_bytes()).decode()
        assert "session_validation_failed" in content

    def test_session_belongs_to_other_agent_emits_error_event(self, client):
        from smartem_backend.model.database import AgentSession

        client._db.execute.return_value = make_execute_result(
            AgentSession(session_id="sess-1", agent_id="other-agent", status="active")
        )

        with client.stream("GET", "/agent/agent-1/session/sess-1/instructions/stream") as resp:
            assert resp.status_code == 200
            content = b"".join(resp.iter_bytes()).decode()
        assert "session_validation_failed" in content

    def test_inactive_session_emits_error_event(self, client):
        from smartem_backend.model.database import AgentSession

        client._db.execute.return_value = make_execute_result(
            AgentSession(session_id="sess-1", agent_id="agent-1", status="ended")
        )

        with client.stream("GET", "/agent/agent-1/session/sess-1/instructions/stream") as resp:
            assert resp.status_code == 200
            content = b"".join(resp.iter_bytes()).decode()
        assert "session_validation_failed" in content
