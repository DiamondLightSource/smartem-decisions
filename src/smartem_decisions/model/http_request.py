from pydantic import BaseModel
from datetime import datetime

from src.smartem_decisions.model.entity_status import (
    AcquisitionStatus,
    GridStatus,
    GridSquareStatus,
    FoilHoleStatus,
    MicrographStatus,
)


# Acquisition models
class AcquisitionBaseRequest(BaseModel):
    name: str | None = None
    id: str | None = None
    status: AcquisitionStatus | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    paused_time: datetime | None = None
    storage_path: str | None = None
    atlas_path: str | None = None
    clustering_mode: str | None = None
    clustering_radius: str | None = None


class AcquisitionCreateRequest(AcquisitionBaseRequest):
    pass


class AcquisitionUpdateRequest(BaseModel):
    pass


# Atlas models
class AtlasTileBaseRequest(BaseModel):
    tile_id: str
    position_x: int | None = None
    position_y: int | None = None
    size_x: int | None = None
    size_y: int | None = None
    file_format: str | None = None
    base_filename: str | None = None


class AtlasTileCreateRequest(AtlasTileBaseRequest):
    atlas_id: str


class AtlasTileUpdateRequest(BaseModel):
    tile_id: str | None = None
    position_x: int | None = None
    position_y: int | None = None
    size_x: int | None = None
    size_y: int | None = None
    file_format: str | None = None
    base_filename: str | None = None


class AtlasBaseRequest(BaseModel):
    atlas_id: str
    grid_id: str
    acquisition_date: datetime | None = None
    storage_folder: str | None = None
    description: str | None = None
    name: str


class AtlasCreateRequest(AtlasBaseRequest):
    tiles: list[AtlasTileCreateRequest] | None = None


class AtlasUpdateRequest(BaseModel):
    atlas_id: str | None = None
    acquisition_date: datetime | None = None
    storage_folder: str | None = None
    description: str | None = None
    name: str | None = None


# Grid models
class GridBaseRequest(BaseModel):
    id: str
    name: str
    acquisition_id: str
    status: GridStatus | None = None
    data_dir: str | None = None
    atlas_dir: str | None = None
    scan_start_time: datetime | None = None
    scan_end_time: datetime | None = None


class GridCreateRequest(GridBaseRequest):
    pass


class GridUpdateRequest(BaseModel):
    name: str | None = None
    acquisition_id: str | None = None
    status: GridStatus | None = None
    data_dir: str | None = None
    atlas_dir: str | None = None
    scan_start_time: datetime | None = None
    scan_end_time: datetime | None = None


# GridSquare models
class GridSquareBaseRequest(BaseModel):
    grid_id: str
    gridsquare_id: str
    data_dir: str | None = None

    # From GridSquareMetadata
    atlas_node_id: int | None = None  # This remains int as it's not an ID reference
    state: str | None = None
    rotation: float | None = None
    image_path: str | None = None
    selected: bool | None = None
    unusable: bool | None = None

    # From GridSquareStagePosition
    stage_position_x: float | None = None
    stage_position_y: float | None = None
    stage_position_z: float | None = None

    # From GridSquarePosition
    center_x: int | None = None
    center_y: int | None = None
    physical_x: float | None = None
    physical_y: float | None = None
    size_width: int | None = None
    size_height: int | None = None

    # From GridSquareManifest
    acquisition_datetime: datetime | None = None
    defocus: float | None = None
    magnification: float | None = None
    pixel_size: float | None = None
    detector_name: str | None = None
    applied_defocus: float | None = None

    status: GridSquareStatus | None = None


class GridSquareCreateRequest(GridSquareBaseRequest):
    pass


