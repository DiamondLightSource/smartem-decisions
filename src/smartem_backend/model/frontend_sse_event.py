from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class FrontendEventType(str, Enum):
    AGENT_STATUS = "agent.status"
    ACQUISITION_PROGRESS = "acquisition.progress"
    INSTRUCTION_LIFECYCLE = "instruction.lifecycle"
    PROCESSING_METRIC = "processing.metric"
    AGENT_LOG = "agent.log"
    HEARTBEAT = "heartbeat"


class AgentStatusData(BaseModel):
    agent_id: str
    status: str
    session_id: str | None = None
    acquisition_uuid: str | None = None
    last_heartbeat_at: str | None = None
    connection_count: int = 0


class AcquisitionProgressData(BaseModel):
    acquisition_uuid: str
    grid_count: int = 0
    gridsquare_count: int = 0
    foilhole_count: int = 0
    micrograph_count: int = 0
    status: str = ""


class InstructionLifecycleData(BaseModel):
    instruction_id: str
    agent_id: str
    session_id: str
    instruction_type: str
    status: str
    created_at: str
    sent_at: str | None = None
    acknowledged_at: str | None = None
    ack_status: str | None = None


class ProcessingMetricData(BaseModel):
    micrograph_uuid: str
    foilhole_uuid: str | None = None
    total_motion: float | None = None
    average_motion: float | None = None
    ctf_max_resolution_estimate: float | None = None
    number_of_particles_picked: int | None = None
    number_of_particles_selected: int | None = None


class AgentLogData(BaseModel):
    agent_id: str
    session_id: str
    timestamp: str
    level: str
    logger_name: str
    message: str


class AgentLogEntry(BaseModel):
    timestamp: datetime
    level: str
    logger_name: str
    message: str


class AgentLogBatchRequest(BaseModel):
    logs: list[AgentLogEntry]


class AgentLogBatchResponse(BaseModel):
    stored: int
