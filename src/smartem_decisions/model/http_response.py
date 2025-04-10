from pydantic import BaseModel, ConfigDict
from datetime import datetime

from src.smartem_decisions.model.entity_status import (
    AcquisitionStatus,
    GridStatus,
    GridSquareStatus,
    FoilHoleStatus,
    MicrographStatus,
)


class AcquisitionResponse(BaseModel):
    id: int
    epu_id: str | None
    name: str
    status: AcquisitionStatus
    session_start_time: datetime | None
    session_end_time: datetime | None
    session_paused_time: datetime | None

    model_config = ConfigDict(from_attributes=True)


class GridResponse(BaseModel):
    id: int
    session_id: int | None
    status: GridStatus
    name: str
    scan_start_time: datetime | None
    scan_end_time: datetime | None

    model_config = ConfigDict(from_attributes=True)


class GridSquareResponse(BaseModel):
    id: int
    grid_id: int | None
    status: GridSquareStatus
    atlastile_img: str
    name: str

    model_config = ConfigDict(from_attributes=True)


class FoilHoleResponse(BaseModel):
    id: int
    gridsquare_id: int | None
    status: FoilHoleStatus
    name: str

    model_config = ConfigDict(from_attributes=True)


class MicrographResponse(BaseModel):
    id: int
    foilhole_id: int | None
    status: MicrographStatus
    total_motion: float | None
    average_motion: float | None
    ctf_max_resolution_estimate: float | None
    number_of_particles_selected: int | None
    number_of_particles_rejected: int | None
    selection_distribution: str | None
    number_of_particles_picked: int | None
    pick_distribution: str | None

    model_config = ConfigDict(from_attributes=True)
