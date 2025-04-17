from pydantic import BaseModel, Field
from datetime import datetime

from src.smartem_decisions.model.entity_status import (
    AcquisitionStatus,
    GridStatus,
    GridSquareStatus,
    FoilHoleStatus,
    MicrographStatus,
)

# Acquisition models
class AcquisitionBase(BaseModel):
    name: str
    epu_id: str | None = None
    status: AcquisitionStatus | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    paused_time: datetime | None = None
    storage_path: str | None = None
    atlas_path: str | None = None
    clustering_mode: str | None = None
    clustering_radius: str | None = None


class AcquisitionCreate(AcquisitionBase):
    pass


class AcquisitionUpdate(BaseModel):
    name: str | None = None
    epu_id: str | None = None
    status: AcquisitionStatus | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    paused_time: datetime | None = None
    storage_path: str | None = None
    atlas_path: str | None = None
    clustering_mode: str | None = None
    clustering_radius: str | None = None


# Atlas models
class AtlasTileBase(BaseModel):
    tile_id: str
    position_x: int | None = None
    position_y: int | None = None
    size_x: int | None = None
    size_y: int | None = None
    file_format: str | None = None
    base_filename: str | None = None


class AtlasTileCreate(AtlasTileBase):
    atlas_id: int


class AtlasTileUpdate(BaseModel):
    tile_id: str | None = None
    position_x: int | None = None
    position_y: int | None = None
    size_x: int | None = None
    size_y: int | None = None
    file_format: str | None = None
    base_filename: str | None = None


class AtlasBase(BaseModel):
    atlas_id: str
    grid_id: int
    acquisition_date: datetime | None = None
    storage_folder: str | None = None
    description: str | None = None
    name: str


class AtlasCreate(AtlasBase):
    tiles: list[AtlasTileCreate] | None = None


class AtlasUpdate(BaseModel):
    atlas_id: str | None = None
    acquisition_date: datetime | None = None
    storage_folder: str | None = None
    description: str | None = None
    name: str | None = None


# Grid models
class GridBase(BaseModel):
    name: str
    acquisition_id: int  # Changed from session_id to acquisition_id
    status: GridStatus | None = None
    data_dir: str | None = None
    atlas_dir: str | None = None
    scan_start_time: datetime | None = None
    scan_end_time: datetime | None = None


class GridCreate(GridBase):
    pass


class GridUpdate(BaseModel):
    name: str | None = None
    acquisition_id: int | None = None  # Changed from session_id to acquisition_id
    status: GridStatus | None = None
    data_dir: str | None = None
    atlas_dir: str | None = None
    scan_start_time: datetime | None = None
    scan_end_time: datetime | None = None


# GridSquare models
class GridSquareBase(BaseModel):
    grid_id: int
    gridsquare_id: str  # Original string ID from data model
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


class GridSquareCreate(GridSquareBase):
    pass


class GridSquareUpdate(BaseModel):
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
    grid_id: int | None = None


# FoilHole models
class FoilHoleBase(BaseModel):
    gridsquare_id: int
    foilhole_id: str  # Original string ID from data model

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


class FoilHoleCreate(FoilHoleBase):
    pass


class FoilHoleUpdate(BaseModel):
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
    gridsquare_id: int | None = None


# Micrograph models
class MicrographBase(BaseModel):
    foilhole_id: int
    micrograph_id: str  # Original string ID from data model
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


class MicrographCreate(MicrographBase):
    pass


class MicrographUpdate(BaseModel):
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
    foilhole_id: int | None = None
