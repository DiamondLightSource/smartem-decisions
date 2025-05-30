from datetime import datetime

from pydantic import BaseModel, ConfigDict

from smartem_decisions.model.entity_status import (
    AcquisitionStatus,
    FoilHoleStatus,
    GridSquareStatus,
    GridStatus,
    MicrographStatus,
)


class AtlasTileResponse(BaseModel):
    uuid: str
    atlas_id: str
    tile_id: str
    position_x: int | None
    position_y: int | None
    size_x: int | None
    size_y: int | None
    file_format: str | None
    base_filename: str | None

    model_config = ConfigDict(from_attributes=True)


class AtlasResponse(BaseModel):
    uuid: str
    grid_id: str
    atlas_id: str
    acquisition_date: datetime | None
    storage_folder: str | None
    description: str | None
    name: str
    tiles: list[AtlasTileResponse] | None = []

    model_config = ConfigDict(from_attributes=True, json_encoders={datetime: lambda v: v.isoformat() if v else None})


class AcquisitionResponse(BaseModel):
    uuid: str
    name: str
    status: AcquisitionStatus | None
    start_time: datetime | None
    end_time: datetime | None
    paused_time: datetime | None
    storage_path: str | None
    atlas_path: str | None
    clustering_mode: str | None
    clustering_radius: str | None

    model_config = ConfigDict(
        from_attributes=True, use_enum_values=True, json_encoders={datetime: lambda v: v.isoformat() if v else None}
    )


class GridResponse(BaseModel):
    uuid: str
    acquisition_uuid: str | None
    status: GridStatus | None
    name: str
    data_dir: str | None
    atlas_dir: str | None
    scan_start_time: datetime | None
    scan_end_time: datetime | None

    model_config = ConfigDict(
        from_attributes=True, use_enum_values=True, json_encoders={datetime: lambda v: v.isoformat() if v else None}
    )


class GridSquareResponse(BaseModel):
    uuid: str
    gridsquare_id: str
    grid_uuid: str | None
    status: GridSquareStatus | None
    data_dir: str | None
    atlas_node_id: int | None
    state: str | None
    rotation: float | None
    image_path: str | None
    selected: bool | None
    unusable: bool | None
    stage_position_x: float | None
    stage_position_y: float | None
    stage_position_z: float | None
    center_x: int | None
    center_y: int | None
    physical_x: float | None
    physical_y: float | None
    size_width: int | None
    size_height: int | None
    acquisition_datetime: datetime | None
    defocus: float | None
    magnification: float | None
    pixel_size: float | None
    detector_name: str | None
    applied_defocus: float | None

    model_config = ConfigDict(
        from_attributes=True, use_enum_values=True, json_encoders={datetime: lambda v: v.isoformat() if v else None}
    )


class FoilHoleResponse(BaseModel):
    uuid: str
    gridsquare_id: str | None
    foilhole_id: str
    status: FoilHoleStatus
    center_x: float | None
    center_y: float | None
    quality: float | None
    rotation: float | None
    size_width: float | None
    size_height: float | None
    x_location: int | None
    y_location: int | None
    x_stage_position: float | None
    y_stage_position: float | None
    diameter: int | None
    is_near_grid_bar: bool

    model_config = ConfigDict(from_attributes=True, use_enum_values=True)


class MicrographResponse(BaseModel):
    uuid: str
    foilhole_uuid: str
    foilhole_id: str | None = None
    micrograph_id: str | None = None
    location_id: str | None = None
    status: MicrographStatus
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

    model_config = ConfigDict(
        from_attributes=True, use_enum_values=True, json_encoders={datetime: lambda v: v.isoformat() if v else None}
    )
