import logging
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Generic, TypeVar
from uuid import uuid4
from base64 import urlsafe_b64encode

T = TypeVar("T")


@dataclass
class EntityStore(Generic[T]):
    _items: dict[str, T] = field(default_factory=dict)
    _api_client = None
    _entity_type: str = None
    _in_memory_only: bool = True
    _parent_entity: tuple[str, str] = None  # (entity_type, entity_id) tuple

    @staticmethod
    def generate_uuid():
        return urlsafe_b64encode(uuid4().bytes).decode("ascii").rstrip("=")

    def set_api_client(self, api_client, entity_type: str, in_memory_only: bool = True):
        self._api_client = api_client
        self._entity_type = entity_type
        self._in_memory_only = in_memory_only

    def set_parent_entity(self, parent_type: str, parent_id: str):
        self._parent_entity = (parent_type, parent_id)

    # TODO review and refactor
    def add(self, uuid: str | None, item: T) -> None:
        if not uuid:
            uuid = EntityStore.generate_uuid()

        is_new = uuid not in self._items

        entity_type = getattr(self, "_entity_type", "unknown")

        logging.info(f"EntityStore.add({entity_type}/{uuid})")

        has_api_client = hasattr(self, "_api_client") and self._api_client is not None
        if has_api_client:
            logging.info(f"EntityStore for {entity_type} has API client")
        else:
            logging.info(f"EntityStore for {entity_type} has NO API client")

        # Add the item to _items first
        self._items[uuid] = item

        # For Grid entities, we need special handling to ensure dependencies are created in order
        if entity_type == "grid" and has_api_client:
            in_memory_only = getattr(self, "_in_memory_only", False)
            if not in_memory_only:
                # Create the grid first
                parent_entity = getattr(self, "_parent_entity", None)
                logging.info(f"Creating {entity_type}/{uuid} via API (parent={parent_entity})")
                grid_success = self._api_client.create(entity_type, uuid, item, parent_entity)

                if grid_success:
                    logging.info(f"Successfully created {entity_type}/{uuid} via API")

                    # Now handle nested entities in order
                    self._sync_hierarchical_entities(item, uuid)
                else:
                    logging.error(f"Failed to create {entity_type}/{uuid} via API")
        elif has_api_client:
            # For non-grid entities, proceed with normal creation
            in_memory_only = getattr(self, "_in_memory_only", False)
            if not in_memory_only:
                try:
                    parent_entity = getattr(self, "_parent_entity", None)
                    if is_new:
                        logging.info(f"Creating {entity_type}/{uuid} via API (parent={parent_entity})")
                        success = self._api_client.create(entity_type, uuid, item, parent_entity)
                        if success:
                            logging.info(f"Successfully created {entity_type}/{uuid} via API")
                        else:
                            logging.error(f"Failed to create {entity_type}/{uuid} via API")
                    else:
                        logging.info(f"Updating {entity_type}/{uuid} via API (parent={parent_entity})")
                        success = self._api_client.update(entity_type, uuid, item, parent_entity)
                        if success:
                            logging.info(f"Successfully updated {entity_type}/{uuid} via API")
                        else:
                            logging.error(f"Failed to update {entity_type}/{uuid} via API")
                except Exception as e:
                    logging.error(f"API sync failed for {entity_type}/{uuid}: {str(e)}")
            else:
                logging.info(f"Skipping API call for {entity_type}/{uuid} (in_memory_only={in_memory_only})")
        else:
            logging.info(f"Skipping API call for {entity_type}/{uuid} (no API client)")

        # Configure nested EntityStores in the added item
        if hasattr(item, "__dict__"):
            for field_name, field_value in item.__dict__.items():
                if isinstance(field_value, EntityStore):
                    # Determine entity type from field name (handle plurals)
                    nested_entity_type = field_name
                    if nested_entity_type.endswith("s"):
                        nested_entity_type = nested_entity_type[:-1]

                    logging.info(f"Found nested EntityStore for {nested_entity_type} in {entity_type}/{uuid}")

                    # If we have an API client, configure the nested EntityStore
                    if has_api_client:
                        in_memory_only = getattr(self, "_in_memory_only", False)
                        logging.info(
                            f"Configuring nested EntityStore {nested_entity_type} with API client (in_memory_only={in_memory_only})"
                        )

                        # Configure the nested EntityStore
                        field_value.set_api_client(self._api_client, nested_entity_type, in_memory_only)

                        # Set parent entity relationship
                        field_value.set_parent_entity(entity_type, uuid)
                        logging.info(f"Set parent entity for {nested_entity_type} to {entity_type}/{uuid}")

    # TODO review and refactor
    def _sync_hierarchical_entities(self, grid_entity, grid_uuid):
        """
        Sync hierarchical entities in the correct order to satisfy dependencies.
        This method assumes the grid entity has already been created.
        """
        # First, find all gridsquares
        if not hasattr(grid_entity, "gridsquares") or not isinstance(grid_entity.gridsquares, EntityStore):
            logging.warning("Grid entity does not have gridsquares attribute or it's not an EntityStore")
            return

        # Map to collect created entity IDs for dependency tracking
        created_entities = {
            "gridsquare": set(),
            "foilhole": set(),
        }

        # First pass: Create all gridsquares
        logging.info(f"Creating gridsquares for grid/{grid_uuid}")
        for gs_uuid, gs in grid_entity.gridsquares._items.items():
            try:
                logging.info(f"Creating gridsquare/{gs_uuid} via API (parent=('grid', '{grid_uuid}'))")
                success = self._api_client.create("gridsquare", gs_uuid, gs, ("grid", grid_uuid))
                if success:
                    logging.info(f"Successfully created gridsquare/{gs_uuid} via API")
                    created_entities["gridsquare"].add(gs_uuid)
                else:
                    logging.error(f"Failed to create gridsquare/{gs_uuid} via API")
            except Exception as e:
                logging.error(f"API sync failed for gridsquare/{gs_uuid}: {str(e)}")

        # Second pass: Create all foilholes with valid gridsquare parents
        if hasattr(grid_entity, "foilholes") and isinstance(grid_entity.foilholes, EntityStore):
            logging.info(f"Creating foilholes for grid/{grid_uuid}")
            for fh_uuid, fh in grid_entity.foilholes._items.items():
                # Check if this foilhole has a valid gridsquare parent
                if hasattr(fh, "gridsquare_id") and fh.gridsquare_id in created_entities["gridsquare"]:
                    try:
                        logging.info(
                            f"Creating foilhole/{fh_uuid} via API (parent=('gridsquare', '{fh.gridsquare_id}'))"
                        )
                        success = self._api_client.create("foilhole", fh_uuid, fh, ("gridsquare", fh.gridsquare_id))
                        if success:
                            logging.info(f"Successfully created foilhole/{fh_uuid} via API")
                            created_entities["foilhole"].add(fh_uuid)
                        else:
                            logging.error(f"Failed to create foilhole/{fh_uuid} via API")
                    except Exception as e:
                        logging.error(f"API sync failed for foilhole/{fh_uuid}: {str(e)}")
                else:
                    logging.warning(f"Skipping foilhole/{fh_uuid} - missing valid gridsquare parent")

        # Third pass: Create all micrographs with valid foilhole parents
        if hasattr(grid_entity, "micrographs") and isinstance(grid_entity.micrographs, EntityStore):
            logging.info(f"Creating micrographs for grid/{grid_uuid}")
            for mic_uuid, mic in grid_entity.micrographs._items.items():
                # Check if this micrograph has a valid foilhole parent
                if hasattr(mic, "foilhole_id") and mic.foilhole_id in created_entities["foilhole"]:
                    try:
                        logging.info(
                            f"Creating micrograph/{mic_uuid} via API (parent=('foilhole', '{mic.foilhole_id}'))"
                        )
                        success = self._api_client.create("micrograph", mic_uuid, mic, ("foilhole", mic.foilhole_id))
                        if success:
                            logging.info(f"Successfully created micrograph/{mic_uuid} via API")
                        else:
                            logging.error(f"Failed to create micrograph/{mic_uuid} via API")
                    except Exception as e:
                        logging.error(f"API sync failed for micrograph/{mic_uuid}: {str(e)}")
                else:
                    logging.warning(f"Skipping micrograph/{mic_uuid} - missing valid foilhole parent")

    def get(self, uuid: str) -> T | None:
        return self._items.get(uuid)

    def exists(self, uuid: str) -> bool:
        return uuid in self._items

    def ids(self) -> set[str]:
        return set(self._items.keys())

    def values(self) -> Iterator[T]:
        return iter(self._items.values())

    def items(self) -> Iterator[tuple[str, T]]:
        return iter(self._items.items())

    def __len__(self) -> int:
        return len(self._items)




