import json
import time
from collections.abc import Callable
from pathlib import Path

import requests

from smartem_backend.api_client import SmartEMAPIClient
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
from smartem_common.utils import get_logger

# Initialize logger for agent
logger = get_logger("smartem_agent")

# Retry configuration constants
DEFAULT_MAX_RETRIES = 5
DEFAULT_INITIAL_DELAY = 1.0
DEFAULT_BACKOFF_FACTOR = 1.5


def retry_with_backoff(
    max_retries: int = DEFAULT_MAX_RETRIES,
    initial_delay: float = DEFAULT_INITIAL_DELAY,
    backoff_factor: float = DEFAULT_BACKOFF_FACTOR,
):
    """Decorator for retrying operations with exponential backoff"""

    def decorator(func):
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except requests.HTTPError as e:
                    last_exception = e
                    if e.response.status_code == 404 and attempt < max_retries - 1:
                        delay = initial_delay * (backoff_factor**attempt)
                        logger.warning(f"Attempt {attempt + 1} failed with 404. Retrying in {delay:.1f}s...")
                        time.sleep(delay)
                        continue
                    else:
                        raise
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        delay = initial_delay * (backoff_factor**attempt)
                        logger.warning(
                            f"Attempt {attempt + 1} failed with {type(e).__name__}: {e}. Retrying in {delay:.1f}s..."
                        )
                        time.sleep(delay)
                        continue
                    else:
                        raise

            raise last_exception

        return wrapper

    return decorator


