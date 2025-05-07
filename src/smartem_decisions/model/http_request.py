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
class AcquisitionBaseFields(BaseModel):
    uuid: str | None = None
    name: str | None = None
    status: AcquisitionStatus | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    paused_time: datetime | None = None
    storage_path: str | None = None
    atlas_path: str | None = None
    clustering_mode: str | None = None
    clustering_radius: str | None = None


class AcquisitionBaseRequest(AcquisitionBaseFields):
    uuid: str  # Override with required


class AcquisitionCreateRequest(AcquisitionBaseRequest):
    pass


class AcquisitionUpdateRequest(AcquisitionBaseFields):
    pass


# Atlas models
class AtlasTileBaseFields(BaseModel):
    uuid: str | None = None
    position_x: int | None = None
    position_y: int | None = None
    size_x: int | None = None
    size_y: int | None = None
    file_format: str | None = None
    base_filename: str | None = None
    atlas_id: str | None = None


class AtlasTileBaseRequest(AtlasTileBaseFields):
    uuid: str  # Override with required


class AtlasTileCreateRequest(AtlasTileBaseRequest):
    atlas_id: str  # Override with required


class AtlasTileUpdateRequest(AtlasTileBaseFields):
    pass


class AtlasBaseFields(BaseModel):
    atlas_id: str | None = None
    grid_id: str | None = None
    acquisition_date: datetime | None = None
    storage_folder: str | None = None
    description: str | None = None
    name: str | None = None


class AtlasBaseRequest(AtlasBaseFields):
    atlas_id: str  # Override with required
    grid_id: str   # Override with required
    name: str      # Override with required


class AtlasCreateRequest(AtlasBaseRequest):
    tiles: list[AtlasTileCreateRequest] | None = None


class AtlasUpdateRequest(AtlasBaseFields):
    # All fields already optional in the parent
    pass


# Grid models
class GridBaseFields(BaseModel):
    uuid: str | None = None
    name: str | None = None
    acquisition_uuid: str | None = None
    status: GridStatus | None = None
    data_dir: str | None = None
    atlas_dir: str | None = None
    scan_start_time: datetime | None = None
    scan_end_time: datetime | None = None


class GridBaseRequest(GridBaseFields):
    uuid: str  # Override with required
    name: str  # Override with required
    acquisition_uuid: str  # Override with required


class GridCreateRequest(GridBaseRequest):
    pass


class GridUpdateRequest(GridBaseFields):
    pass


# GridSquare models
class GridSquareBaseFields(BaseModel):
    uuid: str | None = None
    grid_id: str | None = None
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


class GridSquareBaseRequest(GridSquareBaseFields):
    uuid: str  # Override with required
    grid_id: str  # Override with required


class GridSquareCreateRequest(GridSquareBaseRequest):
    pass


class GridSquareUpdateRequest(GridSquareBaseFields):
    pass


# FoilHole models
class FoilHoleBaseFields(BaseModel):
    uuid: str | None = None
    gridsquare_id: str | None = None
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
    is_near_grid_bar: bool = False

    status: FoilHoleStatus | None = None


class FoilHoleBaseRequest(FoilHoleBaseFields):
    uuid: str  # Override with required
    id: str  # Override with required
    gridsquare_id: str  # Override with required


class FoilHoleCreateRequest(FoilHoleBaseRequest):
    pass


class FoilHoleUpdateRequest(FoilHoleBaseFields):
    pass


# Micrograph models
class MicrographBaseFields(BaseModel):
    uuid: str | None = None
    foilhole_id: str | None = None
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


class MicrographBaseRequest(MicrographBaseFields):
    uuid: str  # Override with required
    foilhole_id: str  # Override with required


class MicrographCreateRequest(MicrographBaseRequest):
    pass


class MicrographUpdateRequest(MicrographBaseFields):
    pass