class EpuAcquisitionSessionStore:
    """Purpose of this class is to hold state of EPU session detection as data parsing is performed.
    An object of this class will be shared among all fs event handlers and parsers.
    """

    root_dir: Path
    in_memory_only: bool = False
    api_client = None
    uuid: str | None = None

    def __init__(self, root_dir: str, in_memory_only: bool = False, api_url: str = None):
        self.root_dir = Path(root_dir)
        self.in_memory_only = in_memory_only
        self.acquisition = EpuSessionData()
        self.grids = EntityStore()

        if not self.in_memory_only:
            # from src.epu_data_intake.core_api_client_adapter import ApiClientAdapter as ApiClient
            from src.epu_data_intake.core_http_api_client import SmartEMAPIClient as APIClient

            self.api_client = APIClient(api_url)
            response = self.api_client.create("acquisition", self.acquisition.id, self.acquisition, None)
            if not response:
                logging.error(f"Failed to create acquisition {self.acquisition.id}")
            self.grids.set_api_client(self.api_client, "grid", in_memory_only)
            self.grids.set_parent_entity("acquisition", self.acquisition.id)

    def add_grid(self, grid: Grid):
        grid_id = EntityStore.generate_uuid()

        # Configure the grid's EntityStores for the hierarchy:
        # acquisition -> grid -> gridsquare -> foilhole -> micrograph
        if self.api_client and not self.in_memory_only:
            # Grid is already set up with parent as acquisition/session in `self.__init__`

            # GridSquares have Grid as parent
            grid.gridsquares.set_api_client(self.api_client, "gridsquare", self.in_memory_only)
            grid.gridsquares.set_parent_entity("grid", grid_id)

            # FoilHoles don't have Grid as direct parent, but we need to configure them
            # The actual parent relationship is set when the foilhole is added to a GridSquare
            grid.foilholes.set_api_client(self.api_client, "foilhole", self.in_memory_only)

            # Micrographs similarly don't have Grid as direct parent
            grid.micrographs.set_api_client(self.api_client, "micrograph", self.in_memory_only)

        self.grids.add(grid_id, grid)

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

        for grid_id, grid in self.grids.items():
            # Check if either directory is defined and contains the path
            if (grid.data_dir and path.is_relative_to(grid.data_dir)) or (
                grid.atlas_dir and path.is_relative_to(grid.atlas_dir)
            ):
                return grid_id

        logging.debug(f"No grid found for path: {path}")
        return None

    def __str__(self):
        result = (
            f"\nEPU Acquisition Summary:\n  UUID: {self.uuid}\n Root dir: {self.root_dir}\n  Grids: {len(self.grids)}\n"
        )

        # Add each grid's string representation. TODO debug this doesn't seem to work
        for grid_id, grid in self.grids.items():
            result += f"Grid ID: {grid_id}\n{grid}\n"

        return result