class GridSquareUpdateRequest(BaseModel):
    gridsquare_id: str | None = None
    data_dir: str | None = None

    # From GridSquareMetadata
    atlas_node_id: int | None = None
    state: str | None = None
    rotation: float | None = None
    image_path: str | None = None
    selected: bool | None = None
    unusable: bool | None = None

    # From GridSquareStagePosition
    stage_position_x: float | None = None
    stage_position_y: float | None = None
    stage_position_z: float | None = None

    # From GridSquarePosition
    center_x: int | None = None
    center_y: int | None = None
    physical_x: float | None = None
    physical_y: float | None = None
    size_width: int | None = None
    size_height: int | None = None

    # From GridSquareManifest
    acquisition_datetime: datetime | None = None
    defocus: float | None = None
    magnification: float | None = None
    pixel_size: float | None = None
    detector_name: str | None = None
    applied_defocus: float | None = None

    status: GridSquareStatus | None = None
    grid_id: str | None = None


# FoilHole models
class FoilHoleBaseRequest(BaseModel):
    gridsquare_id: str
    foilhole_id: str

    # From FoilHoleData
    center_x: float | None = None
    center_y: float | None = None
    quality: float | None = None
    rotation: float | None = None
    size_width: float | None = None
    size_height: float | None = None

    # From FoilHolePosition
    x_location: int | None = None
    y_location: int | None = None
    x_stage_position: float | None = None
    y_stage_position: float | None = None
    diameter: int | None = None
    is_near_grid_bar: bool = False

    status: FoilHoleStatus | None = None


class FoilHoleCreateRequest(FoilHoleBaseRequest):
    pass


class FoilHoleUpdateRequest(BaseModel):
    foilhole_id: str | None = None

    # From FoilHoleData
    center_x: float | None = None
    center_y: float | None = None
    quality: float | None = None
    rotation: float | None = None
    size_width: float | None = None
    size_height: float | None = None

    # From FoilHolePosition
    x_location: int | None = None
    y_location: int | None = None
    x_stage_position: float | None = None
    y_stage_position: float | None = None
    diameter: int | None = None
    is_near_grid_bar: bool | None = None

    status: FoilHoleStatus | None = None
    gridsquare_id: str | None = None


# Micrograph models
class MicrographBaseRequest(BaseModel):
    foilhole_id: str
    micrograph_id: str
    location_id: str | None = None
    high_res_path: str | None = None
    manifest_file: str | None = None

    # From MicrographManifest
    acquisition_datetime: datetime | None = None
    defocus: float | None = None
    detector_name: str | None = None
    energy_filter: bool | None = None
    phase_plate: bool | None = None
    image_size_x: int | None = None
    image_size_y: int | None = None
    binning_x: int | None = None
    binning_y: int | None = None

    # Processing fields
    total_motion: float | None = None
    average_motion: float | None = None
    ctf_max_resolution_estimate: float | None = None
    number_of_particles_selected: int | None = None
    number_of_particles_rejected: int | None = None
    selection_distribution: str | None = None
    number_of_particles_picked: int | None = None
    pick_distribution: str | None = None

    status: MicrographStatus | None = None


class MicrographCreateRequest(MicrographBaseRequest):
    pass


class MicrographUpdateRequest(BaseModel):
    micrograph_id: str | None = None
    location_id: str | None = None
    high_res_path: str | None = None
    manifest_file: str | None = None

    # From MicrographManifest
    acquisition_datetime: datetime | None = None
    defocus: float | None = None
    detector_name: str | None = None
    energy_filter: bool | None = None
    phase_plate: bool | None = None
    image_size_x: int | None = None
    image_size_y: int | None = None
    binning_x: int | None = None
    binning_y: int | None = None

    # Processing fields
    total_motion: float | None = None
    average_motion: float | None = None
    ctf_max_resolution_estimate: float | None = None
    number_of_particles_selected: int | None = None
    number_of_particles_rejected: int | None = None
    selection_distribution: str | None = None
    number_of_particles_picked: int | None = None
    pick_distribution: str | None = None

    status: MicrographStatus | None = None
    foilhole_id: str | None = None
