import asyncio
import json
import logging
import random
import time
import traceback
from collections.abc import Callable
from datetime import datetime

import requests
import sseclient
from pydantic import BaseModel

from smartem_backend.model.http_request import (
    AcquisitionCreateRequest,
    AgentInstructionAcknowledgement,
    AtlasCreateRequest,
    AtlasTileCreateRequest,
    FoilHoleCreateRequest,
    GridCreateRequest,
    GridSquareCreateRequest,
    GridSquarePositionRequest,
    MicrographCreateRequest,
)
from smartem_backend.model.http_response import (
    AcquisitionResponse,
    AgentInstructionAcknowledgementResponse,
    AtlasResponse,
    AtlasTileGridSquarePositionResponse,
    AtlasTileResponse,
    FoilHoleResponse,
    GridResponse,
    GridSquareResponse,
    MicrographResponse,
)
from smartem_common.entity_status import AcquisitionStatus, GridSquareStatus, GridStatus
from smartem_common.schemas import (
    AcquisitionData,
    AtlasData,
    AtlasTileData,
    AtlasTileGridSquarePositionData,
    FoilHoleData,
    GridData,
    GridSquareData,
    MicrographData,
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
            instrument_model=entity.instrument.instrument_model if entity.instrument else None,
            instrument_id=entity.instrument.instrument_id if entity.instrument else None,
            computer_name=entity.instrument.computer_name if entity.instrument else None,
            status=AcquisitionStatus.STARTED,
        )

    @staticmethod
    def grid_to_request(entity: GridData, lowmag: bool = False) -> GridCreateRequest:
        """Convert Grid data to grid request model"""
        return GridCreateRequest(
            uuid=entity.uuid,
            status=GridStatus.NONE,
            name=entity.acquisition_data.name if entity.acquisition_data else "Unknown",
            acquisition_uuid=entity.acquisition_data.uuid,
            data_dir=str(entity.data_dir) if entity.data_dir else None,
            atlas_dir=str(entity.atlas_dir) if entity.atlas_dir else None,
            lowmag=lowmag,
        )

    @staticmethod
    def gridsquare_to_request(entity: GridSquareData, lowmag: bool = False) -> GridSquareCreateRequest:
        """Convert GridSquareData to grid square request model"""
        metadata = entity.metadata
        manifest = entity.manifest
        return GridSquareCreateRequest(
            grid_uuid=entity.grid_uuid,
            gridsquare_id=entity.gridsquare_id,
            uuid=entity.uuid,
            center_x=entity.center_x,
            center_y=entity.center_y,
            size_width=entity.size_width,
            size_height=entity.size_height,
            status=GridSquareStatus.NONE,
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
            lowmag=lowmag,
        )

    @staticmethod
    def foilhole_to_request(entity: FoilHoleData) -> FoilHoleCreateRequest:
        """Convert FoilHoleData to foil hole request model"""
        return FoilHoleCreateRequest(
            uuid=entity.uuid,
            foilhole_id=entity.id,  # Changed from id=entity.id to foilhole_id=entity.id
            gridsquare_id=entity.gridsquare_id,
            gridsquare_uuid=entity.gridsquare_uuid,
            center_x=entity.center_x,
            center_y=entity.center_y,
            quality=entity.quality,
            rotation=entity.rotation,
            size_width=entity.size_width,
            size_height=entity.size_height,
            x_location=entity.x_location,
            y_location=entity.y_location,
            x_stage_position=entity.x_stage_position,
            y_stage_position=entity.y_stage_position,
            diameter=entity.diameter,
            is_near_grid_bar=entity.is_near_grid_bar,
        )

    @staticmethod
    def micrograph_to_request(entity: MicrographData) -> MicrographCreateRequest:
        """Convert MicrographData to micrograph request model"""
        manifest = entity.manifest
        return MicrographCreateRequest(
            uuid=entity.uuid,
            foilhole_uuid=entity.foilhole_uuid,
            foilhole_id=entity.foilhole_id,
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
    def atlas_to_request(entity: AtlasData) -> AtlasCreateRequest:
        """Convert AtlasData to atlas request model"""
        return AtlasCreateRequest(
            uuid=entity.uuid,
            atlas_id=entity.id,
            grid_uuid=entity.grid_uuid,
            name=entity.name,
            storage_folder=entity.storage_folder,
            acquisition_date=entity.acquisition_date,
            tiles=[
                AtlasTileCreateRequest(
                    atlas_uuid=entity.uuid,
                    uuid=t.uuid,
                    tile_id=t.id,
                    position_x=t.tile_position.position[0],
                    position_y=t.tile_position.position[1],
                    size_x=t.tile_position.size[0],
                    size_y=t.tile_position.size[1],
                    file_format=t.file_format,
                    base_filename=t.base_filename,
                )
                for t in entity.tiles
            ],
        )

    @staticmethod
    def atlas_tile_to_request(entity: AtlasTileData) -> AtlasTileCreateRequest:
        """Convert AtlasTileData to atlas tile request model"""
        return AtlasTileCreateRequest(
            atlas_uuid=entity.atlas_uuid,
            uuid=entity.uuid,
            tile_id=entity.id,
            position_x=entity.tile_position.position[0],
            position_y=entity.tile_position.position[1],
            size_x=entity.tile_position.size[0],
            size_y=entity.tile_position.size[1],
            file_format=entity.file_format,
            base_filename=entity.base_filename,
        )

    @staticmethod
    def gridsquare_position_to_request(entity: AtlasTileGridSquarePositionData) -> GridSquarePositionRequest:
        """Convert AtlasTileData to atlas tile request model"""
        return GridSquarePositionRequest(
            center_x=entity.position[0],
            center_y=entity.position[1],
            size_width=entity.size[0],
            size_height=entity.size[1],
            gridsquare_uuid=entity.gridsquare_uuid,
        )


class SmartEMAPIClient:
    """
    SmartEM API client that provides synchronous HTTP interface.

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
        self._session = requests.Session()
        self._session.timeout = timeout
        self._logger = logger or logging.getLogger(__name__)

        # Configure logger if it's the default one
        if not logger:
            handler = logging.StreamHandler()
            formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
            handler.setFormatter(formatter)
            self._logger.addHandler(handler)
            self._logger.setLevel(logging.INFO)

        self._logger.info(f"Initialized SmartEM API client with base URL: {base_url}")

    def close(self) -> None:
        """Close the client connection"""
        try:
            self._session.close()
        except Exception as e:
            self._logger.error(f"Error closing session: {e}")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    # Generic API request methods
    def _request(
        self,
        method: str,
        endpoint: str,
        request_model: BaseModel | dict | list[BaseModel] | None = None,
        response_cls=None,
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
            requests.HTTPError: If the HTTP request returns an error status code
            requests.RequestException: If there's a network error or timeout
            ValueError: If there's an error parsing the response
            Exception: For any other errors
        """
        url = f"{self.base_url}/{endpoint}"
        json_data = None

        if request_model:
            if hasattr(request_model, "model_dump"):
                # It's a Pydantic model
                json_data = request_model.model_dump(mode="json", exclude_none=True)
            elif isinstance(request_model, list):
                json_data = [m.model_dump(mode="json", exclude_none=True) for m in request_model]
            else:
                # It's already a dict, but might contain datetime objects
                json_data = {k: v.isoformat() if isinstance(v, datetime) else v for k, v in request_model.items()}
            self._logger.debug(f"Request data for {method} {url}: {json_data}")

        try:
            self._logger.debug(f"Making {method.upper()} request to {url}")
            response = self._session.request(method, url, json=json_data)
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
                        raise ValueError(f"Invalid response data: {str(e)}") from None

                return data
            except json.JSONDecodeError as e:
                self._logger.error(f"Could not parse JSON response from {url}: {e}")
                self._logger.debug(f"Raw response: {response.text}")
                raise ValueError(f"Invalid JSON response: {str(e)}") from None

        except requests.HTTPError as e:
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

        except requests.RequestException as e:
            self._logger.error(f"Request error for {method.upper()} {url}: {e}")
            self._logger.debug(f"Request error details: {traceback.format_exc()}")
            raise

        except Exception as e:
            self._logger.error(f"Unexpected error making request to {url}: {e}")
            self._logger.debug(f"Error details: {traceback.format_exc()}")
            raise

    # Entity-specific methods

    # Status and Health
    def get_status(self) -> dict[str, object]:
        """Get API status information"""
        return self._request("get", "status")

    def get_health(self) -> dict[str, object]:
        """Get API health check information"""
        return self._request("get", "health")

    # Acquisitions
    def get_acquisitions(self) -> list[AcquisitionResponse]:
        """Get all acquisitions"""
        return self._request("get", "acquisitions", response_cls=AcquisitionResponse)

    def create_acquisition(self, acquisition: AcquisitionData) -> AcquisitionResponse:
        """Create a new acquisition"""
        acquisition = EntityConverter.acquisition_to_request(acquisition)
        response = self._request("post", "acquisitions", acquisition, AcquisitionResponse)
        return response

    def get_acquisition(self, acquisition_uuid: str) -> AcquisitionResponse:
        """Get a single acquisition by ID"""
        return self._request("get", f"acquisitions/{acquisition_uuid}", response_cls=AcquisitionResponse)

    def update_acquisition(self, acquisition: AcquisitionData) -> AcquisitionResponse:
        """Update an acquisition"""
        acquisition = EntityConverter.acquisition_to_request(acquisition)
        return self._request("put", f"acquisitions/{acquisition.uuid}", acquisition, AcquisitionResponse)

    def delete_acquisition(self, acquisition_uuid: str) -> None:
        """Delete an acquisition"""
        return self._request("delete", f"acquisitions/{acquisition_uuid}")

    # Grids
    def get_grids(self) -> list[GridResponse]:
        """Get all grids"""
        return self._request("get", "grids", response_cls=GridResponse)

    def get_grid(self, grid_uuid: str) -> GridResponse:
        """Get a single grid by ID"""
        return self._request("get", f"grids/{grid_uuid}", response_cls=GridResponse)

    def update_grid(self, grid: GridData) -> GridResponse:
        """Update a grid"""
        grid = EntityConverter.grid_to_request(grid)
        return self._request("put", f"grids/{grid.uuid}", grid, GridResponse)

    def delete_grid(self, grid_uuid: str) -> None:
        """Delete a grid"""
        return self._request("delete", f"grids/{grid_uuid}")

    def get_acquisition_grids(self, acquisition_uuid: str) -> list[GridResponse]:
        """Get all grids for a specific acquisition"""
        return self._request("get", f"acquisitions/{acquisition_uuid}/grids", response_cls=GridResponse)

    def create_acquisition_grid(self, grid: GridData) -> GridResponse:
        """Create a new grid for a specific acquisition"""
        grid = EntityConverter.grid_to_request(grid)
        response = self._request("post", f"acquisitions/{grid.acquisition_uuid}/grids", grid, GridResponse)
        return response

    def grid_registered(self, grid_uuid: str) -> bool:
        return self._request("post", f"grids/{grid_uuid}/registered")

    # Atlas
    def get_atlases(self) -> list[AtlasResponse]:
        """Get all atlases"""
        return self._request("get", "atlases", response_cls=AtlasResponse)

    def get_atlas(self, atlas_uuid: str) -> AtlasResponse:
        """Get a single atlas by ID"""
        return self._request("get", f"atlases/{atlas_uuid}", response_cls=AtlasResponse)

    def update_atlas(self, atlas: AtlasData) -> AtlasResponse:
        """Update an atlas"""
        atlas = EntityConverter.atlas_to_request(atlas)
        return self._request("put", f"atlases/{atlas.uuid}", atlas, AtlasResponse)

    def delete_atlas(self, atlas_uuid: str) -> None:
        """Delete an atlas"""
        return self._request("delete", f"atlases/{atlas_uuid}")

    def get_grid_atlas(self, grid_uuid: str) -> AtlasResponse:
        """Get the atlas for a specific grid"""
        return self._request("get", f"grids/{grid_uuid}/atlas", response_cls=AtlasResponse)

    def create_grid_atlas(self, atlas: AtlasData) -> AtlasResponse:
        """Create a new atlas for a grid"""
        # Convert AtlasData to AtlasCreateRequest if needed
        atlas = EntityConverter.atlas_to_request(atlas)
        response = self._request("post", f"grids/{atlas.grid_uuid}/atlas", atlas, AtlasResponse)
        return response

    # Atlas Tiles
    def get_atlas_tiles(self) -> list[AtlasTileResponse]:
        """Get all atlas tiles"""
        return self._request("get", "atlas-tiles", response_cls=AtlasTileResponse)

    def get_atlas_tile(self, tile_uuid: str) -> AtlasTileResponse:
        """Get a single atlas tile by ID"""
        return self._request("get", f"atlas-tiles/{tile_uuid}", response_cls=AtlasTileResponse)

    def update_atlas_tile(self, tile: AtlasTileData) -> AtlasTileResponse:
        """Update an atlas tile"""
        tile = EntityConverter.atlas_tile_to_request(tile)
        return self._request("put", f"atlas-tiles/{tile.uuid}", tile, AtlasTileResponse)

    def delete_atlas_tile(self, tile_uuid: str) -> None:
        """Delete an atlas tile"""
        return self._request("delete", f"atlas-tiles/{tile_uuid}")

    def get_atlas_tiles_by_atlas(self, atlas_uuid: str) -> list[AtlasTileResponse]:
        """Get all tiles for a specific atlas"""
        return self._request("get", f"atlases/{atlas_uuid}/tiles", response_cls=AtlasTileResponse)

    def create_atlas_tile_for_atlas(self, tile: AtlasTileData) -> AtlasTileResponse:
        """Create a new tile for a specific atlas"""
        tile = EntityConverter.atlas_tile_to_request(tile)
        response = self._request("post", f"atlases/{tile.atlas_uuid}/tiles", tile, AtlasTileResponse)
        return response

    def link_atlas_tile_and_gridsquare(
        self, gridsquare_position: AtlasTileGridSquarePositionData
    ) -> AtlasTileGridSquarePositionResponse:
        """Link a grid square to a tile"""
        tile_uuid = gridsquare_position.tile_uuid
        gridsquare_uuid = gridsquare_position.gridsquare_uuid
        gridsquare_position = EntityConverter.gridsquare_position_to_request(gridsquare_position)
        response = self._request(
            "post",
            f"atlas-tiles/{tile_uuid}/gridsquares/{gridsquare_uuid}",
            gridsquare_position,
            AtlasTileGridSquarePositionResponse,
        )
        return response

    def link_atlas_tile_and_gridsquares(
        self, gridsquare_positions: list[AtlasTileGridSquarePositionData]
    ) -> list[AtlasTileGridSquarePositionResponse]:
        """Link multiple grid squares to a tile"""
        if not gridsquare_positions:
            return []
        assert len({pos.tile_uuid for pos in gridsquare_positions}) == 1
        tile_uuid = gridsquare_positions[0].tile_uuid
        gridsquare_positions = [EntityConverter.gridsquare_position_to_request(pos) for pos in gridsquare_positions]
        response = self._request(
            "post",
            f"atlas-tiles/{tile_uuid}/gridsquares",
            gridsquare_positions,
            AtlasTileGridSquarePositionResponse,
        )
        return response

    # GridSquares
    def get_gridsquares(self) -> list[GridSquareResponse]:
        """Get all grid squares"""
        return self._request("get", "gridsquares", response_cls=GridSquareResponse)

    def get_gridsquare(self, gridsquare_uuid: str) -> GridSquareResponse:
        """Get a single grid square by ID"""
        return self._request("get", f"gridsquares/{gridsquare_uuid}", response_cls=GridSquareResponse)

    def update_gridsquare(self, gridsquare: GridSquareData, lowmag: bool = False) -> GridSquareResponse:
        """Update a grid square"""
        request_model = EntityConverter.gridsquare_to_request(gridsquare, lowmag=lowmag)
        return self._request("put", f"gridsquares/{gridsquare.uuid}", request_model, GridSquareResponse)

    def delete_gridsquare(self, gridsquare_uuid: str) -> None:
        """Delete a grid square"""
        return self._request("delete", f"gridsquares/{gridsquare_uuid}")

    def get_grid_gridsquares(self, grid_uuid: str) -> list[GridSquareResponse]:
        """Get all grid squares for a specific grid"""
        return self._request("get", f"grids/{grid_uuid}/gridsquares", response_cls=GridSquareResponse)

    def create_grid_gridsquare(self, gridsquare: GridSquareData, lowmag: bool = False) -> GridSquareResponse:
        """Create a new grid square for a specific grid"""
        # Convert GridSquareData to GridSquareCreateRequest if needed
        gridsquare = EntityConverter.gridsquare_to_request(gridsquare, lowmag=lowmag)
        response = self._request("post", f"grids/{gridsquare.grid_uuid}/gridsquares", gridsquare, GridSquareResponse)
        return response

    def gridsquare_registered(self, gridsquare_uuid: str, count: int | None = None) -> bool:
        if count is None:
            return self._request("post", f"gridsquares/{gridsquare_uuid}/registered")
        return self._request("post", f"gridsquares/{gridsquare_uuid}/registered?count={count}")

    # FoilHoles
    def get_foilholes(self) -> list[FoilHoleResponse]:
        """Get all foil holes"""
        return self._request("get", "foilholes", response_cls=FoilHoleResponse)

    def get_foilhole(self, foilhole_uuid: str) -> FoilHoleResponse:
        """Get a single foil hole by ID"""
        return self._request("get", f"foilholes/{foilhole_uuid}", response_cls=FoilHoleResponse)

    def update_foilhole(self, foilhole: FoilHoleData) -> FoilHoleResponse:
        """Update a foil hole"""
        foilhole = EntityConverter.foilhole_to_request(foilhole)
        return self._request("put", f"foilholes/{foilhole.uuid}", foilhole, FoilHoleResponse)

    def delete_foilhole(self, foilhole_uuid: str) -> None:
        """Delete a foil hole"""
        return self._request("delete", f"foilholes/{foilhole_uuid}")

    def get_gridsquare_foilholes(self, gridsquare_uuid: str) -> list[FoilHoleResponse]:
        """Get all foil holes for a specific grid square"""
        return self._request("get", f"gridsquares/{gridsquare_uuid}/foilholes", response_cls=FoilHoleResponse)

    def create_gridsquare_foilholes(
        self, gridsquare_uuid: str, foilholes: list[FoilHoleData], allow_on_grid_bar: bool = False
    ) -> list[FoilHoleResponse]:
        """Create a new foil hole for a specific grid square"""
        foilholes = [
            EntityConverter.foilhole_to_request(fh)
            for fh in foilholes
            if (not fh.is_near_grid_bar or allow_on_grid_bar)
        ]
        # this currently assumes all foil holes are on the same square
        response = self._request("post", f"gridsquares/{gridsquare_uuid}/foilholes", foilholes, FoilHoleResponse)
        return response

    # Micrographs
    def get_micrographs(self) -> list[MicrographResponse]:
        """Get all micrographs"""
        return self._request("get", "micrographs", response_cls=MicrographResponse)

    def get_micrograph(self, micrograph_uuid: str) -> MicrographResponse:
        """Get a single micrograph by ID"""
        return self._request("get", f"micrographs/{micrograph_uuid}", response_cls=MicrographResponse)

    def update_micrograph(self, micrograph: MicrographData) -> MicrographResponse:
        """Update a micrograph"""
        micrograph = EntityConverter.micrograph_to_request(micrograph)
        return self._request("put", f"micrographs/{micrograph.uuid}", micrograph, MicrographResponse)

    def delete_micrograph(self, micrograph_id: str) -> None:
        """Delete a micrograph"""
        return self._request("delete", f"micrographs/{micrograph_id}")

    def get_foilhole_micrographs(self, foilhole_id: str) -> list[MicrographResponse]:
        """Get all micrographs for a specific foil hole"""
        return self._request("get", f"foilholes/{foilhole_id}/micrographs", response_cls=MicrographResponse)

    def create_foilhole_micrograph(self, micrograph: MicrographData) -> MicrographResponse:
        """Create a new micrograph for a specific foil hole"""
        micrograph = EntityConverter.micrograph_to_request(micrograph)
        response = self._request(
            "post", f"foilholes/{micrograph.foilhole_uuid}/micrographs", micrograph, MicrographResponse
        )
        return response

    # ============ Agent Communication Methods ============

    def acknowledge_instruction(
        self, agent_id: str, session_id: str, instruction_id: str, acknowledgement: AgentInstructionAcknowledgement
    ) -> AgentInstructionAcknowledgementResponse:
        """Acknowledge an instruction from the agent"""
        return self._request(
            "post",
            f"agent/{agent_id}/session/{session_id}/instructions/{instruction_id}/ack",
            acknowledgement,
            AgentInstructionAcknowledgementResponse,
        )

    def get_active_connections(self) -> dict:
        """Get active agent connections (debug endpoint)"""
        return self._request("get", "debug/agent-connections")

    def get_session_instructions(self, session_id: str) -> dict:
        """Get instructions for a session (debug endpoint)"""
        return self._request("get", f"debug/session/{session_id}/instructions")


class SSEAgentClient:
    """
    SSE client for agents to receive real-time instructions from the backend.
    This is separate from the main ApiClient as it handles long-lived connections.
    """

    def __init__(
        self,
        base_url: str,
        agent_id: str,
        session_id: str,
        timeout: int = 30,
        max_retries: int = 10,
        initial_retry_delay: float = 1.0,
        max_retry_delay: float = 60.0,
    ):
        """
        Initialize SSE client for agent communication

        Args:
            base_url: Base URL of the API server
            agent_id: Unique identifier for this agent/microscope
            session_id: Current microscopy session ID
            timeout: Connection timeout in seconds
            max_retries: Maximum number of reconnection attempts
            initial_retry_delay: Initial delay between retries in seconds
            max_retry_delay: Maximum delay between retries in seconds
        """
        self.base_url = base_url.rstrip("/")
        self.agent_id = agent_id
        self.session_id = session_id
        self.timeout = timeout
        self.max_retries = max_retries
        self.initial_retry_delay = initial_retry_delay
        self.max_retry_delay = max_retry_delay
        self.logger = logging.getLogger(f"SSEAgentClient-{agent_id}")
        self._is_running = False
        self._connection_id: str | None = None
        self._stats = {
            "total_connections": 0,
            "successful_connections": 0,
            "failed_connections": 0,
            "instructions_received": 0,
            "instructions_acknowledged": 0,
            "last_connection_time": None,
            "last_instruction_time": None,
        }

    def stream_instructions(
        self,
        instruction_callback: Callable[[dict], None],
        connection_callback: Callable[[dict], None] | None = None,
        error_callback: Callable[[Exception], None] | None = None,
    ) -> None:
        """
        Start streaming instructions via SSE (blocking)

        Args:
            instruction_callback: Called when an instruction is received
            connection_callback: Called when connection events occur (optional)
            error_callback: Called when errors occur (optional)
        """
        stream_url = f"{self.base_url}/agent/{self.agent_id}/session/{self.session_id}/instructions/stream"

        self.logger.info(f"Starting SSE stream for agent {self.agent_id}, session {self.session_id}")
        self._is_running = True
        self._stats["total_connections"] += 1

        try:
            response = requests.get(
                stream_url, headers={"Accept": "text/event-stream"}, stream=True, timeout=self.timeout
            )
            response.raise_for_status()

            self._stats["successful_connections"] += 1
            self._stats["last_connection_time"] = datetime.now().isoformat()

            client = sseclient.SSEClient(response)

            for event in client.events():
                if not self._is_running:
                    break

                try:
                    data = json.loads(event.data)
                    event_type = data.get("type")

                    match event_type:
                        case "connection":
                            self._connection_id = data.get("connection_id")
                            self.logger.info(f"Connected with connection_id: {self._connection_id}")
                            if connection_callback:
                                connection_callback(data)

                        case "heartbeat":
                            self.logger.debug(f"Heartbeat received at {data.get('timestamp')}")

                        case "instruction":
                            self._stats["instructions_received"] += 1
                            self._stats["last_instruction_time"] = datetime.now().isoformat()
                            self.logger.info(
                                f"Instruction received: {data.get('instruction_id')} - {data.get('instruction_type')}"
                            )
                            instruction_callback(data)

                        case "error":
                            error_msg = data.get("message", "Unknown error")
                            error = ConnectionError(f"Server error: {error_msg}")
                            self.logger.error(f"Server error received: {error_msg}")
                            if error_callback:
                                error_callback(error)
                            break

                        case _:
                            self.logger.warning(f"Unknown event type: {event_type}")

                except json.JSONDecodeError as e:
                    self.logger.error(f"Failed to parse SSE data: {e}")
                    if error_callback:
                        error_callback(e)
                except Exception as e:
                    self.logger.error(f"Error processing SSE event: {e}")
                    if error_callback:
                        error_callback(e)

        except requests.exceptions.RequestException as e:
            self._stats["failed_connections"] += 1
            self.logger.error(f"SSE connection error: {e}")
            if error_callback:
                error_callback(e)
        except Exception as e:
            self._stats["failed_connections"] += 1
            self.logger.error(f"Unexpected SSE error: {e}")
            if error_callback:
                error_callback(e)
        finally:
            self._is_running = False
            self.logger.info("SSE stream ended")

    def _calculate_backoff_delay(self, retry_count: int) -> float:
        """Calculate exponential backoff delay with jitter."""
        delay = min(self.initial_retry_delay * (2**retry_count), self.max_retry_delay)
        # Add jitter (±25% of delay)
        jitter = delay * 0.25 * (2 * random.random() - 1)
        return max(0.1, delay + jitter)

    async def stream_instructions_async(
        self,
        instruction_callback: Callable[[dict], None],
        connection_callback: Callable[[dict], None] | None = None,
        error_callback: Callable[[Exception], None] | None = None,
        auto_retry: bool = True,
    ) -> None:
        """
        Start streaming instructions via SSE (async with auto-retry and exponential backoff)

        Args:
            instruction_callback: Called when an instruction is received
            connection_callback: Called when connection events occur (optional)
            error_callback: Called when errors occur (optional)
            auto_retry: Whether to automatically retry on connection failures
        """
        retry_count = 0
        last_error: Exception | None = None

        # Ensure we're running
        self._is_running = True

        while retry_count <= self.max_retries and self._is_running:
            try:
                self.logger.info(f"Starting SSE connection (attempt {retry_count + 1}/{self.max_retries + 1})")

                # Run the synchronous streaming in a thread pool
                await asyncio.get_event_loop().run_in_executor(
                    None, self.stream_instructions, instruction_callback, connection_callback, error_callback
                )

                # If we get here, the connection ended gracefully (user stopped it)
                if not self._is_running:
                    self.logger.info("Connection stopped by user")
                    break

                # If auto_retry is disabled, exit after one attempt
                if not auto_retry:
                    break

            except Exception as e:
                last_error = e
                retry_count += 1

                self.logger.error(f"SSE connection failed (attempt {retry_count}/{self.max_retries + 1}): {e}")

                if retry_count <= self.max_retries and auto_retry and self._is_running:
                    delay = self._calculate_backoff_delay(retry_count - 1)
                    self.logger.info(f"Retrying in {delay:.2f} seconds...")
                    await asyncio.sleep(delay)
                else:
                    self.logger.error("Max retries reached or auto_retry disabled, giving up")
                    if error_callback and last_error:
                        error_callback(last_error)
                    break

    def acknowledge_instruction(
        self,
        instruction_id: str,
        status: str,
        result: str | None = None,
        error_message: str | None = None,
        processing_time_ms: int | None = None,
        retry_count: int = 3,
    ) -> AgentInstructionAcknowledgementResponse:
        """
        Acknowledge an instruction with retry logic

        Args:
            instruction_id: ID of the instruction to acknowledge
            status: Status of acknowledgement ('received', 'processed', 'failed', 'declined')
            result: Optional result message
            error_message: Optional error message if status is 'failed'
            processing_time_ms: Time taken to process the instruction in milliseconds
            retry_count: Number of retry attempts for acknowledgement
        """
        acknowledgement = AgentInstructionAcknowledgement(
            status=status,
            result=result,
            error_message=error_message,
            processing_time_ms=processing_time_ms,
            processed_at=datetime.now(),
        )

        ack_url = f"{self.base_url}/agent/{self.agent_id}/session/{self.session_id}/instructions/{instruction_id}/ack"

        last_error = None
        for attempt in range(retry_count):
            try:
                response = requests.post(
                    ack_url,
                    json=acknowledgement.model_dump(mode="json"),
                    headers={"Content-Type": "application/json"},
                    timeout=self.timeout,
                )
                response.raise_for_status()

                ack_response = AgentInstructionAcknowledgementResponse(**response.json())
                self._stats["instructions_acknowledged"] += 1
                self.logger.info(f"Successfully acknowledged instruction {instruction_id} with status {status}")
                return ack_response

            except requests.exceptions.RequestException as e:
                last_error = e
                if attempt < retry_count - 1:
                    delay = self._calculate_backoff_delay(attempt)
                    self.logger.warning(
                        f"Failed to acknowledge instruction {instruction_id} (attempt {attempt + 1}), "
                        f"retrying in {delay:.2f}s: {e}"
                    )
                    time.sleep(delay)
                else:
                    self.logger.error(
                        f"Failed to acknowledge instruction {instruction_id} after {retry_count} attempts: {e}"
                    )

            except Exception as e:
                last_error = e
                self.logger.error(f"Unexpected error acknowledging instruction {instruction_id}: {e}")
                break

        # If we get here, all retries failed
        raise last_error if last_error else Exception("Unknown acknowledgement error")

    def get_stats(self) -> dict:
        """Get client connection and performance statistics."""
        return {
            **self._stats,
            "agent_id": self.agent_id,
            "session_id": self.session_id,
            "connection_id": self._connection_id,
            "is_running": self._is_running,
            "max_retries": self.max_retries,
            "success_rate": (self._stats["successful_connections"] / max(self._stats["total_connections"], 1)) * 100,
        }

    def reset_stats(self) -> None:
        """Reset client statistics."""
        self._stats = {
            "total_connections": 0,
            "successful_connections": 0,
            "failed_connections": 0,
            "instructions_received": 0,
            "instructions_acknowledged": 0,
            "last_connection_time": None,
            "last_instruction_time": None,
        }

    def is_connected(self) -> bool:
        """Check if the client is currently connected and streaming."""
        return self._is_running and self._connection_id is not None

    def send_heartbeat(self, retry_count: int = 3) -> bool:
        """
        Send a heartbeat to the backend to update connection health status

        Args:
            retry_count: Number of retry attempts for heartbeat

        Returns:
            bool: True if heartbeat was sent successfully, False otherwise
        """
        heartbeat_url = f"{self.base_url}/agent/{self.agent_id}/session/{self.session_id}/heartbeat"

        for attempt in range(retry_count):
            try:
                response = requests.post(
                    heartbeat_url,
                    headers={"Content-Type": "application/json"},
                    timeout=self.timeout,
                )
                response.raise_for_status()

                heartbeat_response = response.json()
                self.logger.debug(
                    f"Heartbeat sent successfully: {heartbeat_response.get('heartbeat_timestamp', 'unknown')}"
                )
                return True

            except requests.exceptions.RequestException as e:
                if attempt < retry_count - 1:
                    delay = self._calculate_backoff_delay(attempt)
                    self.logger.warning(
                        f"Failed to send heartbeat (attempt {attempt + 1}), retrying in {delay:.2f}s: {e}"
                    )
                    time.sleep(delay)
                else:
                    self.logger.error(f"Failed to send heartbeat after {retry_count} attempts: {e}")

            except Exception as e:
                self.logger.error(f"Unexpected error sending heartbeat: {e}")
                break

        return False

    def stop(self):
        """Stop the SSE stream"""
        self.logger.info("Stopping SSE stream...")
        self._is_running = False
