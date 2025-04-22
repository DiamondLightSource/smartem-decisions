import asyncio
import logging
from typing import TypeVar

from src.epu_data_intake.core_api_client import (
    SmartEMCoreAPIClient,
    AcquisitionCreateRequest,
    GridCreateRequest,
    GridSquareCreateRequest,
    FoilHoleCreateRequest,
    MicrographCreateRequest,
    AtlasCreateRequest,
    AtlasTileCreateRequest,
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

T = TypeVar('T')


class ApiClientAdapter:
    """Adapter for SmartEMCoreAPIClient that provides a sync interface for EntityStore"""

    def __init__(self, api_url: str):
        self.api_url = api_url
        self.logger = logging.getLogger(__name__)
        self._client = None
        self._loop = None
        self._acquisition_id = None

        # Cache of entity IDs to database IDs
        self._id_map = {
            "acquisition": {},
            "grid": {},
            "gridsquare": {},
            "foilhole": {},
            "micrograph": {},
            "atlas": {},
            "atlas_tile": {},
        }

    def _get_or_create_client(self):
        if self._client is None:
            self._client = SmartEMCoreAPIClient(self.api_url)
        return self._client

    def _get_or_create_loop(self):
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

    def create(self, entity_type: str, entity_id: str, entity: T,
               parent: tuple[str, str] | None = None) -> bool:
        """Create a new entity via API"""
        try:
            client = self._get_or_create_client()

            if entity_type == "acquisition" and isinstance(entity, EpuSessionData):
                # Handle acquisition creation - no parent
                request = AcquisitionCreateRequest(
                    name=entity.name,
                    epu_id=entity.id,
                    start_time=entity.start_time,
                    storage_path=entity.storage_path,
                    atlas_path=entity.atlas_path,
                    clustering_mode=entity.clustering_mode,
                    clustering_radius=entity.clustering_radius,
                )
                response = self._run_async(client.create_acquisition(request))
                self._acquisition_id = response.id
                self._id_map["acquisition"][entity_id] = response.id

            elif entity_type == "grid" and isinstance(entity, Grid):
                if parent and parent[0] == "acquisition":
                    acquisition_db_id = self._id_map["acquisition"].get(parent[1])
                    if not acquisition_db_id:
                        self.logger.error(f"Cannot create grid: Acquisition {parent[1]} not found in ID map")
                        return False

                    request = GridCreateRequest(
                        name=entity.session_data.name if entity.session_data else "Unknown",
                        acquisition_id=acquisition_db_id,
                        data_dir=str(entity.data_dir) if entity.data_dir else None,
                        atlas_dir=str(entity.atlas_dir) if entity.atlas_dir else None,
                    )
                    response = self._run_async(client.create_acquisition_grid(acquisition_db_id, request))
                    self._id_map["grid"][entity_id] = response.id
                else:
                    self.logger.error("Cannot create grid: No valid acquisition parent")
                    return False

            elif entity_type == "gridsquare" and isinstance(entity, GridSquareData):
                if parent and parent[0] == "grid":
                    grid_db_id = self._id_map["grid"].get(parent[1])
                    if not grid_db_id:
                        self.logger.error(f"Cannot create gridsquare: Grid {parent[1]} not found in ID map")
                        return False

                    metadata = entity.metadata
                    manifest = entity.manifest
                    request = GridSquareCreateRequest(
                        grid_id=grid_db_id,
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
                    response = self._run_async(client.create_grid_gridsquare(grid_db_id, request))
                    self._id_map["gridsquare"][entity.id] = response.id
                else:
                    self.logger.error("Cannot create gridsquare: No valid grid parent")
                    return False

            elif entity_type == "foilhole" and isinstance(entity, FoilHoleData):
                if parent and parent[0] == "gridsquare":
                    gridsquare_db_id = self._id_map["gridsquare"].get(parent[1])
                    if not gridsquare_db_id:
                        self.logger.error(f"Cannot create foilhole: Gridsquare {parent[1]} not found in ID map")
                        return False

                    request = FoilHoleCreateRequest(
                        gridsquare_id=gridsquare_db_id,
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
                    response = self._run_async(client.create_gridsquare_foilhole(gridsquare_db_id, request))
                    self._id_map["foilhole"][entity.id] = response.id
                else:
                    self.logger.error("Cannot create foilhole: No valid gridsquare parent")
                    return False


            elif entity_type == "micrograph" and isinstance(entity, MicrographData):
                if parent and parent[0] == "foilhole":
                    foilhole_db_id = self._id_map["foilhole"].get(parent[1])
                    if not foilhole_db_id:
                        self.logger.error(f"Cannot create micrograph: Foilhole {parent[1]} not found in ID map")
                        return False

                    manifest = entity.manifest
                    request = MicrographCreateRequest(
                        foilhole_id=foilhole_db_id,
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
                    response = self._run_async(client.create_foilhole_micrograph(foilhole_db_id, request))
                    self._id_map["micrograph"][entity.id] = response.id
                else:
                    self.logger.error("Cannot create micrograph: No valid foilhole parent")
                    return False

            else:
                self.logger.error(f"Unsupported entity type: {entity_type}")
                return False

            return True

        except Exception as e:
            self.logger.error(f"Failed to create {entity_type}/{entity_id}: {str(e)}")
            return False

    def update(self, entity_type: str, entity_id: str, entity: T,
               parent: tuple[str, str] | None = None) -> bool:
        """Update an existing entity via API"""
        # TODO Similar implementation to create but using update methods
        #   You would use the ID mapping to get the database ID for the update
        self.logger.info(f"Would update {entity_type}/{entity_id} via API")
        return True

    def close(self):
        """Close the API client connection"""
        if self._client:
            self._run_async(self._client.close())
            self._client = None
