import asyncio
import logging
import traceback
import json
import httpx

from pydantic import BaseModel

from src.smartem_decisions.model.http_request import (
    AcquisitionCreateRequest,
    AtlasCreateRequest,
    AtlasTileCreateRequest,
    GridCreateRequest,
    GridSquareCreateRequest,
    FoilHoleCreateRequest,
    MicrographCreateRequest,
)
from src.smartem_decisions.model.http_response import (
    AcquisitionResponse,
    AtlasResponse,
    AtlasTileResponse,
    GridResponse,
    GridSquareResponse,
    FoilHoleResponse,
    MicrographResponse,
)
from src.epu_data_intake.model.schemas import (
    AcquisitionData,
    GridData,
    GridSquareData,
    FoilHoleData,
    MicrographData,
    AtlasData,
    AtlasTileData,
)

from src.smartem_decisions.model.entity_status import (
    AcquisitionStatus,
    GridStatus,
    GridSquareStatus,
    FoilHoleStatus,
    MicrographStatus,
)

# TODO look for a way to remove the extra bloat - conversion from EntityData type to EntityCreateRequest type
#  if at all possible

class EntityConverter:
    """
    Handles conversions between EPU data model and API request/response models.
    Separating this conversion logic keeps the main client code cleaner.
    """

    @staticmethod
    def acquisition_to_request(entity: AcquisitionData) -> AcquisitionCreateRequest:
        """Convert EPU session data to acquisition request model"""
        return AcquisitionCreateRequest(
            uuid=entity.uuid,
            # TODO check if natural `id` should also be included
            name=entity.name,
            start_time=entity.start_time,
            storage_path=entity.storage_path,
            atlas_path=entity.atlas_path,
            clustering_mode=entity.clustering_mode,
            clustering_radius=entity.clustering_radius,
            status=AcquisitionStatus.STARTED,
        )

    @staticmethod
    def grid_to_request(entity: GridData) -> GridCreateRequest:
        """Convert Grid data to grid request model"""
        return GridCreateRequest(
            uuid=entity.uuid,
            status=GridStatus.NONE,
            name=entity.acquisition_data.name if entity.acquisition_data else "Unknown",
            acquisition_uuid=entity.acquisition_data.uuid,
            data_dir=str(entity.data_dir) if entity.data_dir else None,
            atlas_dir=str(entity.atlas_dir) if entity.atlas_dir else None,
        )

    @staticmethod
    def gridsquare_to_request(entity: GridSquareData) -> GridSquareCreateRequest:
        """Convert GridSquareData to grid square request model"""
        metadata = entity.metadata
        manifest = entity.manifest
        return GridSquareCreateRequest(
            grid_uuid=entity.grid_uuid,
            uuid=entity.uuid,
            data_dir=str(entity.data_dir) if entity.data_dir else None,
            atlas_node_id=metadata.atlas_node_id if metadata else None,
            state=metadata.state if metadata else None,
            rotation=metadata.rotation if metadata else None,
            image_path=str(metadata.image_path) if metadata and metadata.image_path else None,
            selected=metadata.selected if metadata else None,
            unusable=metadata.unusable if metadata else None,
            stage_position_x=metadata.stage_position.x if metadata and metadata.stage_position else None,
            stage_position_y=metadata.stage_position.y if metadata and metadata.stage_position else None,
            stage_position_z=metadata.stage_position.z if metadata and metadata.stage_position else None,
            acquisition_datetime=manifest.acquisition_datetime if manifest else None,
            defocus=manifest.defocus if manifest else None,
            magnification=manifest.magnification if manifest else None,
            pixel_size=manifest.pixel_size if manifest else None,
            detector_name=manifest.detector_name if manifest else None,
            applied_defocus=manifest.applied_defocus if manifest else None,
        )

    @staticmethod
    def foilhole_to_request(entity: FoilHoleData) -> FoilHoleCreateRequest:
        """Convert FoilHoleData to foil hole request model"""
        return FoilHoleCreateRequest(
            uuid=entity.uuid,
            id=entity.id,
            gridsquare_uuid=entity.gridsquare_uuid,
            center_x=entity.center_x,
            center_y=entity.center_y,
            quality=entity.quality,
            rotation=entity.rotation,
            size_width=entity.size_width,
            size_height=entity.size_height,
            x_location=None,  # Map from metadata if available
            y_location=None,  # Map from metadata if available
            x_stage_position=None,  # Map from metadata if available
            y_stage_position=None,  # Map from metadata if available
            diameter=None,  # Map from metadata if available
        )

    @staticmethod
    def micrograph_to_request(entity: MicrographData) -> MicrographCreateRequest:
        """Convert MicrographData to micrograph request model"""
        manifest = entity.manifest
        return MicrographCreateRequest(
            uuid=entity.uuid,
            foilhole_uuid=entity.foilhole_uuid,
            # micrograph_id=entity.id, TODO
            location_id=entity.location_id,
            high_res_path=str(entity.high_res_path) if entity.high_res_path else None,
            manifest_file=str(entity.manifest_file) if entity.manifest_file else None,
            acquisition_datetime=manifest.acquisition_datetime if manifest else None,
            defocus=manifest.defocus if manifest else None,
            detector_name=manifest.detector_name if manifest else None,
            energy_filter=manifest.energy_filter if manifest else None,
            phase_plate=manifest.phase_plate if manifest else None,
            image_size_x=manifest.image_size_x if manifest else None,
            image_size_y=manifest.image_size_y if manifest else None,
            binning_x=manifest.binning_x if manifest else None,
            binning_y=manifest.binning_y if manifest else None,
        )

    # TODO fix
    @staticmethod
    def atlas_to_request(entity: AtlasData) -> AtlasCreateRequest:
        """Convert AtlasData to atlas request model"""
        return AtlasCreateRequest(
            grid_uuid=entity.grid_uuid,
            name=entity.name,
            type=entity.type,
            path=str(entity.path) if entity.path else None,
            pixel_size=entity.pixel_size,
            width=entity.width,
            height=entity.height,
        )

    # TODO fix
    @staticmethod
    def atlas_tile_to_request(entity: AtlasTileData) -> AtlasTileCreateRequest:
        """Convert AtlasTileData to atlas tile request model"""
        return AtlasTileCreateRequest(
            atlas_uuid=entity.atlas_uuid,
            uuid=entity.uuid,
            id=entity.id,
            path=str(entity.path) if entity.path else None,
            position_x=entity.position_x,
            position_y=entity.position_y,
            width=entity.width,
            height=entity.height,
        )


