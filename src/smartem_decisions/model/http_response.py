from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional

from .entity_status import (
    AcquisitionStatus,
    GridStatus,
    GridSquareStatus,
    FoilHoleStatus,
    MicrographStatus,
)


class AcquisitionResponse(BaseModel):
    id: int
    epu_id: Optional[str]
    name: str
    status: AcquisitionStatus
    session_start_time: Optional[datetime]
    session_end_time: Optional[datetime]
    session_paused_time: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


class GridResponse(BaseModel):
    id: int
    session_id: Optional[int]
    status: GridStatus
    name: str
    scan_start_time: Optional[datetime]
    scan_end_time: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


class GridSquareResponse(BaseModel):
    id: int
    grid_id: Optional[int]
    status: GridSquareStatus
    atlastile_img: str
    name: str

    model_config = ConfigDict(from_attributes=True)


class FoilHoleResponse(BaseModel):
    id: int
    gridsquare_id: Optional[int]
    status: FoilHoleStatus
    name: str

    model_config = ConfigDict(from_attributes=True)


class MicrographResponse(BaseModel):
    id: int
    foilhole_id: Optional[int]
    status: MicrographStatus
    total_motion: Optional[float]
    average_motion: Optional[float]
    ctf_max_resolution_estimate: Optional[float]
    number_of_particles_selected: Optional[int]
    number_of_particles_rejected: Optional[int]
    selection_distribution: Optional[str]
    number_of_particles_picked: Optional[int]
    pick_distribution: Optional[str]

    model_config = ConfigDict(from_attributes=True)
