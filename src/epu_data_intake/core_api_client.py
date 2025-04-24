from datetime import datetime
import httpx
from enum import Enum
from pydantic import BaseModel


# TODO refactor shared definitions out into `shared` module and import from there
#   both in `epu_data_intake` (epu_agent) and `smartem_decisions` (core)
class AcquisitionStatus(str, Enum):
    PLANNED = "planned"
    STARTED = "started"
    COMPLETED = "completed"
    PAUSED = "paused"
    ABANDONED = "abandoned"


class GridStatus(str, Enum):
    NONE = "none"
    SCAN_STARTED = "scan started"
    SCAN_COMPLETED = "scan completed"
    GRID_SQUARES_DECISION_STARTED = "grid squares decision started"
    GRID_SQUARES_DECISION_COMPLETED = "grid squares decision completed"


class GridSquareStatus(str, Enum):
    NONE = "none"
    FOIL_HOLES_DECISION_STARTED = "foil holes decision started"
    FOIL_HOLES_DECISION_COMPLETED = "foil holes decision completed"


class FoilHoleStatus(str, Enum):
    NONE = "none"
    MICROGRAPHS_DETECTED = "micrographs detected"


class MicrographStatus(str, Enum):
    NONE = "none"
    MOTION_CORRECTION_STARTED = "motion correction started"
    MOTION_CORRECTION_COMPLETED = "motion correction completed"
    CTF_STARTED = "ctf started"
    CTF_COMPLETED = "ctf completed"
    PARTICLE_PICKING_STARTED = "particle picking started"
    PARTICLE_PICKING_COMPLETED = "particle picking completed"
    PARTICLE_SELECTION_STARTED = "particle selection started"
    PARTICLE_SELECTION_COMPLETED = "particle selection completed"


# Request Models
class AcquisitionCreateRequest(BaseModel):
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


class AcquisitionUpdateRequest(BaseModel):
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


class AtlasTileCreateRequest(BaseModel):
    tile_id: str
    position_x: int | None = None
    position_y: int | None = None
    size_x: int | None = None
    size_y: int | None = None
    file_format: str | None = None
    base_filename: str | None = None
    atlas_id: int


class AtlasCreateRequest(BaseModel):
    atlas_id: str
    grid_id: int
    acquisition_date: datetime | None = None
    storage_folder: str | None = None
    description: str | None = None
    name: str
    tiles: list[AtlasTileCreateRequest] | None = None


class AtlasUpdateRequest(BaseModel):
    atlas_id: str | None = None
    acquisition_date: datetime | None = None
    storage_folder: str | None = None
    description: str | None = None
    name: str | None = None


class AtlasTileUpdateRequest(BaseModel):
    tile_id: str | None = None
    position_x: int | None = None
    position_y: int | None = None
    size_x: int | None = None
    size_y: int | None = None
    file_format: str | None = None
    base_filename: str | None = None


class GridCreateRequest(BaseModel):
    name: str
    acquisition_id: int
    status: GridStatus | None = None
    data_dir: str | None = None
    atlas_dir: str | None = None
    scan_start_time: datetime | None = None
    scan_end_time: datetime | None = None


class GridUpdateRequest(BaseModel):
    name: str | None = None
    acquisition_id: int | None = None
    status: GridStatus | None = None
    data_dir: str | None = None
    atlas_dir: str | None = None
    scan_start_time: datetime | None = None
    scan_end_time: datetime | None = None


class GridSquareCreateRequest(BaseModel):
    grid_id: int
    gridsquare_id: str
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


class GridSquareUpdateRequest(BaseModel):
    gridsquare_id: str | None = None
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
    grid_id: int | None = None


class FoilHoleCreateRequest(BaseModel):
    gridsquare_id: int
    foilhole_id: str
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


class FoilHoleUpdateRequest(BaseModel):
    foilhole_id: str | None = None
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
    is_near_grid_bar: bool | None = None
    status: FoilHoleStatus | None = None
    gridsquare_id: int | None = None


class MicrographCreateRequest(BaseModel):
    foilhole_id: int
    micrograph_id: str
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
    status: MicrographStatus | None = None


class MicrographUpdateRequest(BaseModel):
    micrograph_id: str | None = None
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
    status: MicrographStatus | None = None
    foilhole_id: int | None = None


