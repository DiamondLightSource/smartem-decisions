from pydantic import BaseModel, ConfigDict
from datetime import datetime

from src.smartem_decisions.model.entity_status import (
    AcquisitionStatus,
    GridStatus,
    GridSquareStatus,
    FoilHoleStatus,
    MicrographStatus,
)


# ========== HTTP Response Models ==========

class AtlasTileResponse(BaseModel):
    id: int
    atlas_id: int
    tile_id: str
    position_x: int | None
    position_y: int | None
    size_x: int | None
    size_y: int | None
    file_format: str | None
    base_filename: str | None

    model_config = ConfigDict(from_attributes=True)


class AtlasResponse(BaseModel):
    id: int
    grid_id: int
    atlas_id: str
    acquisition_date: datetime | None
    storage_folder: str | None
    description: str | None
    name: str
    tiles: list[AtlasTileResponse] | None = []

    model_config = ConfigDict(from_attributes=True)


class AcquisitionResponse(BaseModel):
    id: int
    epu_id: str | None
    name: str
    status: AcquisitionStatus
    start_time: datetime | None
    end_time: datetime | None
    paused_time: datetime | None
    storage_path: str | None
    atlas_path: str | None
    clustering_mode: str | None
    clustering_radius: str | None

    model_config = ConfigDict(from_attributes=True)


class GridResponse(BaseModel):
    id: int
    acquisition_id: int | None  # Changed from session_id to acquisition_id
    status: GridStatus
    name: str
    data_dir: str | None
    atlas_dir: str | None
    scan_start_time: datetime | None
    scan_end_time: datetime | None

    model_config = ConfigDict(from_attributes=True)


class GridSquareResponse(BaseModel):
    id: int
    grid_id: int | None
    gridsquare_id: str
    status: GridSquareStatus
    data_dir: str | None

    # From GridSquareMetadata
    atlas_node_id: int | None
    state: str | None
    rotation: float | None
    image_path: str | None
    selected: bool | None
    unusable: bool | None

    # From GridSquareStagePosition
    stage_position_x: float | None
    stage_position_y: float | None
    stage_position_z: float | None

    # From GridSquarePosition
    center_x: int | None
    center_y: int | None
    physical_x: float | None
    physical_y: float | None
    size_width: int | None
    size_height: int | None

    # From GridSquareManifest
    acquisition_datetime: datetime | None
    defocus: float | None
    magnification: float | None
    pixel_size: float | None
    detector_name: str | None
    applied_defocus: float | None

    model_config = ConfigDict(from_attributes=True)


class FoilHoleResponse(BaseModel):
    id: int
    gridsquare_id: int | None
    foilhole_id: str
    status: FoilHoleStatus

    # From FoilHoleData
    center_x: float | None
    center_y: float | None
    quality: float | None
    rotation: float | None
    size_width: float | None
    size_height: float | None

    # From FoilHolePosition
    x_location: int | None
    y_location: int | None
    x_stage_position: float | None
    y_stage_position: float | None
    diameter: int | None
    is_near_grid_bar: bool

    model_config = ConfigDict(from_attributes=True)


class MicrographResponse(BaseModel):
    id: int
    foilhole_id: int | None
    micrograph_id: str
    location_id: str | None
    high_res_path: str | None
    manifest_file: str | None
    status: MicrographStatus

    # From MicrographManifest
    acquisition_datetime: datetime | None
    defocus: float | None
    detector_name: str | None
    energy_filter: bool | None
    phase_plate: bool | None
    image_size_x: int | None
    image_size_y: int | None
    binning_x: int | None
    binning_y: int | None

    # Processing fields
    total_motion: float | None
    average_motion: float | None
    ctf_max_resolution_estimate: float | None
    number_of_particles_selected: int | None
    number_of_particles_rejected: int | None
    selection_distribution: str | None
    number_of_particles_picked: int | None
    pick_distribution: str | None

    model_config = ConfigDict(from_attributes=True)