class InMemoryDataStore:
    def __init__(self, root_dir: str):
        self.root_dir = Path(root_dir)
        self.acquisition = AcquisitionData()
        logger.info(self.acquisition)

        self.grids: dict[str, GridData] = {}
        self.atlases: dict[str, AtlasData] = {}
        self.atlastiles: dict[str, AtlasTileData] = {}
        self.gridsquares: dict[str, GridSquareData] = {}
        self.foilholes: dict[str, FoilHoleData] = {}
        self.micrographs: dict[str, MicrographData] = {}

        # Collections to track parent-child relationships between entities
        self.acquisition_rels: dict[str, set[str]] = {}
        self.grid_rels: dict[str, set[str]] = {}
        self.gridsquare_rels: dict[str, set[str]] = {}
        self.foilhole_rels: dict[str, set[str]] = {}
        self.micrograph_rels: dict[str, set[str]] = {}

        # Initialize the acquisition_rels dict with a set for the acquisition
        self.acquisition_rels[self.acquisition.uuid] = set()

    def get_grid_by_path(self, path: str):
        """
        Retrieve a grid from the EntityStore where the provided path is inside
        the grid's data_dir or atlas_dir.

        Args:
            path (str): The specific path that should be inside a grid's directory

        Returns:
            The matching grid entity or None if no match is found
        """
        path = Path(path)

        for grid_uuid, grid in self.grids.items():
            if (grid.data_dir and path.is_relative_to(grid.data_dir)) or (
                grid.atlas_dir and path.is_relative_to(grid.atlas_dir)
            ):
                return grid_uuid

        logger.debug(f"No grid found for path: {path}")
        return None

    # Grid methods
    def create_grid(self, grid, path_mapper: Callable[[Path], Path] = lambda p: p):
        self.grids[grid.uuid] = grid
        self.acquisition_rels[self.acquisition.uuid].add(grid.uuid)
        self.grid_rels[grid.uuid] = set()

    def update_grid(self, grid: GridData):
        if grid.uuid in self.grids:
            self.grids[grid.uuid] = grid

    def remove_grid(self, uuid: str):
        if uuid in self.grids:
            del self.grids[uuid]

        for _acquisition_uuid, children in self.acquisition_rels.items():
            if uuid in children:
                children.remove(uuid)
                break

    def get_grid(self, uuid: str):
        return self.grids.get(uuid)

    def grid_registered(self, uuid: str):
        return None

    # Atlas methods
    def create_atlas(self, atlas: AtlasData):
        self.atlases[atlas.uuid] = atlas

    def update_atlas(self, atlas: AtlasData):
        if atlas.uuid in self.atlases:
            self.atlases[atlas.uuid] = atlas

    def remove_atlas(self, uuid: str):
        if uuid in self.atlases:
            del self.atlases[uuid]

    def get_atlas(self, uuid: str):
        return self.atlases.get(uuid)

    # Atlas tile methods
    def create_atlastile(self, atlastile: AtlasTileData):
        self.atlastiles[atlastile.uuid] = atlastile

    def update_atlastile(self, atlastile: AtlasTileData):
        if atlastile.uuid in self.atlases:
            self.atlastiles[atlastile.uuid] = atlastile

    def remove_atlastile(self, uuid: str):
        if uuid in self.atlastiles:
            del self.atlastiles[uuid]

    def get_atlastile(self, uuid: str):
        return self.atlastiles.get(uuid)

    def link_atlastile_to_gridsquare(self, gridsquare_position: AtlasTileGridSquarePositionData):
        return None

    def link_atlastile_to_gridsquares(self, gridsquare_positions: list[AtlasTileGridSquarePositionData]):
        return None

    def create_gridsquare(self, gridsquare: GridSquareData, lowmag: bool = False):
        self.gridsquares[gridsquare.uuid] = gridsquare
        if gridsquare.grid_uuid not in self.grid_rels:
            self.grid_rels[gridsquare.grid_uuid] = set()
        self.grid_rels[gridsquare.grid_uuid].add(gridsquare.uuid)
        self.gridsquare_rels[gridsquare.uuid] = set()

    def update_gridsquare(self, gridsquare: GridSquareData, lowmag: bool = False):
        if gridsquare.uuid in self.gridsquares:
            self.gridsquares[gridsquare.uuid] = gridsquare

    def remove_gridsquare(self, uuid: str):
        if uuid in self.gridsquares:
            del self.gridsquares[uuid]

        for _grid_uuid, children in self.grid_rels.items():
            if uuid in children:
                children.remove(uuid)
                break

    def gridsquare_registered(self, uuid: str):
        return None

    def get_gridsquare(self, uuid: str):
        return self.gridsquares.get(uuid)

    def find_gridsquare_by_natural_id(self, gridsquare_natural_id: str) -> GridSquareData | None:
        """Find a gridsquare by its id attribute (not uuid)
        Helper function to find a gridsquare by its "natural" `id` (as opposed to synthetic `uuid`)"""
        for _uuid, gridsquare in self.gridsquares.items():
            if gridsquare.gridsquare_id == gridsquare_natural_id:
                return gridsquare
        return None

    def find_foilhole_by_natural_id(self, foilhole_natural_id: str):
        """Find a foilhole by its id attribute (not uuid)
        Helper function to find a foilhole by its "natural" `id` (as opposed to synthetic `uuid`)"""
        for _uuid, foilhole in self.foilholes.items():
            if foilhole.id == foilhole_natural_id:
                return foilhole
        return None

    def find_micrograph_by_natural_id(self, micrograph_natural_id: str):
        """Find a micrograph by its id attribute (not uuid)
        Helper function to find a micrograph by its "natural" `id` (as opposed to synthetic `uuid`)"""
        for _uuid, micrograph in self.micrographs.items():
            if micrograph.id == micrograph_natural_id:
                return micrograph
        return None

    def create_foilhole(self, foilhole: FoilHoleData):
        self.foilholes[foilhole.uuid] = foilhole
        if foilhole.gridsquare_uuid not in self.gridsquare_rels:
            self.gridsquare_rels[foilhole.gridsquare_uuid] = set()
        self.gridsquare_rels[foilhole.gridsquare_uuid].add(foilhole.uuid)
        self.foilhole_rels[foilhole.uuid] = set()

    def create_foilholes(self, gridsquare_uuid: str, foilholes: list[FoilHoleData]):
        for foilhole in foilholes:
            self.foilholes[foilhole.uuid] = foilhole
            if gridsquare_uuid not in self.gridsquare_rels:
                self.gridsquare_rels[gridsquare_uuid] = set()
            self.gridsquare_rels[gridsquare_uuid].add(foilhole.uuid)
            self.foilhole_rels[foilhole.uuid] = set()

    def update_foilhole(self, foilhole: FoilHoleData):
        if foilhole.uuid in self.foilholes:
            self.foilholes[foilhole.uuid] = foilhole

    def remove_foilhole(self, uuid: str):
        if uuid in self.foilholes:
            del self.foilholes[uuid]

        for _gridsquare_uuid, children in self.gridsquare_rels.items():
            if uuid in children:
                children.remove(uuid)
                break

    def get_foilhole(self, uuid: str):
        return self.foilholes.get(uuid)

    def upsert_foilhole(self, foilhole: FoilHoleData) -> bool:
        """Create or update a foilhole, handling UUID management internally.

        Returns:
            bool: True if successful, False if parent gridsquare doesn't exist
        """
        if foilhole.gridsquare_uuid not in self.gridsquares:
            return False

        existing = self.find_foilhole_by_natural_id(foilhole.id)

        if existing:
            foilhole.uuid = existing.uuid
            self.update_foilhole(foilhole)
        else:
            self.create_foilhole(foilhole)

        return True

    def upsert_micrograph(self, micrograph: MicrographData) -> bool:
        """Create or update micrograph with parent validation.

        Args:
            micrograph: The micrograph data to create or update

        Returns:
            bool: True if successful, False if parent foilhole doesn't exist
        """
        if micrograph.foilhole_uuid not in self.foilholes:
            return False

        existing = self.find_micrograph_by_natural_id(micrograph.id)

        if existing:
            micrograph.uuid = existing.uuid
            self.update_micrograph(micrograph)
        else:
            self.create_micrograph(micrograph)

        return True

    def remove_foilhole_by_natural_id(self, natural_id: str) -> bool:
        """Remove foilhole by natural ID, returns True if found and removed."""
        existing = self.find_foilhole_by_natural_id(natural_id)
        if existing:
            self.remove_foilhole(existing.uuid)
            return True
        return False

    def create_micrograph(self, micrograph: MicrographData):
        self.micrographs[micrograph.uuid] = micrograph
        if micrograph.foilhole_uuid not in self.foilhole_rels:
            self.foilhole_rels[micrograph.foilhole_uuid] = set()
        self.foilhole_rels[micrograph.foilhole_uuid].add(micrograph.uuid)  # TODO

    def update_micrograph(self, micrograph: MicrographData):
        if micrograph.uuid in self.micrographs:
            self.micrographs[micrograph.uuid] = micrograph

    def remove_micrograph(self, uuid: str):
        if uuid in self.micrographs:
            del self.micrographs[uuid]

        for _foilhole_uuid, children in self.foilhole_rels.items():
            if uuid in children:
                children.remove(uuid)
                break

    def get_micrograph(self, uuid: str):
        return self.micrographs.get(uuid)

    def __str__(self):
        store_info = {
            "type": self.__class__.__name__,
            "root_dir": str(self.root_dir),
            "acquisition": {
                "uuid": self.acquisition.uuid,
                "name": self.acquisition.name,
                "start_time": str(self.acquisition.start_time) if self.acquisition.start_time else None,
            },
            "entities": {
                "grids": len(self.grids),
                "gridsquares": len(self.gridsquares),
                "foilholes": len(self.foilholes),
                "micrographs": len(self.micrographs),
            },
        }

        if hasattr(self, "api_client"):
            store_info["api_url"] = self.api_client.base_url

        return json.dumps(store_info, indent=2)


