from collections.abc import Iterator
import logging
from typing import Generic, TypeVar, NotRequired, TypedDict
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field

T = TypeVar('T')


@dataclass
class EntityStore(Generic[T]):
    _items: dict[str, T] = field(default_factory=dict)

    def add(self, id: str, item: T) -> None:
        self._items[id] = item

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
    defocus: float
    detector_name: str
    energy_filter: bool
    phase_plate: bool
    image_size_x: int
    image_size_y: int
    binning_x: int
    binning_y: int

    def __post_init__(self):
        """Validate that size and binning values are positive."""
        for field in ['image_size_x', 'image_size_y', 'binning_x', 'binning_y']:
            value = getattr(self, field)
            if value <= 0:
                raise ValueError(f"{field} must be positive, got {value}")


# TODO:
#   - Record Path to high-res micrograph image
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


@dataclass
class GridSquareManifest:
    acquisition_datetime: datetime
    defocus: float  # in meters
    magnification: float
    pixel_size: float  # in meters
    detector_name: str
    applied_defocus: float
    data_dir: Path | None = None


class Position(TypedDict):
    x: float
    y: float
    z: float


@dataclass
class GridSquareMetadata:
    """Contains metadata about a grid square's position and properties.

    Attributes:
        atlas_node_id: Related atlas node identifier
        position: Dictionary containing x, y, z stage coordinates
        state: Current state of the grid square (e.g., 'Defined')
        rotation: float
        image_path: Path to the grid square MRC image file
        selected: Whether this grid square is selected for acquisition
        unusable: Whether this grid square has been marked as unusable
    """
    atlas_node_id: int
    position: Position
    state: str | None
    rotation: float
    image_path: Path | None
    selected: bool
    unusable: bool


@dataclass
class GridSquareData:
    id: str
    data_dir: Path | None = None
    metadata: GridSquareMetadata | None = None
    manifest: GridSquareManifest | None = None


@dataclass
class AtlasTileData:
    id: str
    position: tuple  # (x, y)
    size: tuple     # (width, height)
    file_format: str
    base_filename: str


@dataclass
class AtlasData:
    id: str
    acquisition_date: datetime
    storage_folder: str
    description: str
    name: str
    tiles: list[AtlasTileData]


@dataclass
class EpuSessionData:
    name: str
    id: str
    start_time: datetime
    atlas_id: str | None = None
    storage_path: str | None = None # Path of parent directory containing the epu session dir
    clustering_mode: str | None = None
    clustering_radius: str | None = None


class EpuSession:
    """Purpose of this class is to hold state of EPU session detection as incremental data parsing is performed.
    On object of this class will be shared among all fs event handlers and parsers. TBD: merge with EpuParser class?
    """

    project_dir: Path
    atlas_dir: Path

    session_data: EpuSessionData | None = None
    gridsquares: EntityStore[GridSquareData] = field(default_factory=EntityStore)
    foilholes: EntityStore[FoilHoleData] = field(default_factory=EntityStore)
    micrographs: EntityStore[MicrographData] = field(default_factory=EntityStore)

    def __init__(self, project_dir, atlas_dir):
        self.logger = logging.getLogger(__name__)
        self.project_dir = Path(project_dir)
        self.atlas_dir = Path(atlas_dir)
        self.gridsquares = EntityStore()
        self.foilholes = EntityStore()
        self.micrographs = EntityStore()


    def __str__(self):
        return (
            f"\nEPU Acquisition Summary:\n"
            f"==================\n"
            # f"ID: {self.session_data.id}\n"
            # f"Name: {self.session_data.name}\n"
            # f"Start time: {self.session_data.start_time}\n"
            f"Project directory: {self.project_dir}\n"
            f"Atlas directory: {self.atlas_dir}\n"
            f"Entities discovered:\n"
            f"  Gridsquares: {len(self.gridsquares)}\n"
            f"  Foilholes: {len(self.foilholes)}\n"
            f"  Micrographs: {len(self.micrographs)}\n"
        )
