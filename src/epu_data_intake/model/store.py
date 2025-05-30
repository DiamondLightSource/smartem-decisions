import json
from pathlib import Path

from epu_data_intake.core_http_api_client import SmartEMAPIClient
from epu_data_intake.model.schemas import AcquisitionData, FoilHoleData, GridData, GridSquareData, MicrographData
from smartem_decisions.utils import logger


class InMemoryDataStore:
    def __init__(self, root_dir: str):
        self.root_dir = Path(root_dir)
        self.acquisition = AcquisitionData()
        logger.info(self.acquisition)

        # Collections of data objects indexed by uuid
        self.grids: dict[str, GridData] = {}
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
            # Check if either directory is defined and contains the path
            if (grid.data_dir and path.is_relative_to(grid.data_dir)) or (
                grid.atlas_dir and path.is_relative_to(grid.atlas_dir)
            ):
                return grid_uuid

        logger.debug(f"No grid found for path: {path}")
        return None

    # Grid methods
    def create_grid(self, grid):
        self.grids[grid.uuid] = grid
        self.acquisition_rels[self.acquisition.uuid].add(grid.uuid)
        self.grid_rels[grid.uuid] = set()

    def update_grid(self, grid: GridData):
        if grid.uuid in self.grids:
            self.grids[grid.uuid] = grid

    def remove_grid(self, uuid: str):
        if uuid in self.grids:
            del self.grids[uuid]

        # Remove the relationship from acquisition_rels
        for _acquisition_uuid, children in self.acquisition_rels.items():
            if uuid in children:
                children.remove(uuid)
                break  # Assuming a grid belongs to only one acquisition

    def get_grid(self, uuid: str):
        return self.grids.get(uuid)

    def create_gridsquare(self, gridsquare: GridSquareData):
        self.gridsquares[gridsquare.uuid] = gridsquare
        if gridsquare.grid_uuid not in self.grid_rels:
            self.grid_rels[gridsquare.grid_uuid] = set()
        self.grid_rels[gridsquare.grid_uuid].add(gridsquare.uuid)
        self.gridsquare_rels[gridsquare.uuid] = set()

    def update_gridsquare(self, gridsquare: GridSquareData):
        if gridsquare.uuid in self.gridsquares:
            self.gridsquares[gridsquare.uuid] = gridsquare

    def remove_gridsquare(self, uuid: str):
        if uuid in self.gridsquares:
            del self.gridsquares[uuid]

        # Remove the relationship from grid_rels
        for _grid_uuid, children in self.grid_rels.items():
            if uuid in children:
                children.remove(uuid)
                break  # Assuming a gridsquare belongs to only one grid

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

    def create_foilhole(self, foilhole: FoilHoleData):
        self.foilholes[foilhole.uuid] = foilhole
        if foilhole.gridsquare_uuid not in self.gridsquare_rels:
            self.gridsquare_rels[foilhole.gridsquare_uuid] = set()
        self.gridsquare_rels[foilhole.gridsquare_uuid].add(foilhole.uuid)
        self.foilhole_rels[foilhole.uuid] = set()

    def update_foilhole(self, foilhole: FoilHoleData):
        if foilhole.uuid in self.foilholes:
            self.foilholes[foilhole.uuid] = foilhole

    def remove_foilhole(self, uuid: str):
        if uuid in self.foilholes:
            del self.foilholes[uuid]

        # Remove the relationship from grid_rels
        for _gridsquare_uuid, children in self.gridsquare_rels.items():
            if uuid in children:
                children.remove(uuid)
                break  # Assuming a foilhole belongs to only one gridsquare

    def get_foilhole(self, uuid: str):
        return self.foilholes.get(uuid)

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

        # Remove the relationship from grid_rels
        for _foilhole_uuid, children in self.foilhole_rels.items():
            if uuid in children:
                children.remove(uuid)
                break  # Assuming a micrograph belongs to only one foilhole

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

    def create_grid(self, grid):
        try:
            super().create_grid(grid)
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
        except Exception as e:
            logger.error(f"Error updating grid {grid.uuid}: {e}")

    def remove_grid(self, uuid: str):
        try:
            super().remove_grid(uuid)
            self.api_client.delete_grid(uuid)  # TODO not tested
        except Exception as e:
            logger.error(f"Error removing grid UUID {uuid}: {e}")
            # TODO rollback localstore mutations on API failure

    def create_gridsquare(self, gridsquare: GridSquareData):
        try:
            super().create_gridsquare(gridsquare)
            result = self.api_client.create_grid_gridsquare(gridsquare)
            if not result:
                logger.error(f"API call to create gridsquare {gridsquare.uuid} failed, local store changes rolled back")
        except Exception as e:
            logger.error(f"Error creating gridsquare UUID {gridsquare.uuid}: {e}")
            # Roll back the local store change if the API call fails
            del self.gridsquares[gridsquare.uuid]
            self.grid_rels[gridsquare.grid_uuid].remove(gridsquare.uuid)

    def update_gridsquare(self, gridsquare: GridSquareData):
        try:
            super().update_gridsquare(gridsquare)
            self.api_client.update_gridsquare(gridsquare)
        except Exception as e:
            logger.error(f"Error updating gridsquare UUID {gridsquare.uuid}: {e}")
            # TODO rollback localstore mutations on API failure

    def remove_gridsquare(self, uuid: str):
        try:
            super().remove_gridsquare(uuid)
            self.api_client.delete_gridsquare(uuid)  # TODO not tested
        except Exception as e:
            logger.error(f"Error removing gridsquare UUID {uuid}: {e}")

    def create_foilhole(self, foilhole: FoilHoleData):
        try:
            super().create_foilhole(foilhole)
            self.api_client.create_gridsquare_foilhole(foilhole)
        except Exception as e:
            logger.error(f"Error creating foilhole UUID {foilhole.uuid}: {e}")

    def update_foilhole(self, foilhole: FoilHoleData):
        try:
            super().update_foilhole(foilhole)
            self.api_client.update_foilhole(foilhole)
        except Exception as e:
            logger.error(f"Error updating foilhole UUID {foilhole.uuid}: {e}")

    def remove_foilhole(self, uuid: str):
        try:
            super().remove_foilhole(uuid)
            self.api_client.delete_foilhole(uuid)  # TODO not tested
        except Exception as e:
            logger.error(f"Error removing foilhole UUID {uuid}: {e}")

    # def create_micrograph(self, micrograph: MicrographData):
    #     try:
    #         super().create_micrograph(micrograph)
    #         self.api_client.create_foilhole_micrograph(micrograph)
    #     except Exception as e:
    #         logger.error(f"Error creating micrograph UUID {micrograph.uuid}: {e}")

    # TODO rollback retries in no race condition, otherwise implement throttling universally
    def create_micrograph(self, micrograph: MicrographData):
        import time

        max_retries = 3
        retry_delay = 1.0  # seconds

        for attempt in range(max_retries):
            try:
                super().create_micrograph(micrograph)
                result = self.api_client.create_foilhole_micrograph(micrograph)
                if result:
                    return
                raise Exception("API call failed with no success response")
            except Exception as e:
                if attempt < max_retries - 1:
                    logger.warning(f"Retry {attempt + 1}/{max_retries} creating micrograph {micrograph.uuid}: {e}")
                    # Roll back the local store change before retrying
                    if micrograph.uuid in self.micrographs:
                        del self.micrographs[micrograph.uuid]
                    if micrograph.uuid in self.foilhole_rels.get(micrograph.foilhole_uuid, []):
                        self.foilhole_rels[micrograph.foilhole_uuid].remove(micrograph.uuid)
                    time.sleep(retry_delay)
                else:
                    logger.error(f"Error creating micrograph UUID {micrograph.uuid} after {max_retries} attempts: {e}")

    def update_micrograph(self, micrograph: MicrographData):
        try:
            super().update_micrograph(micrograph)
            self.api_client.update_micrograph(micrograph)
        except Exception as e:
            logger.error(f"Error updating micrograph UUID {micrograph.uuid}: {e}")

    def remove_micrograph(self, uuid: str):
        try:
            super().remove_micrograph(uuid)
            self.api_client.delete_micrograph(uuid)  # TODO not tested
        except Exception as e:
            logger.error(f"Error removing micrograph UUID {uuid}: {e}")

    def close(self):
        if self.api_client:
            self.api_client.close()