class SmartEMAPIClient:
    """
    Unified SmartEM API client that provides both async and sync interfaces.

    This client handles all API communication with the SmartEM Core API,
    provides data conversion between EPU data models and API request/response models,
    and maintains a cache of entity IDs.
    """

    def __init__(self, base_url: str, timeout: float = 10.0, logger=None):
        """
        Initialize the SmartEM API client

        Args:
            base_url: Base URL for the API
            timeout: Request timeout in seconds
            logger: Optional custom logger instance
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._async_client = httpx.AsyncClient(timeout=timeout)
        self._logger = logger or logging.getLogger(__name__)

        # Configure logger if it's the default one
        if not logger:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self._logger.addHandler(handler)
            self._logger.setLevel(logging.INFO)

        self._loop = None
        self._logger.info(f"Initialized SmartEM API client with base URL: {base_url}")

    def close(self) -> None:
        """Close the sync client connection"""
        try:
            self._run_async(self._async_client.aclose())
        except Exception as e:
            self._logger.error(f"Error closing async client: {e}")

    async def aclose(self) -> None:
        """Close the async client connection"""
        await self._async_client.aclose()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.aclose()

    def _get_or_create_loop(self):
        """Get the current event loop or create a new one if necessary"""
        if self._loop is None:
            try:
                self._loop = asyncio.get_running_loop()
            except RuntimeError:
                self._loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self._loop)
        return self._loop

    def _run_async(self, coro):
        """Run an async coroutine in a sync context"""
        loop = self._get_or_create_loop()
        if loop.is_running():
            # If we're already in an async context, create a task
            return asyncio.create_task(coro)
        else:
            # Otherwise, run the coroutine to completion
            return loop.run_until_complete(coro)

    # Generic API request methods
    async def _request(
            self,
            method: str,
            endpoint: str,
            request_model: BaseModel | None = None,
            response_cls= None,
    ):
        """
        Make a generic API request

        Args:
            method: HTTP method (get, post, put, delete)
            endpoint: API endpoint path
            request_model: Optional request data model
            response_cls: Optional response class to parse the response

        Returns:
            Parsed response, list of responses, or None for delete operations

        Raises:
            httpx.HTTPStatusError: If the HTTP request returns an error status code
            httpx.RequestError: If there's a network error or timeout
            ValueError: If there's an error parsing the response
            Exception: For any other errors
        """
        url = f"{self.base_url}/{endpoint}"
        json_data = None

        if request_model:
            json_data = request_model.model_dump(exclude_none=True)
            self._logger.debug(f"Request data for {method} {url}: {json_data}")

        try:
            self._logger.debug(f"Making {method.upper()} request to {url}")
            response = await self._async_client.request(
                method,
                url,
                json=json_data
            )
            response.raise_for_status()

            # For delete operations, return None
            if method.lower() == "delete":
                self._logger.info(f"Successfully deleted resource at {url}")
                return None

            try:
                data = response.json()
                self._logger.debug(f"Response from {url}: {data}")

                # Parse response if response_cls is provided
                if response_cls:
                    try:
                        if isinstance(data, list):
                            return [response_cls.model_validate(item) for item in data]
                        else:
                            return response_cls.model_validate(data)
                    except Exception as e:
                        self._logger.error(f"Error validating response data from {url}: {e}")
                        self._logger.debug(f"Response data that failed validation: {data}")
                        raise ValueError(f"Invalid response data: {str(e)}")

                return data
            except json.JSONDecodeError as e:
                self._logger.error(f"Could not parse JSON response from {url}: {e}")
                self._logger.debug(f"Raw response: {response.text}")
                raise ValueError(f"Invalid JSON response: {str(e)}")

        except httpx.HTTPStatusError as e:
            status_code = e.response.status_code
            error_detail = None

            # Try to extract error details from the response
            try:
                error_response = e.response.json()
                error_detail = error_response.get("detail", str(e))
            except Exception:
                error_detail = e.response.text or str(e)

            self._logger.error(f"HTTP {status_code} error for {method.upper()} {url}: {error_detail}")
            raise

        except httpx.RequestError as e:
            self._logger.error(f"Request error for {method.upper()} {url}: {e}")
            self._logger.debug(f"Request error details: {traceback.format_exc()}")
            raise

        except Exception as e:
            self._logger.error(f"Unexpected error making request to {url}: {e}")
            self._logger.debug(f"Error details: {traceback.format_exc()}")
            raise

    # Entity-specific methods with both async and sync variants

    # Status and Health
    async def aget_status(self) -> dict[str, object]:
        """Get API status information (async)"""
        return await self._request("get", "status")

    def get_status(self) -> dict[str, object]:
        """Get API status information (sync)"""
        return self._run_async(self.aget_status())

    async def aget_health(self) -> dict[str, object]:
        """Get API health check information (async)"""
        return await self._request("get", "health")

    def get_health(self) -> dict[str, object]:
        """Get API health check information (sync)"""
        return self._run_async(self.aget_health())

    # Acquisitions
    async def aget_acquisitions(self) -> list[AcquisitionResponse]:
        """Get all acquisitions (async)"""
        return await self._request("get", "acquisitions", response_cls=AcquisitionResponse)

    def get_acquisitions(self) -> list[AcquisitionResponse]:
        """Get all acquisitions (sync)"""
        return self._run_async(self.aget_acquisitions())

    async def acreate_acquisition(self,
                                  acquisition: AcquisitionData) -> AcquisitionResponse:
        """Create a new acquisition (async)"""
        acquisition = EntityConverter.acquisition_to_request(acquisition)
        response = await self._request("post", "acquisitions", acquisition, AcquisitionResponse)
        return response

    def create_acquisition(self,
                           acquisition: AcquisitionData) -> AcquisitionResponse:
        """Create a new acquisition (sync)"""
        return self._run_async(self.acreate_acquisition(acquisition))

    async def aget_acquisition(self, acquisition_uuid: str) -> AcquisitionResponse:
        """Get a single acquisition by ID (async)"""
        return await self._request("get", f"acquisitions/{acquisition_uuid}", response_cls=AcquisitionResponse)

    def get_acquisition(self, acquisition_uuid: str) -> AcquisitionResponse:
        """Get a single acquisition by ID (sync)"""
        return self._run_async(self.aget_acquisition(acquisition_uuid))

    async def aupdate_acquisition(self, acquisition: AcquisitionData) -> AcquisitionResponse:
        """Update an acquisition (async)"""
        acquisition = EntityConverter.acquisition_to_request(acquisition)
        return await self._request("put", f"acquisitions/{acquisition.uuid}", acquisition, AcquisitionResponse)

    def update_acquisition(self, acquisition: AcquisitionData) -> AcquisitionResponse:
        """Update an acquisition (sync)"""
        return self._run_async(self.aupdate_acquisition(acquisition))

    async def adelete_acquisition(self, acquisition_uuid: str) -> None:
        """Delete an acquisition (async)"""
        await self._request("delete", f"acquisitions/{acquisition_uuid}")

    def delete_acquisition(self, acquisition_uuid: str) -> None:
        """Delete an acquisition (sync)"""
        return self._run_async(self.adelete_acquisition(acquisition_uuid))

    # Grids
    async def aget_grids(self) -> list[GridResponse]:
        """Get all grids (async)"""
        return await self._request("get", "grids", response_cls=GridResponse)

    def get_grids(self) -> list[GridResponse]:
        """Get all grids (sync)"""
        return self._run_async(self.aget_grids())

    async def aget_grid(self, grid_uuid: str) -> GridResponse:
        """Get a single grid by ID (async)"""
        return await self._request("get", f"grids/{grid_uuid}", response_cls=GridResponse)

    def get_grid(self, grid_uuid: str) -> GridResponse:
        """Get a single grid by ID (sync)"""
        return self._run_async(self.aget_grid(grid_uuid))

    async def aupdate_grid(self, grid: GridData) -> GridResponse:
        """Update a grid (async)"""
        grid = EntityConverter.grid_to_request(grid)
        return await self._request("put", f"grids/{grid.uuid}", grid, GridResponse)

    def update_grid(self, grid: GridData) -> GridResponse:
        """Update a grid (sync)"""
        return self._run_async(self.aupdate_grid(grid))

    async def adelete_grid(self, grid_uuid: str) -> None:
        """Delete a grid (async)"""
        await self._request("delete", f"grids/{grid_uuid}")

    def delete_grid(self, grid_uuid: str) -> None:
        """Delete a grid (sync)"""
        return self._run_async(self.adelete_grid(grid_uuid))

    async def aget_acquisition_grids(self, acquisition_uuid: str) -> list[GridResponse]:
        """Get all grids for a specific acquisition (async)"""
        return await self._request("get", f"acquisitions/{acquisition_uuid}/grids", response_cls=GridResponse)

    def get_acquisition_grids(self, acquisition_uuid: str) -> list[GridResponse]:
        """Get all grids for a specific acquisition (sync)"""
        return self._run_async(self.aget_acquisition_grids(acquisition_uuid))

    async def acreate_acquisition_grid(
            self,
            grid: GridData
    ) -> GridResponse:
        """Create a new grid for a specific acquisition (async)"""
        grid = EntityConverter.grid_to_request(grid)

        response = await self._request(
            "post",
            f"acquisitions/{grid.acquisition_uuid}/grids",
            grid,
            GridResponse
        )
        return response

    def create_acquisition_grid(
            self,
            grid: GridData
    ) -> GridResponse:
        """Create a new grid for a specific acquisition (sync)"""
        return self._run_async(self.acreate_acquisition_grid(grid))

    # Atlas
    async def aget_atlases(self) -> list[AtlasResponse]:
        """Get all atlases (async)"""
        return await self._request("get", "atlases", response_cls=AtlasResponse)

    def get_atlases(self) -> list[AtlasResponse]:
        """Get all atlases (sync)"""
        return self._run_async(self.aget_atlases())

    async def aget_atlas(self, atlas_uuid: str) -> AtlasResponse:
        """Get a single atlas by ID (async)"""
        return await self._request("get", f"atlases/{atlas_uuid}", response_cls=AtlasResponse)

    def get_atlas(self, atlas_uuid: str) -> AtlasResponse:
        """Get a single atlas by ID (sync)"""
        return self._run_async(self.aget_atlas(atlas_uuid))

    async def aupdate_atlas(self, atlas: AtlasData) -> AtlasResponse:
        """Update an atlas (async)"""
        atlas = EntityConverter.atlas_to_request(atlas)
        return await self._request("put", f"atlases/{atlas.uuid}", atlas, AtlasResponse)

    def update_atlas(self, atlas: AtlasData) -> AtlasResponse:
        """Update an atlas (sync)"""
        return self._run_async(self.aupdate_atlas(atlas))

    async def adelete_atlas(self, atlas_uuid: str) -> None:
        """Delete an atlas (async)"""
        await self._request("delete", f"atlases/{atlas_uuid}")

    def delete_atlas(self, atlas_uuid: str) -> None:
        """Delete an atlas (sync)"""
        return self._run_async(self.adelete_atlas(atlas_uuid))

    async def aget_grid_atlas(self, grid_uuid: str) -> AtlasResponse:
        """Get the atlas for a specific grid (async)"""
        return await self._request("get", f"grids/{grid_uuid}/atlas", response_cls=AtlasResponse)

    def get_grid_atlas(self, grid_uuid: str) -> AtlasResponse:
        """Get the atlas for a specific grid (sync)"""
        return self._run_async(self.aget_grid_atlas(grid_uuid))

    async def acreate_grid_atlas(
            self,
            atlas: AtlasData
    ) -> AtlasResponse:
        """Create a new atlas for a grid (async)"""
        # Convert AtlasData to AtlasCreateRequest if needed
        atlas = EntityConverter.atlas_to_request(atlas)

        response = await self._request(
            "post",
            f"grids/{atlas.grid_uuid}/atlas",
            atlas,
            AtlasResponse
        )
        return response

    def create_grid_atlas(
            self,
            atlas: AtlasData
    ) -> AtlasResponse:
        """Create a new atlas for a grid (sync)"""
        return self._run_async(self.acreate_grid_atlas(atlas))

    # Atlas Tiles
    async def aget_atlas_tiles(self) -> list[AtlasTileResponse]:
        """Get all atlas tiles (async)"""
        return await self._request("get", "atlas-tiles", response_cls=AtlasTileResponse)

    def get_atlas_tiles(self) -> list[AtlasTileResponse]:
        """Get all atlas tiles (sync)"""
        return self._run_async(self.aget_atlas_tiles())

    async def aget_atlas_tile(self, tile_uuid: str) -> AtlasTileResponse:
        """Get a single atlas tile by ID (async)"""
        return await self._request("get", f"atlas-tiles/{tile_uuid}", response_cls=AtlasTileResponse)

    def get_atlas_tile(self, tile_uuid: str) -> AtlasTileResponse:
        """Get a single atlas tile by ID (sync)"""
        return self._run_async(self.aget_atlas_tile(tile_uuid))

    async def aupdate_atlas_tile(self, tile: AtlasTileData) -> AtlasTileResponse:
        """Update an atlas tile (async)"""
        tile = EntityConverter.atlas_tile_to_request(tile)
        return await self._request("put", f"atlas-tiles/{tile.uuid}", tile, AtlasTileResponse)

    def update_atlas_tile(self, tile: AtlasTileData) -> AtlasTileResponse:
        """Update an atlas tile (sync)"""
        return self._run_async(self.aupdate_atlas_tile(tile))

    async def adelete_atlas_tile(self, tile_uuid: str) -> None:
        """Delete an atlas tile (async)"""
        await self._request("delete", f"atlas-tiles/{tile_uuid}")

    def delete_atlas_tile(self, tile_uuid: str) -> None:
        """Delete an atlas tile (sync)"""
        return self._run_async(self.adelete_atlas_tile(tile_uuid))

    async def aget_atlas_tiles_by_atlas(self, atlas_uuid: str) -> list[AtlasTileResponse]:
        """Get all tiles for a specific atlas (async)"""
        return await self._request("get", f"atlases/{atlas_uuid}/tiles", response_cls=AtlasTileResponse)

    def get_atlas_tiles_by_atlas(self, atlas_uuid: str) -> list[AtlasTileResponse]:
        """Get all tiles for a specific atlas (sync)"""
        return self._run_async(self.aget_atlas_tiles_by_atlas(atlas_uuid))

    async def acreate_atlas_tile_for_atlas(
            self,
            tile: AtlasTileData
    ) -> AtlasTileResponse:
        """Create a new tile for a specific atlas (async)"""
        tile = EntityConverter.atlas_tile_to_request(tile)
        response = await self._request(
            "post",
            f"atlases/{tile.atlas_uuid}/tiles",
            tile,
            AtlasTileResponse
        )
        return response

    def create_atlas_tile_for_atlas(
            self,
            tile: AtlasTileData
    ) -> AtlasTileResponse:
        """Create a new tile for a specific atlas (sync)"""
        return self._run_async(self.acreate_atlas_tile_for_atlas(tile))

    # GridSquares
    async def aget_gridsquares(self) -> list[GridSquareResponse]:
        """Get all grid squares (async)"""
        return await self._request("get", "gridsquares", response_cls=GridSquareResponse)

    def get_gridsquares(self) -> list[GridSquareResponse]:
        """Get all grid squares (sync)"""
        return self._run_async(self.aget_gridsquares())

    async def aget_gridsquare(self, gridsquare_uuid: str) -> GridSquareResponse:
        """Get a single grid square by ID (async)"""
        return await self._request("get", f"gridsquares/{gridsquare_uuid}", response_cls=GridSquareResponse)

    def get_gridsquare(self, gridsquare_uuid: str) -> GridSquareResponse:
        """Get a single grid square by ID (sync)"""
        return self._run_async(self.aget_gridsquare(gridsquare_uuid))

    async def aupdate_gridsquare(self, gridsquare: GridSquareData) -> GridSquareResponse:
        """Update a grid square (async)"""
        gridsquare = EntityConverter.gridsquare_to_request(gridsquare)
        return await self._request("put", f"gridsquares/{gridsquare.uuid}", gridsquare, GridSquareResponse)

    def update_gridsquare(self, gridsquare: GridSquareData) -> GridSquareResponse:
        """Update a grid square (sync)"""
        return self._run_async(self.aupdate_gridsquare(gridsquare))

    async def adelete_gridsquare(self, gridsquare_uuid: str) -> None:
        """Delete a grid square (async)"""
        await self._request("delete", f"gridsquares/{gridsquare_uuid}")

    def delete_gridsquare(self, gridsquare_uuid: str) -> None:
        """Delete a grid square (sync)"""
        return self._run_async(self.adelete_gridsquare(gridsquare_uuid))

    async def aget_grid_gridsquares(self, grid_uuid: str) -> list[GridSquareResponse]:
        """Get all grid squares for a specific grid (async)"""
        return await self._request("get", f"grids/{grid_uuid}/gridsquares", response_cls=GridSquareResponse)

    def get_grid_gridsquares(self, grid_uuid: str) -> list[GridSquareResponse]:
        """Get all grid squares for a specific grid (sync)"""
        return self._run_async(self.aget_grid_gridsquares(grid_uuid))

    async def acreate_grid_gridsquare(
            self,
            gridsquare: GridSquareData
    ) -> GridSquareResponse:
        """Create a new grid square for a specific grid (async)"""
        # Convert GridSquareData to GridSquareCreateRequest if needed
        gridsquare = EntityConverter.gridsquare_to_request(gridsquare)

        response = await self._request(
            "post",
            f"grids/{gridsquare.grid_uuid}/gridsquares",
            gridsquare,
            GridSquareResponse
        )
        return response

    def create_grid_gridsquare(
            self,
            gridsquare: GridSquareData
    ) -> GridSquareResponse:
        """Create a new grid square for a specific grid (sync)"""
        return self._run_async(self.acreate_grid_gridsquare(gridsquare))

    # FoilHoles
    async def aget_foilholes(self) -> list[FoilHoleResponse]:
        """Get all foil holes (async)"""
        return await self._request("get", "foilholes", response_cls=FoilHoleResponse)

    def get_foilholes(self) -> list[FoilHoleResponse]:
        """Get all foil holes (sync)"""
        return self._run_async(self.aget_foilholes())

    async def aget_foilhole(self, foilhole_uuid: str) -> FoilHoleResponse:
        """Get a single foil hole by ID (async)"""
        return await self._request("get", f"foilholes/{foilhole_uuid}", response_cls=FoilHoleResponse)

    def get_foilhole(self, foilhole_uuid: str) -> FoilHoleResponse:
        """Get a single foil hole by ID (sync)"""
        return self._run_async(self.aget_foilhole(foilhole_uuid))

    async def aupdate_foilhole(self, foilhole: FoilHoleData) -> FoilHoleResponse:
        """Update a foil hole (async)"""
        foilhole = EntityConverter.foilhole_to_request(foilhole)
        return await self._request("put", f"foilholes/{foilhole.uuid}", foilhole, FoilHoleResponse)

    def update_foilhole(self, foilhole: FoilHoleData) -> FoilHoleResponse:
        """Update a foil hole (sync)"""
        return self._run_async(self.aupdate_foilhole(foilhole))

    async def adelete_foilhole(self, foilhole_uuid: str) -> None:
        """Delete a foil hole (async)"""
        await self._request("delete", f"foilholes/{foilhole_uuid}")

    def delete_foilhole(self, foilhole_uuid: str) -> None:
        """Delete a foil hole (sync)"""
        return self._run_async(self.adelete_foilhole(foilhole_uuid))

    async def aget_gridsquare_foilholes(self, gridsquare_uuid: str) -> list[FoilHoleResponse]:
        """Get all foil holes for a specific grid square (async)"""
        return await self._request("get", f"gridsquares/{gridsquare_uuid}/foilholes", response_cls=FoilHoleResponse)

    def get_gridsquare_foilholes(self, gridsquare_uuid: str) -> list[FoilHoleResponse]:
        """Get all foil holes for a specific grid square (sync)"""
        return self._run_async(self.aget_gridsquare_foilholes(gridsquare_uuid))

    async def acreate_gridsquare_foilhole(
            self,
            foilhole: FoilHoleData
    ) -> FoilHoleResponse:
        """Create a new foil hole for a specific grid square (async)"""
        foilhole = EntityConverter.foilhole_to_request(foilhole)
        response = await self._request(
            "post",
            f"gridsquares/{foilhole.gridsquare_uuid}/foilholes",
            foilhole,
            FoilHoleResponse
        )
        return response

    def create_gridsquare_foilhole(
            self,
            foilhole: FoilHoleData
    ) -> FoilHoleResponse:
        """Create a new foil hole for a specific grid square (sync)"""
        return self._run_async(self.acreate_gridsquare_foilhole(foilhole))

    # Micrographs
    async def aget_micrographs(self) -> list[MicrographResponse]:
        """Get all micrographs (async)"""
        return await self._request("get", "micrographs", response_cls=MicrographResponse)

    def get_micrographs(self) -> list[MicrographResponse]:
        """Get all micrographs (sync)"""
        return self._run_async(self.aget_micrographs())

    async def aget_micrograph(self, micrograph_uuid: str) -> MicrographResponse:
        """Get a single micrograph by ID (async)"""
        return await self._request("get", f"micrographs/{micrograph_uuid}", response_cls=MicrographResponse)

    def get_micrograph(self, micrograph_uuid: str) -> MicrographResponse:
        """Get a single micrograph by ID (sync)"""
        return self._run_async(self.aget_micrograph(micrograph_uuid))

    async def aupdate_micrograph(self, micrograph: MicrographData) -> MicrographResponse:
        """Update a micrograph (async)"""
        micrograph = EntityConverter.micrograph_to_request(micrograph)
        return await self._request("put", f"micrographs/{micrograph.uuid}", micrograph, MicrographResponse)

    def update_micrograph(self, micrograph: MicrographData) -> MicrographResponse:
        """Update a micrograph (sync)"""
        return self._run_async(self.aupdate_micrograph(micrograph))

    async def adelete_micrograph(self, micrograph_id: str) -> None:
        """Delete a micrograph (async)"""
        await self._request("delete", f"micrographs/{micrograph_id}")

    def delete_micrograph(self, micrograph_id: str) -> None:
        """Delete a micrograph (sync)"""
        return self._run_async(self.adelete_micrograph(micrograph_id))

    async def aget_foilhole_micrographs(self, foilhole_id: str) -> list[MicrographResponse]:
        """Get all micrographs for a specific foil hole (async)"""
        return await self._request("get", f"foilholes/{foilhole_id}/micrographs", response_cls=MicrographResponse)

    def get_foilhole_micrographs(self, foilhole_id: str) -> list[MicrographResponse]:
        """Get all micrographs for a specific foil hole (sync)"""
        return self._run_async(self.aget_foilhole_micrographs(foilhole_id))

    async def acreate_foilhole_micrograph(
            self,
            micrograph: MicrographData
    ) -> MicrographResponse:
        """Create a new micrograph for a specific foil hole (async)"""
        micrograph = EntityConverter.micrograph_to_request(micrograph)
        response = await self._request(
            "post",
            f"foilholes/{micrograph.foilhole_uuid}/micrographs",
            micrograph,
            MicrographResponse
        )
        return response

    def create_foilhole_micrograph(
            self,
            micrograph: MicrographData
    ) -> MicrographResponse:
        """Create a new micrograph for a specific foil hole (sync)"""
        return self._run_async(self.acreate_foilhole_micrograph(micrograph))
