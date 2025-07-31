from datetime import datetime

from pydantic import BaseModel, ConfigDict

from smartem_common.entity_status import (
    AcquisitionStatus,
    FoilHoleStatus,
    GridSquareStatus,
    GridStatus,
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
    instrument_model: str | None = None
    instrument_id: str | None = None
    computer_name: str | None = None

    model_config = {
        "use_enum_values": True,
        "json_encoders": {
            datetime: lambda v: v.isoformat(),
        },
    }


class AcquisitionBaseRequest(AcquisitionBaseFields):
    uuid: str


class AcquisitionCreateRequest(AcquisitionBaseRequest):
    pass


class AcquisitionUpdateRequest(AcquisitionBaseFields):
    pass


# Atlas models
class AtlasBaseFields(BaseModel):
    uuid: str | None = None
    atlas_id: str | None = None
    grid_uuid: str | None = None
    acquisition_date: datetime | None = None
    storage_folder: str | None = None
    description: str | None = None
    name: str | None = None

    model_config = {
        "json_encoders": {
            datetime: lambda v: v.isoformat(),
        }
    }


class AtlasTileBaseFields(BaseModel):
    uuid: str | None = None
    tile_id: str | None = None
    position_x: int | None = None
    position_y: int | None = None
    size_x: int | None = None
    size_y: int | None = None
    file_format: str | None = None
    base_filename: str | None = None
    atlas_uuid: str | None = None


class AtlasTileBaseRequest(AtlasTileBaseFields):
    uuid: str


class AtlasTileCreateRequest(AtlasTileBaseRequest):
    atlas_uuid: str


class AtlasTileUpdateRequest(AtlasTileBaseFields):
    pass


class AtlasBaseRequest(AtlasBaseFields):
    uuid: str
    grid_uuid: str
    name: str


class AtlasCreateRequest(AtlasBaseRequest):
    tiles: list[AtlasTileCreateRequest] | None = None


class AtlasUpdateRequest(AtlasBaseFields):
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

    model_config = {
        "use_enum_values": True,
        "json_encoders": {
            datetime: lambda v: v.isoformat(),
        },
    }


class GridBaseRequest(GridBaseFields):
    uuid: str
    name: str
    acquisition_uuid: str


class GridCreateRequest(GridBaseRequest):
    pass


class GridUpdateRequest(GridBaseFields):
    pass


class GridSquarePositionRequest(BaseModel):
    center_x: int
    center_y: int
    size_width: int
    size_height: int


# GridSquare models
class GridSquareBaseFields(BaseModel):
    uuid: str | None = None
    gridsquare_id: str | None = None
    grid_uuid: str | None = None
    data_dir: str | None = None
    atlas_node_id: int | None = None
    state: str | None = None
    rotation: float | None = None
    image_path: str | None = None
    selected: bool | None = None
    unusable: bool | None = None
    stage_position_x: float | None = None
    stage_position_y: float | None = None
    stage_position_z: float | None = None
    center_x: int | None = None
    center_y: int | None = None
    physical_x: float | None = None
    physical_y: float | None = None
    size_width: int | None = None
    size_height: int | None = None
    acquisition_datetime: datetime | None = None
    defocus: float | None = None
    magnification: float | None = None
    pixel_size: float | None = None
    detector_name: str | None = None
    applied_defocus: float | None = None
    status: GridSquareStatus | None = None

    model_config = ConfigDict(
        use_enum_values=True, json_encoders={datetime: lambda v: v.isoformat() if v else None}, from_attributes=True
    )


class GridSquareBaseRequest(GridSquareBaseFields):
    uuid: str
    gridsquare_id: str
    grid_uuid: str
    center_x: int | None = None
    center_y: int | None = None
    size_width: int | None = None
    size_height: int | None = None


class GridSquareCreateRequest(GridSquareBaseRequest):
    lowmag: bool = False


class GridSquareUpdateRequest(GridSquareBaseFields):
    lowmag: bool = False


# FoilHole models
class FoilHoleBaseFields(BaseModel):
    uuid: str | None = None
    foilhole_id: str | None = None
    gridsquare_id: str | None = None
    gridsquare_uuid: str | None = None
    center_x: float | None = None
    center_y: float | None = None
    quality: float | None = None
    rotation: float | None = None
    size_width: float | None = None
    size_height: float | None = None
    x_location: int | None = None
    y_location: int | None = None
    x_stage_position: float | None = None
    y_stage_position: float | None = None
    diameter: int | None = None
    is_near_grid_bar: bool = False
    status: FoilHoleStatus | None = None

    model_config = {"use_enum_values": True}


class FoilHoleBaseRequest(FoilHoleBaseFields):
    uuid: str
    foilhole_id: str
    gridsquare_id: str
    gridsquare_uuid: str


class FoilHoleCreateRequest(FoilHoleBaseRequest):
    pass


class FoilHoleUpdateRequest(FoilHoleBaseFields):
    pass


# Micrograph models
class MicrographBaseFields(BaseModel):
    uuid: str | None = None
    foilhole_uuid: str | None = None
    foilhole_id: str | None = None
    location_id: str | None = None
    high_res_path: str | None = None
    manifest_file: str | None = None
    acquisition_datetime: datetime | None = None
    defocus: float | None = None
    detector_name: str | None = None
    energy_filter: bool | None = None
    phase_plate: bool | None = None
    image_size_x: int | None = None
    image_size_y: int | None = None
    binning_x: int | None = None
    binning_y: int | None = None
    total_motion: float | None = None
    average_motion: float | None = None
    ctf_max_resolution_estimate: float | None = None
    number_of_particles_selected: int | None = None
    number_of_particles_rejected: int | None = None
    selection_distribution: str | None = None
    number_of_particles_picked: int | None = None
    pick_distribution: str | None = None
    status: MicrographStatus = MicrographStatus.NONE  # Default to NONE

    model_config = {
        "use_enum_values": True,
        "json_encoders": {
            datetime: lambda v: v.isoformat() if v else None,
        },
    }


class MicrographBaseRequest(MicrographBaseFields):
    uuid: str
    foilhole_id: str
    # foilhole_uuid is not required here since it comes from the path parameter


class MicrographCreateRequest(MicrographBaseRequest):
    pass


class MicrographUpdateRequest(MicrographBaseFields):
    pass