# Response Models
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


class AtlasResponse(BaseModel):
    id: int
    grid_id: int
    atlas_id: str
    acquisition_date: datetime | None
    storage_folder: str | None
    description: str | None
    name: str
    tiles: list[AtlasTileResponse] = []


class GridResponse(BaseModel):
    id: int
    acquisition_id: int | None
    status: GridStatus
    name: str
    data_dir: str | None
    atlas_dir: str | None
    scan_start_time: datetime | None
    scan_end_time: datetime | None


class GridSquareResponse(BaseModel):
    id: int
    grid_id: int | None
    gridsquare_id: str
    status: GridSquareStatus
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


class FoilHoleResponse(BaseModel):
    id: int
    gridsquare_id: int | None
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


class MicrographResponse(BaseModel):
    id: int
    foilhole_id: int | None
    micrograph_id: str
    location_id: str | None
    high_res_path: str | None
    manifest_file: str | None
    status: MicrographStatus
    acquisition_datetime: datetime | None
    defocus: float | None
    detector_name: str | None
    energy_filter: bool | None
    phase_plate: bool | None
    image_size_x: int | None
    image_size_y: int | None
    binning_x: int | None
    binning_y: int | None
    total_motion: float | None
    average_motion: float | None
    ctf_max_resolution_estimate: float | None
    number_of_particles_selected: int | None
    number_of_particles_rejected: int | None
    selection_distribution: str | None
    number_of_particles_picked: int | None
    pick_distribution: str | None


