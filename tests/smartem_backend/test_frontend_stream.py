from datetime import datetime

from smartem_backend.model.frontend_sse_event import (
    AgentLogBatchRequest,
    AgentLogData,
    AgentStatusData,
    FrontendEventType,
    ProcessingMetricData,
)


class TestFrontendEventModels:
    def test_event_type_values(self):
        assert FrontendEventType.AGENT_STATUS.value == "agent.status"
        assert FrontendEventType.ACQUISITION_PROGRESS.value == "acquisition.progress"
        assert FrontendEventType.INSTRUCTION_LIFECYCLE.value == "instruction.lifecycle"
        assert FrontendEventType.PROCESSING_METRIC.value == "processing.metric"
        assert FrontendEventType.AGENT_LOG.value == "agent.log"
        assert FrontendEventType.HEARTBEAT.value == "heartbeat"

    def test_agent_status_data(self):
        data = AgentStatusData(
            agent_id="agent-1",
            status="online",
            session_id="sess-1",
            acquisition_uuid="acq-1",
            last_heartbeat_at="2026-03-27T12:00:00",
            connection_count=1,
        )
        assert data.agent_id == "agent-1"
        assert data.status == "online"

    def test_agent_status_data_minimal(self):
        data = AgentStatusData(agent_id="agent-1", status="offline")
        assert data.session_id is None
        assert data.connection_count == 0

    def test_processing_metric_data(self):
        data = ProcessingMetricData(
            micrograph_uuid="micro-1",
            total_motion=1.5,
            ctf_max_resolution_estimate=3.2,
        )
        assert data.micrograph_uuid == "micro-1"
        assert data.average_motion is None

    def test_agent_log_data(self):
        data = AgentLogData(
            agent_id="agent-1",
            session_id="sess-1",
            timestamp="2026-03-27T12:00:00",
            level="INFO",
            logger_name="smartem_agent.fs_watcher",
            message="Batch processed",
        )
        dumped = data.model_dump()
        assert dumped["level"] == "INFO"

    def test_log_batch_request(self):
        req = AgentLogBatchRequest(
            logs=[
                {
                    "timestamp": datetime(2026, 3, 27, 12, 0, 0),
                    "level": "INFO",
                    "logger_name": "test",
                    "message": "hello",
                },
                {
                    "timestamp": datetime(2026, 3, 27, 12, 0, 1),
                    "level": "ERROR",
                    "logger_name": "test",
                    "message": "oops",
                },
            ]
        )
        assert len(req.logs) == 2
        assert req.logs[0].level == "INFO"
        assert req.logs[1].level == "ERROR"
