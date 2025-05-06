import logging
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import datetime
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


@dataclass
class MicrographManifest:
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

    def __post_init__(self):
        """Validate that size and binning values are positive."""
        for natural_num in ["image_size_x", "image_size_y", "binning_x", "binning_y"]:
            value = getattr(self, natural_num)
            if natural_num is not None and value <= 0:
                raise ValueError(f"{natural_num} must be positive, got {value}")


# TODO:
#   - Record Path to high-res micrograph image (same name as jpeg, but tiff or mrc)
@dataclass
class MicrographData:
    """Represents metadata for a micrograph image.

    :param id: Unique identifier for the micrograph
    :param gridsquare_id: Identifier for the grid square
    :param foilhole_id: Identifier for the foil hole
    :param location_id: The location ID (positioning) of where micrograph was taken within foilhole.
                       These IDs repeat for every foilhole.
    :param high_res_path: Path to the high resolution image
    :param manifest_file: Path to the manifest file
    :param manifest: Associated manifest data
    :type manifest: MicrographManifest
    """

    id: str
    gridsquare_id: str
    foilhole_id: str
    location_id: str
    high_res_path: Path
    manifest_file: Path
    manifest: MicrographManifest


@dataclass
class FoilHoleData:
    id: str
    gridsquare_id: str
    center_x: float | None = None
    center_y: float | None = None
    quality: float | None = None
    rotation: float | None = None
    size_width: float | None = None
    size_height: float | None = None
    micrographs: EntityStore[MicrographData] = field(default_factory=EntityStore)

    def __post_init__(self):
        self.micrographs = EntityStore()

    def add_micrograph(self, micrograph_id: str, micrograph: MicrographData):
        """Add a micrograph with proper API configuration"""
        if hasattr(self.micrographs, "_api_client") and self.micrographs._api_client:
            # Set foilhole as parent of micrograph
            self.micrographs.set_parent_entity("foilhole", self.id)
        self.micrographs.add(micrograph_id, micrograph)


@dataclass
class GridSquareManifest:
    acquisition_datetime: datetime
    defocus: float | None  # in meters
    magnification: float | None
    pixel_size: float | None  # in meters
    detector_name: str
    applied_defocus: float | None
    data_dir: Path | None = None


@dataclass
class GridSquareStagePosition:
    """Represents a 3D position in stage coordinates.

    Attributes:
        x: X-coordinate in stage position
        y: Y-coordinate in stage position
        z: Z-coordinate in stage position
    """

    x: float | None
    y: float | None
    z: float | None


@dataclass
class FoilHolePosition:
    """Contains position and dimensional data for a foil hole.

    Attributes:
        x_location: Pixel X-coordinate of the foil hole center
        y_location: Pixel Y-coordinate of the foil hole center
        x_stage_position: Stage X-coordinate of the foil hole
        y_stage_position: Stage Y-coordinate of the foil hole
        diameter: Diameter of the foil hole in pixels
    """

    x_location: int
    y_location: int
    x_stage_position: float | None
    y_stage_position: float | None
    diameter: int
    is_near_grid_bar: bool = False


@dataclass
class GridSquarePosition:
    center: tuple[int, int] | None  # pixel centre coordinates on Atlas
    physical: tuple[float, float] | None  # estimated stage position (m scaled to nm)
    size: tuple[int, int] | None  # pixel size on Atlas
    rotation: float | None


@dataclass
class GridSquareMetadata:
    """Contains metadata about a grid square's position and properties.

    Attributes:
        atlas_node_id: Related atlas node identifier
        stage_position: GridSquareStagePosition containing x, y, z stage coordinates
        state: Current state of the grid square (e.g., 'Defined')
        rotation: float
        image_path: Path to the grid square MRC image file
        selected: Whether this grid square is selected for acquisition
        unusable: Whether this grid square has been marked as unusable
        foilhole_positions: Positions of foilholes on gridsquare
    """

    atlas_node_id: int
    stage_position: GridSquareStagePosition | None
    state: str | None
    rotation: float | None
    image_path: Path | None
    selected: bool
    unusable: bool
    foilhole_positions: dict[int, FoilHolePosition] | None

    def __post_init__(self):
        """Ensures the foilhole_positions dictionary is initialized if None is provided."""
        if self.foilhole_positions is None:
            self.foilhole_positions = {}


@dataclass
class GridSquareData:
    id: str
    data_dir: Path | None = None
    metadata: GridSquareMetadata | None = None
    manifest: GridSquareManifest | None = None
    foilholes: EntityStore[FoilHoleData] = field(default_factory=EntityStore)

    def __post_init__(self):
        self.foilholes = EntityStore()

    def add_foilhole(self, foilhole_id: str, foilhole: FoilHoleData):
        """Add a foilhole with proper API configuration"""
        if hasattr(self.foilholes, "_api_client") and self.foilholes._api_client:
            # Set gridsquare as parent of foilhole
            self.foilholes.set_parent_entity("gridsquare", self.id)
        self.foilholes.add(foilhole_id, foilhole)


@dataclass
class AtlasTilePosition:
    position: tuple[int, int] | None
    size: tuple[int, int] | None


@dataclass
class AtlasTileData:
    id: str
    tile_position: AtlasTilePosition
    file_format: str | None
    base_filename: str | None


@dataclass
class AtlasData:
    id: str
    acquisition_date: datetime
    storage_folder: str
    description: str
    name: str
    tiles: list[AtlasTileData]
    gridsquare_positions: dict[int, GridSquarePosition] | None


@dataclass
class EpuSessionData:
    name: str = "Unknown"  # TODO more informative default value?
    id: str = field(default_factory=EntityStore.generate_uuid)
    start_time: datetime | None = None
    atlas_path: str | None = None
    storage_path: str | None = None  # Path of parent directory containing the epu session dir
    clustering_mode: str | None = None
    clustering_radius: str | None = None
    # TODO should we generate UUID in constructor? Syntax `id: str = field(default_factory=EntityStore.generate_uuid)`
    #  is only evaluated at class definition time so would always be the same value -
    #  which is a problem if we had multiple instances od EpuSessionData
    # def __init__(self):
    #     self.id = EntityStore.generate_uuid()


@dataclass
class Grid:
    id: str = field(default_factory=EntityStore.generate_uuid)
    data_dir: Path | None = None
    atlas_dir: Path | None = None

    session_data: EpuSessionData | None = None
    atlas_data: AtlasData | None = None
    gridsquares: EntityStore[GridSquareData] = field(default_factory=EntityStore)
    foilholes: EntityStore[FoilHoleData] = field(default_factory=EntityStore)
    micrographs: EntityStore[MicrographData] = field(default_factory=EntityStore)

    def __init__(self, data_dir: str):
        self.id = EntityStore.generate_uuid()
        self.data_dir = Path(data_dir)
        self.gridsquares = EntityStore()
        self.foilholes = EntityStore()
        self.micrographs = EntityStore()

    def __str__(self):
        return (
            f"==================\n"
            # f"ID: {self.session_data.id}\n"
            # f"Name: {self.session_data.name}\n"
            # f"Start time: {self.session_data.start_time}\n"
            f"Data directory: {self.data_dir}\n"
            f"Atlas directory: {self.atlas_dir}\n"
            f"Entities discovered:\n"
            f"  Atlas gridsquare positions: {len(self.atlas_data.gridsquare_positions)}\n"
            f"  Atlas tiles: {len(self.atlas_data.tiles)}\n"
            f"  Gridsquares: {len(self.gridsquares)}\n"
            f"  Foilholes: {len(self.foilholes)}\n"
            f"  Micrographs: {len(self.micrographs)}\n"
        )


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
