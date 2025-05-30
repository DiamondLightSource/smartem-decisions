from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from epu_data_intake.utils import generate_uuid


class MicrographManifest(BaseModel):
    unique_id: str
    acquisition_datetime: datetime
    defocus: float | None
    detector_name: str
    energy_filter: bool
    phase_plate: bool
    image_size_x: int | None
    image_size_y: int | None
    binning_x: int
    binning_y: int

    model_config = ConfigDict(json_encoders={datetime: lambda v: v.isoformat() if v else None}, from_attributes=True)

    def validate_natural_numbers(self):
        for natural_num in ["image_size_x", "image_size_y", "binning_x", "binning_y"]:
            value = getattr(self, natural_num)
            if value is not None and value <= 0:
                raise ValueError(f"{natural_num} must be positive, got {value}")


class MicrographData(BaseModel):
    id: str
    gridsquare_id: str
    foilhole_uuid: str
    foilhole_id: str
    location_id: str
    high_res_path: Path
    manifest_file: Path
    manifest: MicrographManifest
    uuid: str = Field(default_factory=generate_uuid)

    model_config = ConfigDict(from_attributes=True)


class FoilHoleData(BaseModel):
    id: str
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
    uuid: str = Field(default_factory=generate_uuid)

    model_config = ConfigDict(from_attributes=True)


class GridSquareManifest(BaseModel):
    acquisition_datetime: datetime
    defocus: float | None
    magnification: float | None
    pixel_size: float | None
    detector_name: str
    applied_defocus: float | None
    data_dir: Path | None = None

    model_config = ConfigDict(
        json_encoders={datetime: lambda v: v.isoformat() if v else None, Path: lambda v: str(v) if v else None},
        from_attributes=True,
    )


class GridSquareStagePosition(BaseModel):
    x: float | None
    y: float | None
    z: float | None

    model_config = ConfigDict(from_attributes=True)


class FoilHolePosition(BaseModel):
    x_location: int
    y_location: int
    x_stage_position: float | None
    y_stage_position: float | None
    diameter: int
    is_near_grid_bar: bool = False

    model_config = ConfigDict(from_attributes=True)


class GridSquarePosition(BaseModel):
    center: tuple[int, int] | None
    physical: tuple[float, float] | None
    size: tuple[int, int] | None
    rotation: float | None

    model_config = ConfigDict(from_attributes=True)


class GridSquareMetadata(BaseModel):
    atlas_node_id: int
    stage_position: GridSquareStagePosition | None
    state: str | None
    rotation: float | None
    image_path: Path | None
    selected: bool
    unusable: bool
    foilhole_positions: dict[int, FoilHolePosition] | None = {}

    model_config = ConfigDict(json_encoders={Path: lambda v: str(v) if v else None}, from_attributes=True)


class GridSquareData(BaseModel):
    gridsquare_id: str  # TODO refactor rename to `id` for consistency
    grid_uuid: str
    data_dir: Path | None = None
    metadata: GridSquareMetadata | None = None
    manifest: GridSquareManifest | None = None
    uuid: str = Field(default_factory=generate_uuid)

    model_config = ConfigDict(json_encoders={Path: lambda v: str(v) if v else None}, from_attributes=True)


class AtlasTilePosition(BaseModel):
    position: tuple[int, int] | None
    size: tuple[int, int] | None

    model_config = ConfigDict(from_attributes=True)


class AtlasTileData(BaseModel):
    id: str
    tile_position: AtlasTilePosition
    file_format: str | None
    base_filename: str | None
    uuid: str = Field(default_factory=generate_uuid)

    model_config = ConfigDict(from_attributes=True)


class AtlasData(BaseModel):
    id: str
    acquisition_date: datetime
    storage_folder: str
    description: str
    name: str
    tiles: list[AtlasTileData]
    gridsquare_positions: dict[int, GridSquarePosition] | None
    uuid: str = Field(default_factory=generate_uuid)

    model_config = ConfigDict(json_encoders={datetime: lambda v: v.isoformat() if v else None}, from_attributes=True)


class AcquisitionData(BaseModel):
    id: str | None = None
    name: str = "Unknown"
    start_time: datetime | None = None
    atlas_path: str | None = None
    storage_path: str | None = None
    clustering_mode: str | None = None
    clustering_radius: str | None = None
    uuid: str = Field(default_factory=generate_uuid)

    model_config = ConfigDict(json_encoders={datetime: lambda v: v.isoformat() if v else None}, from_attributes=True)


class GridData(BaseModel):
    data_dir: Path
    atlas_dir: Path | None = None
    acquisition_data: AcquisitionData | None = None
    atlas_data: AtlasData | None = None
    uuid: str = Field(default_factory=generate_uuid)

    model_config = ConfigDict(json_encoders={Path: lambda v: str(v) if v else None}, from_attributes=True)

    def model_post_init(self, __context__):
        if isinstance(self.data_dir, str):
            self.data_dir = Path(self.data_dir)