# TODO move this to shared module as it may be useful for core module not just in agent
class SmartEMCoreAPIClient:
    def __init__(self, base_url: str, timeout: float = 10.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.client = httpx.AsyncClient(timeout=timeout)

    async def close(self):
        await self.client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    # General
    async def get_status(self) -> dict:
        """Get API status information"""
        response = await self.client.get(f"{self.base_url}/status")
        response.raise_for_status()
        return response.json()

    async def get_health(self) -> dict:
        """Get API health check information"""
        response = await self.client.get(f"{self.base_url}/health")
        response.raise_for_status()
        return response.json()

    # Acquisitions
    async def get_acquisitions(self) -> list[AcquisitionResponse]:
        response = await self.client.get(f"{self.base_url}/acquisitions")
        response.raise_for_status()
        return [AcquisitionResponse.model_validate(item) for item in response.json()]

    async def create_acquisition(self, acquisition: AcquisitionCreateRequest) -> AcquisitionResponse:
        response = await self.client.post(
            f"{self.base_url}/acquisitions", json=acquisition.model_dump(exclude_none=True)
        )
        response.raise_for_status()
        return AcquisitionResponse.model_validate(response.json())

    async def get_acquisition(self, acquisition_id: int) -> AcquisitionResponse:
        response = await self.client.get(f"{self.base_url}/acquisitions/{acquisition_id}")
        response.raise_for_status()
        return AcquisitionResponse.model_validate(response.json())

    async def update_acquisition(
        self, acquisition_id: int, acquisition: AcquisitionUpdateRequest
    ) -> AcquisitionResponse:
        response = await self.client.put(
            f"{self.base_url}/acquisitions/{acquisition_id}", json=acquisition.model_dump(exclude_none=True)
        )
        response.raise_for_status()
        return AcquisitionResponse.model_validate(response.json())

    async def delete_acquisition(self, acquisition_id: int) -> None:
        response = await self.client.delete(f"{self.base_url}/acquisitions/{acquisition_id}")
        response.raise_for_status()

    # Atlases
    async def get_atlases(self) -> list[AtlasResponse]:
        response = await self.client.get(f"{self.base_url}/atlases")
        response.raise_for_status()
        return [AtlasResponse.model_validate(item) for item in response.json()]

    async def create_atlas(self, atlas: AtlasCreateRequest) -> AtlasResponse:
        response = await self.client.post(f"{self.base_url}/atlases", json=atlas.model_dump(exclude_none=True))
        response.raise_for_status()
        return AtlasResponse.model_validate(response.json())

    async def get_atlas(self, atlas_id: int) -> AtlasResponse:
        response = await self.client.get(f"{self.base_url}/atlases/{atlas_id}")
        response.raise_for_status()
        return AtlasResponse.model_validate(response.json())

    async def update_atlas(self, atlas_id: int, atlas: AtlasUpdateRequest) -> AtlasResponse:
        response = await self.client.put(
            f"{self.base_url}/atlases/{atlas_id}", json=atlas.model_dump(exclude_none=True)
        )
        response.raise_for_status()
        return AtlasResponse.model_validate(response.json())

    async def delete_atlas(self, atlas_id: int) -> None:
        response = await self.client.delete(f"{self.base_url}/atlases/{atlas_id}")
        response.raise_for_status()

    # Grid Atlas
    async def get_grid_atlas(self, grid_id: int) -> AtlasResponse:
        response = await self.client.get(f"{self.base_url}/grids/{grid_id}/atlas")
        response.raise_for_status()
        return AtlasResponse.model_validate(response.json())

    async def create_grid_atlas(self, grid_id: int, atlas: AtlasCreateRequest) -> AtlasResponse:
        response = await self.client.post(
            f"{self.base_url}/grids/{grid_id}/atlas", json=atlas.model_dump(exclude_none=True)
        )
        response.raise_for_status()
        return AtlasResponse.model_validate(response.json())

    # Atlas Tiles
    async def get_atlas_tiles(self) -> list[AtlasTileResponse]:
        response = await self.client.get(f"{self.base_url}/atlas-tiles")
        response.raise_for_status()
        return [AtlasTileResponse.model_validate(item) for item in response.json()]

    async def create_atlas_tile(self, tile: AtlasTileCreateRequest) -> AtlasTileResponse:
        response = await self.client.post(f"{self.base_url}/atlas-tiles", json=tile.model_dump(exclude_none=True))
        response.raise_for_status()
        return AtlasTileResponse.model_validate(response.json())

    async def get_atlas_tile(self, tile_id: int) -> AtlasTileResponse:
        response = await self.client.get(f"{self.base_url}/atlas-tiles/{tile_id}")
        response.raise_for_status()
        return AtlasTileResponse.model_validate(response.json())

    async def update_atlas_tile(self, tile_id: int, tile: AtlasTileUpdateRequest) -> AtlasTileResponse:
        response = await self.client.put(
            f"{self.base_url}/atlas-tiles/{tile_id}", json=tile.model_dump(exclude_none=True)
        )
        response.raise_for_status()
        return AtlasTileResponse.model_validate(response.json())

    async def delete_atlas_tile(self, tile_id: int) -> None:
        response = await self.client.delete(f"{self.base_url}/atlas-tiles/{tile_id}")
        response.raise_for_status()

    # Atlas Tiles by Atlas
    async def get_atlas_tiles_by_atlas(self, atlas_id: int) -> list[AtlasTileResponse]:
        response = await self.client.get(f"{self.base_url}/atlases/{atlas_id}/tiles")
        response.raise_for_status()
        return [AtlasTileResponse.model_validate(item) for item in response.json()]

    async def create_atlas_tile_for_atlas(self, atlas_id: int, tile: AtlasTileCreateRequest) -> AtlasTileResponse:
        response = await self.client.post(
            f"{self.base_url}/atlases/{atlas_id}/tiles", json=tile.model_dump(exclude_none=True)
        )
        response.raise_for_status()
        return AtlasTileResponse.model_validate(response.json())

    # Grids
    async def get_grids(self) -> list[GridResponse]:
        response = await self.client.get(f"{self.base_url}/grids")
        response.raise_for_status()
        return [GridResponse.model_validate(item) for item in response.json()]

    async def create_grid(self, grid: GridCreateRequest) -> GridResponse:
        response = await self.client.post(f"{self.base_url}/grids", json=grid.model_dump(exclude_none=True))
        response.raise_for_status()
        return GridResponse.model_validate(response.json())

    async def get_grid(self, grid_id: int) -> GridResponse:
        response = await self.client.get(f"{self.base_url}/grids/{grid_id}")
        response.raise_for_status()
        return GridResponse.model_validate(response.json())

    async def update_grid(self, grid_id: int, grid: GridUpdateRequest) -> GridResponse:
        response = await self.client.put(f"{self.base_url}/grids/{grid_id}", json=grid.model_dump(exclude_none=True))
        response.raise_for_status()
        return GridResponse.model_validate(response.json())

    async def delete_grid(self, grid_id: int) -> None:
        response = await self.client.delete(f"{self.base_url}/grids/{grid_id}")
        response.raise_for_status()

    # Acquisition Grids
    async def get_acquisition_grids(self, acquisition_id: int) -> list[GridResponse]:
        response = await self.client.get(f"{self.base_url}/acquisitions/{acquisition_id}/grids")
        response.raise_for_status()
        return [GridResponse.model_validate(item) for item in response.json()]

    async def create_acquisition_grid(self, acquisition_id: int, grid: GridCreateRequest) -> GridResponse:
        response = await self.client.post(
            f"{self.base_url}/acquisitions/{acquisition_id}/grids", json=grid.model_dump(exclude_none=True)
        )
        response.raise_for_status()
        return GridResponse.model_validate(response.json())

    # Gridsquares
    async def get_gridsquares(self) -> list[GridSquareResponse]:
        response = await self.client.get(f"{self.base_url}/gridsquares")
        response.raise_for_status()
        return [GridSquareResponse.model_validate(item) for item in response.json()]

    async def create_gridsquare(self, gridsquare: GridSquareCreateRequest) -> GridSquareResponse:
        response = await self.client.post(f"{self.base_url}/gridsquares", json=gridsquare.model_dump(exclude_none=True))
        response.raise_for_status()
        return GridSquareResponse.model_validate(response.json())

    async def get_gridsquare(self, gridsquare_id: int) -> GridSquareResponse:
        response = await self.client.get(f"{self.base_url}/gridsquares/{gridsquare_id}")
        response.raise_for_status()
        return GridSquareResponse.model_validate(response.json())

    async def update_gridsquare(self, gridsquare_id: int, gridsquare: GridSquareUpdateRequest) -> GridSquareResponse:
        response = await self.client.put(
            f"{self.base_url}/gridsquares/{gridsquare_id}", json=gridsquare.model_dump(exclude_none=True)
        )
        response.raise_for_status()
        return GridSquareResponse.model_validate(response.json())

    async def delete_gridsquare(self, gridsquare_id: int) -> None:
        response = await self.client.delete(f"{self.base_url}/gridsquares/{gridsquare_id}")
        response.raise_for_status()

    # Grid Gridsquares
    async def get_grid_gridsquares(self, grid_id: int) -> list[GridSquareResponse]:
        response = await self.client.get(f"{self.base_url}/grids/{grid_id}/gridsquares")
        response.raise_for_status()
        return [GridSquareResponse.model_validate(item) for item in response.json()]

    async def create_grid_gridsquare(self, grid_id: int, gridsquare: GridSquareCreateRequest) -> GridSquareResponse:
        response = await self.client.post(
            f"{self.base_url}/grids/{grid_id}/gridsquares", json=gridsquare.model_dump(exclude_none=True)
        )
        response.raise_for_status()
        return GridSquareResponse.model_validate(response.json())

    # Foilholes
    async def get_foilholes(self) -> list[FoilHoleResponse]:
        response = await self.client.get(f"{self.base_url}/foilholes")
        response.raise_for_status()
        return [FoilHoleResponse.model_validate(item) for item in response.json()]

    async def create_foilhole(self, foilhole: FoilHoleCreateRequest) -> FoilHoleResponse:
        response = await self.client.post(f"{self.base_url}/foilholes", json=foilhole.model_dump(exclude_none=True))
        response.raise_for_status()
        return FoilHoleResponse.model_validate(response.json())

    async def get_foilhole(self, foilhole_id: int) -> FoilHoleResponse:
        response = await self.client.get(f"{self.base_url}/foilholes/{foilhole_id}")
        response.raise_for_status()
        return FoilHoleResponse.model_validate(response.json())

    async def update_foilhole(self, foilhole_id: int, foilhole: FoilHoleUpdateRequest) -> FoilHoleResponse:
        response = await self.client.put(
            f"{self.base_url}/foilholes/{foilhole_id}", json=foilhole.model_dump(exclude_none=True)
        )
        response.raise_for_status()
        return FoilHoleResponse.model_validate(response.json())

    async def delete_foilhole(self, foilhole_id: int) -> None:
        response = await self.client.delete(f"{self.base_url}/foilholes/{foilhole_id}")
        response.raise_for_status()

    # Gridsquare Foilholes
    async def get_gridsquare_foilholes(self, gridsquare_id: int) -> list[FoilHoleResponse]:
        response = await self.client.get(f"{self.base_url}/gridsquares/{gridsquare_id}/foilholes")
        response.raise_for_status()
        return [FoilHoleResponse.model_validate(item) for item in response.json()]

    async def create_gridsquare_foilhole(self, gridsquare_id: int, foilhole: FoilHoleCreateRequest) -> FoilHoleResponse:
        response = await self.client.post(
            f"{self.base_url}/gridsquares/{gridsquare_id}/foilholes", json=foilhole.model_dump(exclude_none=True)
        )
        response.raise_for_status()
        return FoilHoleResponse.model_validate(response.json())

    # Micrographs
    async def get_micrographs(self) -> list[MicrographResponse]:
        response = await self.client.get(f"{self.base_url}/micrographs")
        response.raise_for_status()
        return [MicrographResponse.model_validate(item) for item in response.json()]

    async def create_micrograph(self, micrograph: MicrographCreateRequest) -> MicrographResponse:
        response = await self.client.post(f"{self.base_url}/micrographs", json=micrograph.model_dump(exclude_none=True))
        response.raise_for_status()
        return MicrographResponse.model_validate(response.json())

    async def get_micrograph(self, micrograph_id: int) -> MicrographResponse:
        response = await self.client.get(f"{self.base_url}/micrographs/{micrograph_id}")
        response.raise_for_status()
        return MicrographResponse.model_validate(response.json())

    async def update_micrograph(self, micrograph_id: int, micrograph: MicrographUpdateRequest) -> MicrographResponse:
        response = await self.client.put(
            f"{self.base_url}/micrographs/{micrograph_id}", json=micrograph.model_dump(exclude_none=True)
        )
        response.raise_for_status()
        return MicrographResponse.model_validate(response.json())

    async def delete_micrograph(self, micrograph_id: int) -> None:
        response = await self.client.delete(f"{self.base_url}/micrographs/{micrograph_id}")
        response.raise_for_status()

    # Foilhole Micrographs
    async def get_foilhole_micrographs(self, foilhole_id: int) -> list[MicrographResponse]:
        response = await self.client.get(f"{self.base_url}/foilholes/{foilhole_id}/micrographs")
        response.raise_for_status()
        return [MicrographResponse.model_validate(item) for item in response.json()]

    async def create_foilhole_micrograph(
        self, foilhole_id: int, micrograph: MicrographCreateRequest
    ) -> MicrographResponse:
        response = await self.client.post(
            f"{self.base_url}/foilholes/{foilhole_id}/micrographs", json=micrograph.model_dump(exclude_none=True)
        )
        response.raise_for_status()
        return MicrographResponse.model_validate(response.json())


# ============ Usage Example ============
# import asyncio
# from src.epu_data_intake.core_api_client import (
#     SmartEMClient,
#     AcquisitionCreateRequest,
#     AcquisitionStatus,
#     GridCreateRequest,
#     GridStatus
# )
#
#
# async def main():
#     # Initialize the client with your API base URL
#     async with SmartEMClient("https://api.smartem.example.com") as client:
#         # Create a new acquisition
#         new_acquisition = AcquisitionCreateRequest(
#             name="Test Acquisition 1",
#             status=AcquisitionStatus.PLANNED,
#             storage_path="/path/to/storage"
#         )
#
#         created_acquisition = await client.create_acquisition(new_acquisition)
#         print(f"Created acquisition: {created_acquisition.id} - {created_acquisition.name}")
#
#         # Get all acquisitions
#         all_acquisitions = await client.get_acquisitions()
#         print(f"Total acquisitions: {len(all_acquisitions)}")
#
#         # Create a grid for this acquisition
#         new_grid = GridCreateRequest(
#             name="Grid 1",
#             acquisition_id=created_acquisition.id,
#             status=GridStatus.NONE
#         )
#
#         grid = await client.create_acquisition_grid(created_acquisition.id, new_grid)
#         print(f"Created grid: {grid.id} - {grid.name}")
#
#         # Get grids for this acquisition
#         acquisition_grids = await client.get_acquisition_grids(created_acquisition.id)
#         print(f"Total grids for acquisition {created_acquisition.id}: {len(acquisition_grids)}")
#
#
# if __name__ == "__main__":
#     asyncio.run(main())
