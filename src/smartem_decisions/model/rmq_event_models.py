from typing import Any
from pydantic import BaseModel


# ============ Acquisition Events ============
class AcquisitionEventBase(BaseModel):
    """Base model for acquisition events"""
    pass


class AcquisitionCreatedEvent(AcquisitionEventBase):
    """Event emitted when an acquisition is created"""
    id: int
    name: str
    status: str | None = None
    epu_id: str | None = None
    start_time: str | None = None
    end_time: str | None = None
    metadata: dict[str, Any] | None = None


class AcquisitionUpdatedEvent(AcquisitionEventBase):
    """Event emitted when an acquisition is updated"""
    id: int
    name: str | None = None
    status: str | None = None
    epu_id: str | None = None
    start_time: str | None = None
    end_time: str | None = None
    metadata: dict[str, Any] | None = None


class AcquisitionDeletedEvent(AcquisitionEventBase):
    """Event emitted when an acquisition is deleted"""
    id: int


# ============ Atlas Events ============
class AtlasEventBase(BaseModel):
    """Base model for atlas events"""
    pass


class AtlasCreatedEvent(AtlasEventBase):
    """Event emitted when an atlas is created"""
    id: int
    name: str
    grid_id: int
    pixel_size: float | None = None
    metadata: dict[str, Any] | None = None


class AtlasUpdatedEvent(AtlasEventBase):
    """Event emitted when an atlas is updated"""
    id: int
    name: str | None = None
    grid_id: int | None = None
    pixel_size: float | None = None
    metadata: dict[str, Any] | None = None


class AtlasDeletedEvent(AtlasEventBase):
    """Event emitted when an atlas is deleted"""
    id: int


# ============ Atlas Tile Events ============
class AtlasTileEventBase(BaseModel):
    """Base model for atlas tile events"""
    pass


class AtlasTileCreatedEvent(AtlasTileEventBase):
    """Event emitted when an atlas tile is created"""
    id: int
    name: str
    atlas_id: int
    position_x: float | None = None
    position_y: float | None = None
    metadata: dict[str, Any] | None = None


class AtlasTileUpdatedEvent(AtlasTileEventBase):
    """Event emitted when an atlas tile is updated"""
    id: int
    name: str | None = None
    atlas_id: int | None = None
    position_x: float | None = None
    position_y: float | None = None
    metadata: dict[str, Any] | None = None


class AtlasTileDeletedEvent(AtlasTileEventBase):
    """Event emitted when an atlas tile is deleted"""
    id: int


# ============ Grid Events ============
class GridEventBase(BaseModel):
    """Base model for grid events"""
    pass


class GridCreatedEvent(GridEventBase):
    """Event emitted when a grid is created"""
    id: int
    name: str
    acquisition_id: int
    status: str | None = None
    metadata: dict[str, Any] | None = None


class GridUpdatedEvent(GridEventBase):
    """Event emitted when a grid is updated"""
    id: int
    name: str | None = None
    acquisition_id: int | None = None
    status: str | None = None
    metadata: dict[str, Any] | None = None


class GridDeletedEvent(GridEventBase):
    """Event emitted when a grid is deleted"""
    id: int


# ============ Grid Square Events ============
class GridSquareEventBase(BaseModel):
    """Base model for grid square events"""
    pass


class GridSquareCreatedEvent(GridSquareEventBase):
    """Event emitted when a grid square is created"""
    id: int
    name: str
    grid_id: int
    status: str | None = None
    metadata: dict[str, Any] | None = None


class GridSquareUpdatedEvent(GridSquareEventBase):
    """Event emitted when a grid square is updated"""
    id: int
    name: str | None = None
    grid_id: int | None = None
    status: str | None = None
    metadata: dict[str, Any] | None = None


class GridSquareDeletedEvent(GridSquareEventBase):
    """Event emitted when a grid square is deleted"""
    id: int


# ============ Foil Hole Events ============
class FoilHoleEventBase(BaseModel):
    """Base model for foil hole events"""
    pass


class FoilHoleCreatedEvent(FoilHoleEventBase):
    """Event emitted when a foil hole is created"""
    id: int
    name: str
    gridsquare_id: int
    position_x: float | None = None
    position_y: float | None = None
    diameter: float | None = None
    status: str | None = None
    metadata: dict[str, Any] | None = None


class FoilHoleUpdatedEvent(FoilHoleEventBase):
    """Event emitted when a foil hole is updated"""
    id: int
    name: str | None = None
    gridsquare_id: int | None = None
    position_x: float | None = None
    position_y: float | None = None
    diameter: float | None = None
    status: str | None = None
    metadata: dict[str, Any] | None = None


class FoilHoleDeletedEvent(FoilHoleEventBase):
    """Event emitted when a foil hole is deleted"""
    id: int


# ============ Micrograph Events ============
class MicrographEventBase(BaseModel):
    """Base model for micrograph events"""
    pass


class MicrographCreatedEvent(MicrographEventBase):
    """Event emitted when a micrograph is created"""
    id: int
    name: str
    foilhole_id: int
    pixel_size: float | None = None
    defocus: float | None = None
    total_motion: float | None = None
    average_motion: float | None = None
    ctf_max_resolution_estimate: float | None = None
    number_of_particles_picked: int | None = None
    number_of_particles_selected: int | None = None
    number_of_particles_rejected: int | None = None
    status: str | None = None
    metadata: dict[str, Any] | None = None


class MicrographUpdatedEvent(MicrographEventBase):
    """Event emitted when a micrograph is updated"""
    id: int
    name: str | None = None
    foilhole_id: int | None = None
    pixel_size: float | None = None
    defocus: float | None = None
    total_motion: float | None = None
    average_motion: float | None = None
    ctf_max_resolution_estimate: float | None = None
    number_of_particles_picked: int | None = None
    number_of_particles_selected: int | None = None
    number_of_particles_rejected: int | None = None
    status: str | None = None
    metadata: dict[str, Any] | None = None


class MicrographDeletedEvent(MicrographEventBase):
    """Event emitted when a micrograph is deleted"""
    id: int
