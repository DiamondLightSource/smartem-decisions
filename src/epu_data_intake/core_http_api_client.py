import asyncio
import logging
import functools
import traceback
import json
from typing import Any, Dict, List, Optional, TypeVar, Type, Generic, Union, Callable, cast, overload
import httpx
from enum import Enum
from datetime import datetime

from pydantic import BaseModel

from src.smartem_decisions.model.http_request import (
    AcquisitionCreateRequest,
    AcquisitionUpdateRequest,
    AtlasCreateRequest,
    AtlasUpdateRequest,
    AtlasTileCreateRequest,
    AtlasTileUpdateRequest,
    GridCreateRequest,
    GridUpdateRequest,
    GridSquareCreateRequest,
    GridSquareUpdateRequest,
    FoilHoleCreateRequest,
    FoilHoleUpdateRequest,
    MicrographCreateRequest,
    MicrographUpdateRequest,
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
from src.epu_data_intake.data_model import (
    EpuSessionData,
    Grid,
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

T = TypeVar("T")
RequestT = TypeVar("RequestT", bound=BaseModel)
ResponseT = TypeVar("ResponseT", bound=BaseModel)
EntityT = TypeVar("EntityT")


class EntityConverter:
    """
    Handles conversions between EPU data model and API request/response models.
    Separating this conversion logic keeps the main client code cleaner.
    """

    @staticmethod
    def epu_session_to_request(entity: EpuSessionData) -> AcquisitionCreateRequest:
        """Convert EPU session data to acquisition request model"""
        return AcquisitionCreateRequest(
            id=entity.id,
            name=entity.name,
            start_time=entity.start_time,
            storage_path=entity.storage_path,
            atlas_path=entity.atlas_path,
            clustering_mode=entity.clustering_mode,
            clustering_radius=entity.clustering_radius,
            status=AcquisitionStatus.STARTED,
        )

    @staticmethod
    def grid_to_request(entity: Grid, acquisition_id: str) -> GridCreateRequest:
        """Convert Grid data to grid request model"""
        return GridCreateRequest(
            id=entity.id,
            name=entity.session_data.name if entity.session_data else "Unknown",
            acquisition_id=acquisition_id,
            data_dir=str(entity.data_dir) if entity.data_dir else None,
            atlas_dir=str(entity.atlas_dir) if entity.atlas_dir else None,
        )

    @staticmethod
    def gridsquare_to_request(entity: GridSquareData, grid_id: str) -> GridSquareCreateRequest:
        """Convert GridSquareData to grid square request model"""
        metadata = entity.metadata
        manifest = entity.manifest
        return GridSquareCreateRequest(
            grid_id=grid_id,
            gridsquare_id=entity.id,
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
    def foilhole_to_request(entity: FoilHoleData, gridsquare_id: str) -> FoilHoleCreateRequest:
        """Convert FoilHoleData to foil hole request model"""
        return FoilHoleCreateRequest(
            gridsquare_id=gridsquare_id,
            foilhole_id=entity.id,
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
    def micrograph_to_request(entity: MicrographData, foilhole_id: str) -> MicrographCreateRequest:
        """Convert MicrographData to micrograph request model"""
        manifest = entity.manifest
        return MicrographCreateRequest(
            foilhole_id=foilhole_id,
            micrograph_id=entity.id,
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

    @staticmethod
    def atlas_to_request(entity: AtlasData, grid_id: str) -> AtlasCreateRequest:
        """Convert AtlasData to atlas request model"""
        return AtlasCreateRequest(
            grid_id=grid_id,
            name=entity.name,
            type=entity.type,
            path=str(entity.path) if entity.path else None,
            pixel_size=entity.pixel_size,
            width=entity.width,
            height=entity.height,
        )

    @staticmethod
    def atlas_tile_to_request(entity: AtlasTileData, atlas_id: str) -> AtlasTileCreateRequest:
        """Convert AtlasTileData to atlas tile request model"""
        return AtlasTileCreateRequest(
            atlas_id=atlas_id,
            tile_id=entity.id,
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

        # Cache to map between entity IDs and database IDs
        self._id_map = {
            "acquisition": {},
            "grid": {},
            "gridsquare": {},
            "foilhole": {},
            "micrograph": {},
            "atlas": {},
            "atlas_tile": {},
        }

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

    def _sync_wrap(async_method: Callable) -> Callable:
        """Decorator to wrap async methods to provide sync variants"""

        @functools.wraps(async_method)
        def wrapper(self, *args, **kwargs):
            return self._run_async(async_method(self, *args, **kwargs))

        return wrapper

    # Store entity ID mappings
    def _store_entity_id_mapping(self, entity_type: str, entity_id: str, db_id: str) -> None:
        """Store a mapping from entity ID to database ID"""
        self._id_map[entity_type][entity_id] = db_id
        self._logger.debug(f"Stored ID mapping: {entity_type}/{entity_id} -> {db_id}")

    def _get_db_id(self, entity_type: str, entity_id: str) -> Optional[str]:
        """Get database ID for an entity ID"""
        return self._id_map[entity_type].get(entity_id)

    # Generic API request methods
    async def _request(
            self,
            method: str,
            endpoint: str,
            request_model: Optional[BaseModel] = None,
            response_cls: Optional[Type[ResponseT]] = None,
    ) -> Union[ResponseT, List[ResponseT], Dict[str, Any], None]:
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
    async def aget_status(self) -> Dict[str, Any]:
        """Get API status information (async)"""
        return await self._request("get", "status")

    get_status = _sync_wrap(aget_status)

    async def aget_health(self) -> Dict[str, Any]:
        """Get API health check information (async)"""
        return await self._request("get", "health")

    get_health = _sync_wrap(aget_health)

    # Acquisitions
    async def aget_acquisitions(self) -> List[AcquisitionResponse]:
        """Get all acquisitions (async)"""
        return await self._request("get", "acquisitions", response_cls=AcquisitionResponse)

    get_acquisitions = _sync_wrap(aget_acquisitions)

    async def acreate_acquisition(self,
                                  acquisition: Union[AcquisitionCreateRequest, EpuSessionData]) -> AcquisitionResponse:
        """Create a new acquisition (async)"""
        # Convert EpuSessionData to AcquisitionCreateRequest if needed
        if isinstance(acquisition, EpuSessionData):
            acquisition = EntityConverter.epu_session_to_request(acquisition)

        response = await self._request("post", "acquisitions", acquisition, AcquisitionResponse)
        # Store ID mapping
        self._store_entity_id_mapping("acquisition", acquisition.id, response.id)
        return response

    create_acquisition = _sync_wrap(acreate_acquisition)

    async def aget_acquisition(self, acquisition_id: str) -> AcquisitionResponse:
        """Get a single acquisition by ID (async)"""
        return await self._request("get", f"acquisitions/{acquisition_id}", response_cls=AcquisitionResponse)

    get_acquisition = _sync_wrap(aget_acquisition)

    async def aupdate_acquisition(self, acquisition_id: str,
                                  acquisition: AcquisitionUpdateRequest) -> AcquisitionResponse:
        """Update an acquisition (async)"""
        return await self._request("put", f"acquisitions/{acquisition_id}", acquisition, AcquisitionResponse)

    update_acquisition = _sync_wrap(aupdate_acquisition)

    async def adelete_acquisition(self, acquisition_id: str) -> None:
        """Delete an acquisition (async)"""
        await self._request("delete", f"acquisitions/{acquisition_id}")

    delete_acquisition = _sync_wrap(adelete_acquisition)

    # Grids
    async def aget_grids(self) -> List[GridResponse]:
        """Get all grids (async)"""
        return await self._request("get", "grids", response_cls=GridResponse)

    get_grids = _sync_wrap(aget_grids)

    async def aget_grid(self, grid_id: str) -> GridResponse:
        """Get a single grid by ID (async)"""
        return await self._request("get", f"grids/{grid_id}", response_cls=GridResponse)

    get_grid = _sync_wrap(aget_grid)

    async def aupdate_grid(self, grid_id: str, grid: GridUpdateRequest) -> GridResponse:
        """Update a grid (async)"""
        return await self._request("put", f"grids/{grid_id}", grid, GridResponse)

    update_grid = _sync_wrap(aupdate_grid)

    async def adelete_grid(self, grid_id: str) -> None:
        """Delete a grid (async)"""
        await self._request("delete", f"grids/{grid_id}")

    delete_grid = _sync_wrap(adelete_grid)

    async def aget_acquisition_grids(self, acquisition_id: str) -> List[GridResponse]:
        """Get all grids for a specific acquisition (async)"""
        return await self._request("get", f"acquisitions/{acquisition_id}/grids", response_cls=GridResponse)

    get_acquisition_grids = _sync_wrap(aget_acquisition_grids)

    async def acreate_acquisition_grid(
            self,
            acquisition_id: str,
            grid: Union[GridCreateRequest, Grid]
    ) -> GridResponse:
        """Create a new grid for a specific acquisition (async)"""
        # Convert Grid to GridCreateRequest if needed
        if isinstance(grid, Grid):
            grid_request = EntityConverter.grid_to_request(grid, acquisition_id)
        else:
            grid_request = grid

        response = await self._request(
            "post",
            f"acquisitions/{acquisition_id}/grids",
            grid_request,
            GridResponse
        )
        # Store ID mapping
        self._store_entity_id_mapping("grid", grid_request.id, response.id)
        return response

    create_acquisition_grid = _sync_wrap(acreate_acquisition_grid)

    # Atlas
    async def aget_atlases(self) -> List[AtlasResponse]:
        """Get all atlases (async)"""
        return await self._request("get", "atlases", response_cls=AtlasResponse)

    get_atlases = _sync_wrap(aget_atlases)

    async def aget_atlas(self, atlas_id: str) -> AtlasResponse:
        """Get a single atlas by ID (async)"""
        return await self._request("get", f"atlases/{atlas_id}", response_cls=AtlasResponse)

    get_atlas = _sync_wrap(aget_atlas)

    async def aupdate_atlas(self, atlas_id: str, atlas: AtlasUpdateRequest) -> AtlasResponse:
        """Update an atlas (async)"""
        return await self._request("put", f"atlases/{atlas_id}", atlas, AtlasResponse)

    update_atlas = _sync_wrap(aupdate_atlas)

    async def adelete_atlas(self, atlas_id: str) -> None:
        """Delete an atlas (async)"""
        await self._request("delete", f"atlases/{atlas_id}")

    delete_atlas = _sync_wrap(adelete_atlas)

    async def aget_grid_atlas(self, grid_id: str) -> AtlasResponse:
        """Get the atlas for a specific grid (async)"""
        return await self._request("get", f"grids/{grid_id}/atlas", response_cls=AtlasResponse)

    get_grid_atlas = _sync_wrap(aget_grid_atlas)

    async def acreate_grid_atlas(
            self,
            grid_id: str,
            atlas: Union[AtlasCreateRequest, AtlasData]
    ) -> AtlasResponse:
        """Create a new atlas for a grid (async)"""
        # Convert AtlasData to AtlasCreateRequest if needed
        if isinstance(atlas, AtlasData):
            atlas_request = EntityConverter.atlas_to_request(atlas, grid_id)
        else:
            atlas_request = atlas

        response = await self._request(
            "post",
            f"grids/{grid_id}/atlas",
            atlas_request,
            AtlasResponse
        )
        # Store ID mapping
        self._store_entity_id_mapping("atlas", response.id, response.id)
        return response

    create_grid_atlas = _sync_wrap(acreate_grid_atlas)

    # Atlas Tiles
    async def aget_atlas_tiles(self) -> List[AtlasTileResponse]:
        """Get all atlas tiles (async)"""
        return await self._request("get", "atlas-tiles", response_cls=AtlasTileResponse)

    get_atlas_tiles = _sync_wrap(aget_atlas_tiles)

    async def aget_atlas_tile(self, tile_id: str) -> AtlasTileResponse:
        """Get a single atlas tile by ID (async)"""
        return await self._request("get", f"atlas-tiles/{tile_id}", response_cls=AtlasTileResponse)

    get_atlas_tile = _sync_wrap(aget_atlas_tile)

    async def aupdate_atlas_tile(self, tile_id: str, tile: AtlasTileUpdateRequest) -> AtlasTileResponse:
        """Update an atlas tile (async)"""
        return await self._request("put", f"atlas-tiles/{tile_id}", tile, AtlasTileResponse)

    update_atlas_tile = _sync_wrap(aupdate_atlas_tile)

    async def adelete_atlas_tile(self, tile_id: str) -> None:
        """Delete an atlas tile (async)"""
        await self._request("delete", f"atlas-tiles/{tile_id}")

    delete_atlas_tile = _sync_wrap(adelete_atlas_tile)

    async def aget_atlas_tiles_by_atlas(self, atlas_id: str) -> List[AtlasTileResponse]:
        """Get all tiles for a specific atlas (async)"""
        return await self._request("get", f"atlases/{atlas_id}/tiles", response_cls=AtlasTileResponse)

    get_atlas_tiles_by_atlas = _sync_wrap(aget_atlas_tiles_by_atlas)

    async def acreate_atlas_tile_for_atlas(
            self,
            atlas_id: str,
            tile: Union[AtlasTileCreateRequest, AtlasTileData]
    ) -> AtlasTileResponse:
        """Create a new tile for a specific atlas (async)"""
        # Convert AtlasTileData to AtlasTileCreateRequest if needed
        if isinstance(tile, AtlasTileData):
            tile_request = EntityConverter.atlas_tile_to_request(tile, atlas_id)
        else:
            tile_request = tile

        response = await self._request(
            "post",
            f"atlases/{atlas_id}/tiles",
            tile_request,
            AtlasTileResponse
        )
        # Store ID mapping
        self._store_entity_id_mapping("atlas_tile", tile_request.tile_id, response.id)
        return response

    create_atlas_tile_for_atlas = _sync_wrap(acreate_atlas_tile_for_atlas)

    # GridSquares
    async def aget_gridsquares(self) -> List[GridSquareResponse]:
        """Get all grid squares (async)"""
        return await self._request("get", "gridsquares", response_cls=GridSquareResponse)

    get_gridsquares = _sync_wrap(aget_gridsquares)

    async def aget_gridsquare(self, gridsquare_id: str) -> GridSquareResponse:
        """Get a single grid square by ID (async)"""
        return await self._request("get", f"gridsquares/{gridsquare_id}", response_cls=GridSquareResponse)

    get_gridsquare = _sync_wrap(aget_gridsquare)

    async def aupdate_gridsquare(self, gridsquare_id: str, gridsquare: GridSquareUpdateRequest) -> GridSquareResponse:
        """Update a grid square (async)"""
        return await self._request("put", f"gridsquares/{gridsquare_id}", gridsquare, GridSquareResponse)

    update_gridsquare = _sync_wrap(aupdate_gridsquare)

    async def adelete_gridsquare(self, gridsquare_id: str) -> None:
        """Delete a grid square (async)"""
        await self._request("delete", f"gridsquares/{gridsquare_id}")

    delete_gridsquare = _sync_wrap(adelete_gridsquare)

    async def aget_grid_gridsquares(self, grid_id: str) -> List[GridSquareResponse]:
        """Get all grid squares for a specific grid (async)"""
        return await self._request("get", f"grids/{grid_id}/gridsquares", response_cls=GridSquareResponse)

    get_grid_gridsquares = _sync_wrap(aget_grid_gridsquares)

    async def acreate_grid_gridsquare(
            self,
            grid_id: str,
            gridsquare: Union[GridSquareCreateRequest, GridSquareData]
    ) -> GridSquareResponse:
        """Create a new grid square for a specific grid (async)"""
        # Convert GridSquareData to GridSquareCreateRequest if needed
        if isinstance(gridsquare, GridSquareData):
            gridsquare_request = EntityConverter.gridsquare_to_request(gridsquare, grid_id)
        else:
            gridsquare_request = gridsquare

        response = await self._request(
            "post",
            f"grids/{grid_id}/gridsquares",
            gridsquare_request,
            GridSquareResponse
        )
        # Store ID mapping
        self._store_entity_id_mapping("gridsquare", gridsquare.id, response.id)
        return response

    create_grid_gridsquare = _sync_wrap(acreate_grid_gridsquare)

    # FoilHoles
    async def aget_foilholes(self) -> List[FoilHoleResponse]:
        """Get all foil holes (async)"""
        return await self._request("get", "foilholes", response_cls=FoilHoleResponse)

    get_foilholes = _sync_wrap(aget_foilholes)

    async def aget_foilhole(self, foilhole_id: str) -> FoilHoleResponse:
        """Get a single foil hole by ID (async)"""
        return await self._request("get", f"foilholes/{foilhole_id}", response_cls=FoilHoleResponse)

    get_foilhole = _sync_wrap(aget_foilhole)

    async def aupdate_foilhole(self, foilhole_id: str, foilhole: FoilHoleUpdateRequest) -> FoilHoleResponse:
        """Update a foil hole (async)"""
        return await self._request("put", f"foilholes/{foilhole_id}", foilhole, FoilHoleResponse)

    update_foilhole = _sync_wrap(aupdate_foilhole)

    async def adelete_foilhole(self, foilhole_id: str) -> None:
        """Delete a foil hole (async)"""
        await self._request("delete", f"foilholes/{foilhole_id}")

    delete_foilhole = _sync_wrap(adelete_foilhole)

    async def aget_gridsquare_foilholes(self, gridsquare_id: str) -> List[FoilHoleResponse]:
        """Get all foil holes for a specific grid square (async)"""
        return await self._request("get", f"gridsquares/{gridsquare_id}/foilholes", response_cls=FoilHoleResponse)

    get_gridsquare_foilholes = _sync_wrap(aget_gridsquare_foilholes)

    async def acreate_gridsquare_foilhole(
            self,
            gridsquare_id: str,
            foilhole: Union[FoilHoleCreateRequest, FoilHoleData]
    ) -> FoilHoleResponse:
        """Create a new foil hole for a specific grid square (async)"""
        # Convert FoilHoleData to FoilHoleCreateRequest if needed
        if isinstance(foilhole, FoilHoleData):
            foilhole_request = EntityConverter.foilhole_to_request(foilhole, gridsquare_id)
        else:
            foilhole_request = foilhole

        response = await self._request(
            "post",
            f"gridsquares/{gridsquare_id}/foilholes",
            foilhole_request,
            FoilHoleResponse
        )
        # Store ID mapping
        self._store_entity_id_mapping("foilhole", foilhole.id, response.id)
        return response

    create_gridsquare_foilhole = _sync_wrap(acreate_gridsquare_foilhole)

    # Micrographs
    async def aget_micrographs(self) -> List[MicrographResponse]:
        """Get all micrographs (async)"""
        return await self._request("get", "micrographs", response_cls=MicrographResponse)

    get_micrographs = _sync_wrap(aget_micrographs)

    async def aget_micrograph(self, micrograph_id: str) -> MicrographResponse:
        """Get a single micrograph by ID (async)"""
        return await self._request("get", f"micrographs/{micrograph_id}", response_cls=MicrographResponse)

    get_micrograph = _sync_wrap(aget_micrograph)

    async def aupdate_micrograph(self, micrograph_id: str, micrograph: MicrographUpdateRequest) -> MicrographResponse:
        """Update a micrograph (async)"""
        return await self._request("put", f"micrographs/{micrograph_id}", micrograph, MicrographResponse)

    update_micrograph = _sync_wrap(aupdate_micrograph)

    async def adelete_micrograph(self, micrograph_id: str) -> None:
        """Delete a micrograph (async)"""
        await self._request("delete", f"micrographs/{micrograph_id}")

    delete_micrograph = _sync_wrap(adelete_micrograph)

    async def aget_foilhole_micrographs(self, foilhole_id: str) -> List[MicrographResponse]:
        """Get all micrographs for a specific foil hole (async)"""
        return await self._request("get", f"foilholes/{foilhole_id}/micrographs", response_cls=MicrographResponse)

    get_foilhole_micrographs = _sync_wrap(aget_foilhole_micrographs)

    async def acreate_foilhole_micrograph(
            self,
            foilhole_id: str,
            micrograph: Union[MicrographCreateRequest, MicrographData]
    ) -> MicrographResponse:
        """Create a new micrograph for a specific foil hole (async)"""
        # Convert MicrographData to MicrographCreateRequest if needed
        if isinstance(micrograph, MicrographData):
            micrograph_request = EntityConverter.micrograph_to_request(micrograph, foilhole_id)
        else:
            micrograph_request = micrograph

        response = await self._request(
            "post",
            f"foilholes/{foilhole_id}/micrographs",
            micrograph_request,
            MicrographResponse
        )
        # Store ID mapping
        self._store_entity_id_mapping("micrograph", micrograph.id, response.id)
        return response

    create_foilhole_micrograph = _sync_wrap(acreate_foilhole_micrograph)

    # EntityStore compatibility methods (matching the old adapter API)
    def create(self, entity_type: str, entity_id: str, entity: Any, parent: Optional[tuple[str, str]] = None) -> bool:
        """
        Create a new entity via API - compatibility method for EntityStore

        Args:
            entity_type: Type of entity ("acquisition", "grid", etc.)
            entity_id: Entity ID
            entity: Entity object
            parent: Optional parent entity (entity_type, entity_id)

        Returns:
            bool: Success status
        """
        try:
            self._logger.info(f"Creating {entity_type}/{entity_id} via API" +
                              (f" with parent {parent[0]}/{parent[1]}" if parent else ""))

            if entity_type == "acquisition" and isinstance(entity, EpuSessionData):
                response = self.create_acquisition(entity)
                self._store_entity_id_mapping("acquisition", entity_id, response.id)
                self._logger.info(f"Successfully created acquisition {entity_id} (DB ID: {response.id})")
                return True

            elif entity_type == "grid" and isinstance(entity, Grid):
                if parent and parent[0] == "acquisition":
                    acquisition_db_id = self._get_db_id("acquisition", parent[1])
                    if not acquisition_db_id:
                        self._logger.error(f"Cannot create grid: Acquisition {parent[1]} not found in ID map")
                        return False

                    response = self.create_acquisition_grid(acquisition_db_id, entity)
                    self._store_entity_id_mapping("grid", entity_id, response.id)
                    self._logger.info(f"Successfully created grid {entity_id} (DB ID: {response.id})")
                    return True
                else:
                    self._logger.error("Cannot create grid: No valid acquisition parent")
                    return False

            elif entity_type == "gridsquare" and isinstance(entity, GridSquareData):
                if parent and parent[0] == "grid":
                    grid_db_id = self._get_db_id("grid", parent[1])
                    if not grid_db_id:
                        self._logger.error(f"Cannot create gridsquare: Grid {parent[1]} not found in ID map")
                        return False

                    response = self.create_grid_gridsquare(grid_db_id, entity)
                    self._store_entity_id_mapping("gridsquare", entity_id, response.id)
                    self._logger.info(f"Successfully created gridsquare {entity_id} (DB ID: {response.id})")
                    return True
                else:
                    self._logger.error("Cannot create gridsquare: No valid grid parent")
                    return False

            elif entity_type == "foilhole" and isinstance(entity, FoilHoleData):
                if parent and parent[0] == "gridsquare":
                    gridsquare_db_id = self._get_db_id("gridsquare", parent[1])
                    if not gridsquare_db_id:
                        self._logger.error(f"Cannot create foilhole: Gridsquare {parent[1]} not found in ID map")
                        return False

                    response = self.create_gridsquare_foilhole(gridsquare_db_id, entity)
                    self._store_entity_id_mapping("foilhole", entity_id, response.id)
                    self._logger.info(f"Successfully created foilhole {entity_id} (DB ID: {response.id})")
                    return True
                else:
                    self._logger.error("Cannot create foilhole: No valid gridsquare parent")
                    return False

            elif entity_type == "micrograph" and isinstance(entity, MicrographData):
                if parent and parent[0] == "foilhole":
                    foilhole_db_id = self._get_db_id("foilhole", parent[1])
                    if not foilhole_db_id:
                        self._logger.error(f"Cannot create micrograph: Foilhole {parent[1]} not found in ID map")
                        return False

                    response = self.create_foilhole_micrograph(foilhole_db_id, entity)
                    self._store_entity_id_mapping("micrograph", entity_id, response.id)
                    self._logger.info(f"Successfully created micrograph {entity_id} (DB ID: {response.id})")
                    return True
                else:
                    self._logger.error("Cannot create micrograph: No valid foilhole parent")
                    return False

            elif entity_type == "atlas" and isinstance(entity, AtlasData):
                if parent and parent[0] == "grid":
                    grid_db_id = self._get_db_id("grid", parent[1])
                    if not grid_db_id:
                        self._logger.error(f"Cannot create atlas: Grid {parent[1]} not found in ID map")
                        return False

                    response = self.create_grid_atlas(grid_db_id, entity)
                    self._store_entity_id_mapping("atlas", entity_id, response.id)
                    self._logger.info(f"Successfully created atlas {entity_id} (DB ID: {response.id})")
                    return True
                else:
                    self._logger.error("Cannot create atlas: No valid grid parent")
                    return False

            elif entity_type == "atlas_tile" and isinstance(entity, AtlasTileData):
                if parent and parent[0] == "atlas":
                    atlas_db_id = self._get_db_id("atlas", parent[1])
                    if not atlas_db_id:
                        self._logger.error(f"Cannot create atlas tile: Atlas {parent[1]} not found in ID map")
                        return False

                    response = self.create_atlas_tile_for_atlas(atlas_db_id, entity)
                    self._store_entity_id_mapping("atlas_tile", entity_id, response.id)
                    self._logger.info(f"Successfully created atlas tile {entity_id} (DB ID: {response.id})")
                    return True
                else:
                    self._logger.error("Cannot create atlas tile: No valid atlas parent")
                    return False

            else:
                self._logger.error(f"Unsupported entity type: {entity_type}")
                return False

        except httpx.HTTPStatusError as e:
            status_code = e.response.status_code
            error_detail = None

            # Try to extract error details from the response
            try:
                error_response = e.response.json()
                error_detail = error_response.get("detail", str(e))
            except Exception:
                error_detail = e.response.text or str(e)

            self._logger.error(f"HTTP {status_code} error creating {entity_type}/{entity_id}: {error_detail}")
            return False

        except Exception as e:
            self._logger.error(f"Failed to create {entity_type}/{entity_id}: {str(e)}")
            self._logger.debug(f"Error details: {traceback.format_exc()}")
            return False

    def update(self, entity_type: str, entity_id: str, entity: Any, parent: Optional[tuple[str, str]] = None) -> bool:
        """
        Update an existing entity via API - compatibility method for EntityStore

        Args:
            entity_type: Type of entity ("acquisition", "grid", etc.)
            entity_id: Entity ID
            entity: Entity object
            parent: Optional parent entity (entity_type, entity_id)

        Returns:
            bool: Success status
        """
        try:
            self._logger.info(f"Updating {entity_type}/{entity_id} via API" +
                              (f" with parent {parent[0]}/{parent[1]}" if parent else ""))

            # Map entity_id to database ID
            db_id = self._get_db_id(entity_type, entity_id)
            if not db_id:
                self._logger.warning(f"No database ID found for {entity_type}/{entity_id}, cannot update")
                return False

            # For now, just log that we would update and return success
            self._logger.info(f"Would update {entity_type}/{entity_id} (DB ID: {db_id}) via API")
            return True

        except Exception as e:
            self._logger.error(f"Failed to update {entity_type}/{entity_id}: {str(e)}")
            self._logger.debug(f"Error details: {traceback.format_exc()}")
            return False
