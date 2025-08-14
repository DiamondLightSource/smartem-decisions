"""Athena API request models."""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel


# Enums
class AlgorithmResultType(str, Enum):
    """Types of algorithm results."""

    MOTIONCORRECTION = "motioncorrection"
    CTF = "ctf"
    GRIDSQUARE = "gridsquare"
    MICROGRAPH = "micrograph"
    ATLAS = "atlas"


class EngineState(str, Enum):
    """Engine states."""

    UNKNOWN = "unknown"
    IDLE = "idle"
    RUNNING = "running"


class AreaType(str, Enum):
    """Types of areas."""

    GRIDSQUARE = "gridsquare"
    FOILHOLE = "foilhole"
    ATLAS = "atlas"
    PARTICLE = "particle"


class AcquisitionState(str, Enum):
    """Acquisition states."""

    UNKNOWN = "unknown"
    IGNORE = "ignore"
    QUEUED = "queued"
    STARTED = "started"
    COMPLETED = "completed"
    SKIPPED = "skipped"


class DecisionType(str, Enum):
    """Types of decisions."""

    INCLUDE = "include"
    FOCUS = "focus"
    STAGE_WAITING_TIME = "stageWaitingTime"
    ACQUISITION_ORDER = "acquisitionOrder"
    FOIL_HOLE_SELECTION = "foilHoleSelection"
    GRID_SQUARE_SELECTION = "gridSquareSelection"
    ICE_THICKNESS_FOIL_HOLE_PREDICTION = "iceThicknessFoilHolePrediction"
    AUTOMATIC_FOIL_HOLE_FINDING = "automaticFoilHoleFinding"


class PluginType(str, Enum):
    """Types of plugins."""

    DEFAULT = "default"
    CUSTOM = "custom"
    DUMMY = "dummy"


class GridType(str, Enum):
    """Types of grids."""

    HOLEY_CARBON = "HoleyCarbon"
    HOLEY_GOLD = "HoleyGold"
    LACEY_CARBON = "LaceyCarbon"


# Request Models
class ApplicationStateChange(BaseModel):
    """Request model for changing application state."""

    state: EngineState
    sessionId: UUID | None = None
    areaId: int | None = None
    details: str | None = None


class AreaStateChange(BaseModel):
    """Request model for changing area state."""

    sessionId: UUID
    areaId: int
    state: AcquisitionState


class Area(BaseModel):
    """Request model for area registration."""

    id: int
    sessionId: UUID
    areaType: AreaType
    parentId: int | None = None


class AlgorithmResultRecord(BaseModel):
    """Request model for algorithm result."""

    sessionId: UUID
    areaId: int
    name: str | None = None
    result: dict[str, Any] | None = None
    timestamp: datetime


class DecisionRecord(BaseModel):
    """Request model for decision recording."""

    id: UUID
    sessionId: UUID
    areaId: int
    decisionType: DecisionType
    pluginType: PluginType
    decisionValue: str | None = None
    decidedBy: str | None = None
    details: str | None = None
    timestamp: datetime


class NameValueRecord(BaseModel):
    """Request model for name-value storage."""

    id: int
    sessionId: UUID
    areaId: int | None = None
    name: str | None = None
    value: str | None = None
    timestamp: datetime
    setBy: str | None = None


class Session(BaseModel):
    """Request model for session."""

    sessionId: UUID
    sessionName: str | None = None
    athenaId: str | None = None
    timestamp: datetime
    gridType: GridType


class RunStart(BaseModel):
    """Request model for starting a run."""

    sessionId: UUID


class RunStop(BaseModel):
    """Request model for stopping a run."""

    sessionId: UUID
    runNumber: int
    reason: str | None = None


class SmartPluginConfiguration(BaseModel):
    """Configuration for smart plugins."""

    pluginName: str | None = None
    customPluginSelection: bool
    timestamp: datetime | None = None


class DecisionServiceConfiguration(BaseModel):
    """Request model for decision service configuration."""

    id: UUID
    smartPluginConfigurations: list[SmartPluginConfiguration] | None = None
    timestamp: datetime
