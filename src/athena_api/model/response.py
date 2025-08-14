"""Athena API response models."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel

from .request import (
    AcquisitionState,
    AreaType,
    DecisionType,
    EngineState,
    GridType,
    PluginType,
    SmartPluginConfiguration,
)


# Response Models
class ApplicationState(BaseModel):
    """Response model for application state."""

    id: UUID
    state: EngineState
    sessionId: UUID | None = None
    areaId: int | None = None
    details: str | None = None
    timestamp: datetime | None = None


class AreaState(BaseModel):
    """Response model for area state."""

    id: int
    sessionId: UUID
    areaId: int
    state: AcquisitionState
    timestamp: datetime | None = None


class AlgorithmResultRecord(BaseModel):
    """Response model for algorithm result."""

    sessionId: UUID
    areaId: int
    name: str | None = None
    result: dict[str, Any] | None = None
    timestamp: datetime


class Area(BaseModel):
    """Response model for area."""

    id: int
    sessionId: UUID
    areaType: AreaType
    parentId: int | None = None


class DecisionRecord(BaseModel):
    """Response model for decision."""

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
    """Response model for name-value record."""

    id: int
    sessionId: UUID
    areaId: int | None = None
    name: str | None = None
    value: str | None = None
    timestamp: datetime
    setBy: str | None = None


class Session(BaseModel):
    """Response model for session."""

    sessionId: UUID
    sessionName: str | None = None
    athenaId: str | None = None
    timestamp: datetime
    gridType: GridType


class Run(BaseModel):
    """Response model for run."""

    sessionId: UUID
    runNumber: int
    startTime: datetime | None = None
    stopTime: datetime | None = None
    stopReason: str | None = None


class DecisionServiceConfiguration(BaseModel):
    """Response model for decision service configuration."""

    id: UUID
    smartPluginConfigurations: list[SmartPluginConfiguration] | None = None
    timestamp: datetime


class ProblemDetails(BaseModel):
    """Standard problem details response model."""

    type: str | None = None
    title: str | None = None
    status: int | None = None
    detail: str | None = None
    instance: str | None = None
    extensions: dict[str, Any] | None = None