class PersistentDataStore(InMemoryDataStore):
    def __init__(self, root_dir: str, api_url: str):
        """
        Initialize with root directory and API URL.
        Will exit the program if acquisition creation fails.
        """
        try:
            super().__init__(root_dir)
            self.api_client = SmartEMAPIClient(base_url=api_url, logger=logger)
            result = self.api_client.create_acquisition(self.acquisition)
            if not result:
                raise RuntimeError(f"API call to create acquisition {self.acquisition.uuid} failed with no response")
            logger.info(f"Successfully created acquisition {self.acquisition.uuid} in API")
        except Exception as e:
            error_msg = (
                "CRITICAL FAILURE: "
                f"Unable to initialize API client or create acquisition {self.acquisition.uuid}: {str(e)}"
            )
            logger.critical(error_msg)
            logger.debug("Stack trace:", exc_info=True)
            import sys

            sys.exit(1)

    def create_grid(self, grid, path_mapper: Callable[[Path], Path] = lambda p: p):
        try:
            super().create_grid(grid, path_mapper=path_mapper)
            grid.atlas_dir = path_mapper(grid.atlas_dir) if grid.atlas_dir else grid.atlas_dir
            result = self.api_client.create_acquisition_grid(grid)
            if not result:
                logger.error(f"API call to create grid UUID {grid.uuid} failed, local store changes rolled back")
        except Exception as e:
            logger.error(f"Error creating grid {grid.uuid}: {e}")
            # Roll back the local store change if the API call fails:
            del self.grids[grid.uuid]
            self.acquisition_rels[self.acquisition.uuid].remove(grid.uuid)

    def update_grid(self, grid: GridData):
        try:
            super().update_grid(grid)
            result = self.api_client.update_grid(grid)  # TODO not tested
            if not result:
                logger.error(f"API call to update grid UUID {grid.uuid} failed, but grid was updated in local store")
        except requests.HTTPError as e:
            if e.response.status_code == 404:
                logger.warning(f"Grid {grid.uuid} exists locally but not yet in API - likely queued for creation")
            else:
                logger.error(f"HTTP {e.response.status_code} error updating grid {grid.uuid}: {e}")
        except Exception as e:
            logger.error(f"Error updating grid {grid.uuid}: {e}")

    def remove_grid(self, uuid: str):
        try:
            super().remove_grid(uuid)
            self.api_client.delete_grid(uuid)  # TODO not tested
        except Exception as e:
            logger.error(f"Error removing grid UUID {uuid}: {e}")
            # TODO rollback localstore mutations on API failure

    def grid_registered(self, uuid: str):
        try:
            self.api_client.grid_registered(uuid)
        except Exception as e:
            logger.error(f"Error notifying of registration of grid UUID {uuid}: {e}")

    def create_atlas(self, atlas: AtlasData):
        try:
            super().create_atlas(atlas)
            result = self.api_client.create_grid_atlas(atlas)
            if not result:
                logger.error(f"API call to create atlas UUID {atlas.uuid} failed, local store changes rolled back")
        except Exception as e:
            logger.error(f"Error creating atlas {atlas.uuid}: {e}")
            # Roll back the local store change if the API call fails:
            del self.atlases[atlas.uuid]

    def update_atlas(self, atlas: AtlasData):
        try:
            super().update_atlas(atlas)
            result = self.api_client.update_atlas(atlas)
            if not result:
                logger.error(f"API call to update atlas UUID {atlas.uuid} failed, but grid was updated in local store")
        except requests.HTTPError as e:
            if e.response.status_code == 404:
                logger.warning(f"Atlas {atlas.uuid} exists locally but not yet in API - likely queued for creation")
            else:
                logger.error(f"HTTP {e.response.status_code} error updating atlas {atlas.uuid}: {e}")
        except Exception as e:
            logger.error(f"Error updating atlas {atlas.uuid}: {e}")

    def remove_atlas(self, uuid: str):
        try:
            super().remove_atlas(uuid)
            self.api_client.delete_atlas(uuid)
        except Exception as e:
            logger.error(f"Error removing atlas UUID {uuid}: {e}")

    def create_atlastile(self, atlastile: AtlasTileData):
        try:
            super().create_atlastile(atlastile)
            result = self.api_client.create_atlas_tile_for_atlas(atlastile)
            if not result:
                logger.error(
                    f"API call to create atlas tile UUID {atlastile.uuid} failed, local store changes rolled back"
                )
        except Exception as e:
            logger.error(f"Error creating atlas tile {atlastile.uuid}: {e}")
            # Roll back the local store change if the API call fails:
            del self.atlastiles[atlastile.uuid]

    def update_atlastile(self, atlastile: AtlasTileData):
        try:
            super().update_atlastile(atlastile)
            result = self.api_client.update_atlas_tile(atlastile)
            if not result:
                logger.error(
                    f"API call to update atlas tile UUID {atlastile.uuid} failed, but grid was updated in local store"
                )
        except requests.HTTPError as e:
            if e.response.status_code == 404:
                logger.warning(
                    f"Atlas tile {atlastile.uuid} exists locally but not yet in API - likely queued for creation"
                )
            else:
                logger.error(f"HTTP {e.response.status_code} error updating atlas tile {atlastile.uuid}: {e}")
        except Exception as e:
            logger.error(f"Error updating atlas tile {atlastile.uuid}: {e}")

    def remove_atlastile(self, uuid: str):
        try:
            super().remove_atlastile(uuid)
            self.api_client.delete_atlas_tile(uuid)
        except Exception as e:
            logger.error(f"Error removing atlas tile UUID {uuid}: {e}")

    def link_atlastile_to_gridsquare(self, gridsquare_position: AtlasTileGridSquarePositionData):
        try:
            result = self.api_client.link_atlas_tile_and_gridsquare(gridsquare_position)
            if not result:
                logger.error(
                    f"API call to link atlas tile UUID {gridsquare_position.tile_uuid} to grid square UUID "
                    f"{gridsquare_position.gridsquare_uuid} failed, but grid was updated in local store"
                )
        except requests.HTTPError as e:
            logger.error(
                f"HTTP {e.response.status_code} error linking atlas tile {gridsquare_position.tile_uuid} "
                f"to grid square {gridsquare_position.gridsquare_uuid}: {e}"
            )
        except Exception as e:
            logger.error(
                f"Error linking atlas tile {gridsquare_position.tile_uuid} to "
                f"grid square {gridsquare_position.gridsquare_uuid}: {e}"
            )

    def link_atlastile_to_gridsquares(self, gridsquare_positions: list[AtlasTileGridSquarePositionData]):
        try:
            if not gridsquare_positions:
                return None
            result = self.api_client.link_atlas_tile_and_gridsquares(gridsquare_positions)
            if not result:
                logger.error(
                    f"API call to link atlas tile UUID {gridsquare_positions[0].tile_uuid} with gridsquares "
                    f"failed, but grid was updated in local store"
                )
        except requests.HTTPError as e:
            logger.error(
                f"HTTP {e.response.status_code} error linking atlas tile {gridsquare_positions[0].tile_uuid} "
                f"to grid squares: {e}"
            )
        except Exception as e:
            logger.error(f"Error linking atlas tile {gridsquare_positions[0].tile_uuid} to " f"grid squares: {e}")

    def create_gridsquare(self, gridsquare: GridSquareData, lowmag: bool = False):
        try:
            super().create_gridsquare(gridsquare, lowmag=lowmag)
            result = self.api_client.create_grid_gridsquare(gridsquare, lowmag=lowmag)
            if not result:
                logger.error(f"API call to create gridsquare {gridsquare.uuid} failed, local store changes rolled back")
        except Exception as e:
            logger.error(f"Error creating gridsquare UUID {gridsquare.uuid}: {e}")
            # Roll back the local store change if the API call fails
            del self.gridsquares[gridsquare.uuid]
            self.grid_rels[gridsquare.grid_uuid].remove(gridsquare.uuid)

    def update_gridsquare(self, gridsquare: GridSquareData, lowmag: bool = False):
        try:
            super().update_gridsquare(gridsquare, lowmag=lowmag)
            self.api_client.update_gridsquare(gridsquare, lowmag=lowmag)
        except requests.HTTPError as e:
            if e.response.status_code == 404:
                logger.warning(
                    f"GridSquare {gridsquare.uuid} exists locally but not yet in API - likely queued for creation"
                )
            else:
                logger.error(f"HTTP {e.response.status_code} error updating gridsquare UUID {gridsquare.uuid}: {e}")
        except Exception as e:
            logger.error(f"Error updating gridsquare UUID {gridsquare.uuid}: {e}")
            # TODO rollback localstore mutations on API failure

    def remove_gridsquare(self, uuid: str):
        try:
            super().remove_gridsquare(uuid)
            self.api_client.delete_gridsquare(uuid)  # TODO not tested
        except Exception as e:
            logger.error(f"Error removing gridsquare UUID {uuid}: {e}")

    def gridsquare_registered(self, uuid: str):
        try:
            self.gridsquares[uuid].registered = True
            num_square_registered = sum(s.registered for s in self.gridsquares.values())
            self.api_client.gridsquare_registered(uuid, count=num_square_registered)
        except Exception as e:
            logger.error(f"Error notifying of registration of grid square UUID {uuid}: {e}")

    def create_foilhole(self, foilhole: FoilHoleData):
        try:
            super().create_foilhole(foilhole)
            self._create_foilhole_with_retry(foilhole)
        except requests.HTTPError as e:
            if e.response.status_code == 404:
                logger.error(
                    f"Parent gridsquare {foilhole.gridsquare_uuid} not found when creating foilhole {foilhole.uuid}. "
                    f"This indicates a race condition or missing gridsquare."
                )
            else:
                logger.error(f"HTTP {e.response.status_code} error creating foilhole UUID {foilhole.uuid}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error creating foilhole UUID {foilhole.uuid}: {e}")

    @retry_with_backoff()
    def _create_foilhole_with_retry(self, foilhole: FoilHoleData):
        """Create foilhole with retry logic for handling race conditions"""
        return self.api_client.create_gridsquare_foilholes([foilhole])

    def update_foilhole(self, foilhole: FoilHoleData):
        try:
            super().update_foilhole(foilhole)
            self.api_client.update_foilhole(foilhole)
        except requests.HTTPError as e:
            if e.response.status_code == 404:
                logger.warning(
                    f"FoilHole {foilhole.uuid} exists locally but not yet in API - likely queued for creation"
                )
            else:
                logger.error(f"HTTP {e.response.status_code} error updating foilhole UUID {foilhole.uuid}: {e}")
        except Exception as e:
            logger.error(f"Error updating foilhole UUID {foilhole.uuid}: {e}")

    def create_foilholes(self, gridsquare_uuid: str, foilholes: list[FoilHoleData]):
        if not foilholes:
            return None
        try:
            super().create_foilholes(gridsquare_uuid, foilholes)
            self._create_foilholes_with_retry(gridsquare_uuid, foilholes)
        except requests.HTTPError as e:
            if e.response.status_code == 404:
                logger.error(
                    f"Parent gridsquare {gridsquare_uuid} not found when creating foilholes. "
                    f"This indicates a race condition or missing gridsquare."
                )
            else:
                logger.error(f"HTTP {e.response.status_code} error creating foilholes: {e}")
        except Exception as e:
            logger.error(f"Unexpected error creating foilholes: {e}")

    @retry_with_backoff()
    def _create_foilholes_with_retry(self, gridsquare_uuid: str, foilholes: list[FoilHoleData]):
        """Create foilhole with retry logic for handling race conditions"""
        return self.api_client.create_gridsquare_foilholes(gridsquare_uuid, foilholes)

    def remove_foilhole(self, uuid: str):
        try:
            super().remove_foilhole(uuid)
            self.api_client.delete_foilhole(uuid)  # TODO not tested
        except requests.HTTPError as e:
            if e.response.status_code == 404:
                logger.warning(
                    f"Foilhole {uuid} already deleted or doesn't exist (404). This is expected during cleanup."
                )
            else:
                logger.error(f"HTTP {e.response.status_code} error removing foilhole UUID {uuid}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error removing foilhole UUID {uuid}: {e}")

    def upsert_foilhole(self, foilhole: FoilHoleData) -> bool:
        """Create or update a foilhole with retry logic for race conditions.

        Returns:
            bool: True if successful, False if parent gridsquare doesn't exist after retries
        """
        existing = self.find_foilhole_by_natural_id(foilhole.id)

        if not super().upsert_foilhole(foilhole):
            return False

        try:
            if existing:
                self.api_client.update_foilhole(foilhole)
            else:
                self._create_foilhole_with_retry(foilhole)

            return True

        except requests.HTTPError as e:
            if e.response.status_code == 404:
                logger.error(
                    f"Parent gridsquare {foilhole.gridsquare_uuid} not found when upserting foilhole {foilhole.id}. "
                    f"This indicates a race condition or missing gridsquare."
                )
                if not existing and foilhole.uuid in self.foilholes:
                    super().remove_foilhole(foilhole.uuid)
            else:
                logger.error(f"HTTP {e.response.status_code} error upserting foilhole {foilhole.id}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error upserting foilhole {foilhole.id}: {e}")
            if not existing and foilhole.uuid in self.foilholes:
                super().remove_foilhole(foilhole.uuid)
            return False

    def remove_foilhole_by_natural_id(self, natural_id: str) -> bool:
        """Remove foilhole by natural ID with graceful 404 handling."""
        existing = self.find_foilhole_by_natural_id(natural_id)
        if not existing:
            return False

        foilhole_uuid = existing.uuid

        if not super().remove_foilhole_by_natural_id(natural_id):
            return False

        try:
            self.api_client.delete_foilhole(foilhole_uuid)
            return True
        except requests.HTTPError as e:
            if e.response.status_code == 404:
                logger.warning(f"Foilhole {natural_id} already deleted (404). Local state cleaned up.")
                return True
            else:
                logger.error(f"HTTP {e.response.status_code} error removing foilhole {natural_id}: {e}")
                # TODO: Consider rolling back parent changes on API failure
                return False
        except Exception as e:
            logger.error(f"Unexpected error removing foilhole {natural_id}: {e}")
            # TODO: Consider rolling back parent changes on API failure
            return False

    def create_micrograph(self, micrograph: MicrographData):
        try:
            super().create_micrograph(micrograph)
            self.api_client.create_foilhole_micrograph(micrograph)
        except Exception as e:
            logger.error(f"Error creating micrograph UUID {micrograph.uuid}: {e}")

    def update_micrograph(self, micrograph: MicrographData):
        try:
            super().update_micrograph(micrograph)
            self.api_client.update_micrograph(micrograph)
        except requests.HTTPError as e:
            if e.response.status_code == 404:
                logger.warning(
                    f"Micrograph {micrograph.uuid} exists locally but not yet in API - likely queued for creation"
                )
            else:
                logger.error(f"HTTP {e.response.status_code} error updating micrograph UUID {micrograph.uuid}: {e}")
        except Exception as e:
            logger.error(f"Error updating micrograph UUID {micrograph.uuid}: {e}")

    def remove_micrograph(self, uuid: str):
        try:
            super().remove_micrograph(uuid)
            self.api_client.delete_micrograph(uuid)  # TODO not tested
        except Exception as e:
            logger.error(f"Error removing micrograph UUID {uuid}: {e}")

    def upsert_micrograph(self, micrograph: MicrographData) -> bool:
        """Create or update micrograph with API sync and proper error handling.

        Args:
            micrograph: The micrograph data to create or update

        Returns:
            bool: True if successful, False if failed
        """
        if micrograph.foilhole_uuid not in self.foilholes:
            return False

        existing = self.find_micrograph_by_natural_id(micrograph.id)

        # Update local store first
        if existing:
            micrograph.uuid = existing.uuid
            # Call parent's update directly to avoid API call
            InMemoryDataStore.update_micrograph(self, micrograph)
        else:
            # Call parent's create directly to avoid API call
            InMemoryDataStore.create_micrograph(self, micrograph)

        # Now handle API sync with fallback logic
        try:
            if existing:
                self.api_client.update_micrograph(micrograph)
            else:
                result = self.api_client.create_foilhole_micrograph(micrograph)
                if not result:
                    raise Exception("API call failed with no success response")
            return True
        except requests.HTTPError as e:
            if e.response.status_code == 404 and existing:
                logger.warning(
                    f"Micrograph {micrograph.id} exists locally but not yet in API - likely queued for creation"
                )
                return True
            else:
                logger.error(f"HTTP {e.response.status_code} error syncing micrograph {micrograph.id} with API: {e}")
                if not existing and micrograph.uuid in self.micrographs:
                    InMemoryDataStore.remove_micrograph(self, micrograph.uuid)
                return False
        except Exception as e:
            logger.error(f"Error syncing micrograph {micrograph.id} with API: {e}")
            if not existing and micrograph.uuid in self.micrographs:
                InMemoryDataStore.remove_micrograph(self, micrograph.uuid)
            return False

    def close(self):
        if self.api_client:
            self.api_client.close()
