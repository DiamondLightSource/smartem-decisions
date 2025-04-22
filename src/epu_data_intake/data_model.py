import logging
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass
class EntityStore(Generic[T]):
    _items: dict[str, T] = field(default_factory=dict)
    _api_client = None
    _entity_type: str = None
    _in_memory_only: bool = True
    _parent_entity: tuple[str, str] = None  # (entity_type, entity_id) tuple

    def set_api_client(self, api_client, entity_type: str, in_memory_only: bool = True):
        self._api_client = api_client
        self._entity_type = entity_type
        self._in_memory_only = in_memory_only

    def set_parent_entity(self, parent_type: str, parent_id: str):
        self._parent_entity = (parent_type, parent_id)

    def add(self, id: str, item: T) -> None:
        is_update = id in self._items
        self._items[id] = item

        if not self._in_memory_only and self._api_client:
            try:
                if is_update:
                    self._api_client.update(self._entity_type, id, item, self._parent_entity)
                else:
                    self._api_client.create(self._entity_type, id, item, self._parent_entity)
            except Exception as e:
                logging.error(f"API sync failed for {self._entity_type}/{id}: {str(e)}")

    def get(self, id: str) -> T | None:
        return self._items.get(id)

    def exists(self, id: str) -> bool:
        return id in self._items

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
        if hasattr(self.micrographs, '_api_client') and self.micrographs._api_client:
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
        if hasattr(self.foilholes, '_api_client') and self.foilholes._api_client:
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
    name: str
    id: str
    start_time: datetime
    atlas_path: str | None = None
    storage_path: str | None = None  # Path of parent directory containing the epu session dir
    clustering_mode: str | None = None
    clustering_radius: str | None = None


@dataclass
class Grid:
    data_dir: Path | None
    atlas_dir: Path | None = None

    session_data: EpuSessionData | None = None
    atlas_data: AtlasData | None = None
    gridsquares: EntityStore[GridSquareData] = field(default_factory=EntityStore)
    foilholes: EntityStore[FoilHoleData] = field(default_factory=EntityStore)
    micrographs: EntityStore[MicrographData] = field(default_factory=EntityStore)

    def __init__(self, data_dir: str):
        self.logger = logging.getLogger(__name__)
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

    def __init__(self, root_dir: str, dry_run: bool = False, api_url: str = None):
        self.logger = logging.getLogger(__name__)
        self.root_dir = Path(root_dir)
        self.in_memory_only = dry_run
        self.grids = EntityStore()

        if not dry_run and api_url:
            from src.epu_data_intake.core_api_client_adapter import ApiClientAdapter
            self.api_client = ApiClientAdapter(api_url)
            self.grids.set_api_client(self.api_client, "grid", dry_run)

    def add_grid(self, grid_id: str, grid: Grid):
        """Add a grid with proper API configuration"""

        # Configure the grid's EntityStores for the hierarchy:
        # session -> grid -> gridsquare -> foilhole -> micrograph
        if self.api_client and not self.in_memory_only:
            # Grid is already set up with parent as acquisition/session

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

        self.logger.debug(f"No grid found for path: {path}")
        return None

    def __str__(self):
        result = f"\nEPU Acquisition Summary:\n  Root dir: {self.root_dir}\n  Grids: {len(self.grids)}\n"

        # Add each grid's string representation. TODO debug this doesn't seem to work
        for grid_id, grid in self.grids.items():
            result += f"Grid ID: {grid_id}\n{grid}\n"

        return result
