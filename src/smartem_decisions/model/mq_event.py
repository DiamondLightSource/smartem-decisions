from enum import Enum
from datetime import datetime
from typing import Any
from pydantic import (
    BaseModel,
    computed_field,
    field_serializer,
    model_validator,
)


def non_negative_float(v: float):
    return v >= 0


class MessageQueueEventType(str, Enum):
    """Enum listing various system events that are mapped to messages in RabbitMQ"""

    ACQUISITION_CREATED = "acquisition.created"
    ACQUISITION_UPDATED = "acquisition.updated"
    ACQUISITION_DELETED = "acquisition.deleted"

    ATLAS_CREATED = "atlas.created"
    ATLAS_UPDATED = "atlas.updated"
    ATLAS_DELETED = "atlas.deleted"

    ATLAS_TILE_CREATED = "atlas_tile.created"
    ATLAS_TILE_UPDATED = "atlas_tile.updated"
    ATLAS_TILE_DELETED = "atlas_tile.deleted"

    GRID_CREATED = "grid.created"
    GRID_UPDATED = "grid.updated"
    GRID_DELETED = "grid.deleted"

    GRID_SQUARE_CREATED = "grid_square.created"
    GRID_SQUARE_UPDATED = "grid_square.updated"
    GRID_SQUARE_DELETED = "grid_square.deleted"

    FOIL_HOLE_CREATED = "foil_hole.created"
    FOIL_HOLE_UPDATED = "foil_hole.updated"
    FOIL_HOLE_DELETED = "foil_hole.deleted"

    MICROGRAPH_CREATED = "micrograph.created"
    MICROGRAPH_UPDATED = "micrograph.updated"
    MICROGRAPH_DELETED = "micrograph.deleted"

    # ACQUISITION_START = "acquisition started"
    # ACQUISITION_PAUSE = "acquisition paused"
    # ACQUISITION_RESUME = "acquisition resumed"
    # ACQUISITION_END = "acquisition ended"
    # GRID_SCAN_START = "grid scan started"
    # GRID_SCAN_COMPLETE = "grid scan completed"
    GRID_SQUARES_DECISION_START = "grid_squares.decision_started"
    GRID_SQUARES_DECISION_COMPLETE = "grid_squares.decision_completed"
    FOIL_HOLES_DETECTED = "foil_holes.detected"  # TODO is this redundant?
    FOIL_HOLES_DECISION_START = "foil_holes.decision_started"
    FOIL_HOLES_DECISION_COMPLETE = "foil_holes.decision_completed"
    MICROGRAPHS_DETECTED = "micrographs.detected"  # TODO is this redundant?
    MOTION_CORRECTION_START = "motion_correction.started"
    MOTION_CORRECTION_COMPLETE = "motion_{correction.completed"
    CTF_START = "ctf.started"
    CTF_COMPLETE = "ctf.completed"
    PARTICLE_PICKING_START = "particle_picking.started"
    PARTICLE_PICKING_COMPLETE = "particle_picking.completed"
    PARTICLE_SELECTION_START = "particle_selection.started"
    PARTICLE_SELECTION_COMPLETE = "particle_selection.completed"


class GenericEventMessageBody(BaseModel):
    event_type: MessageQueueEventType

    @field_serializer("event_type")
    def serialize_event_type(self, event_type: MessageQueueEventType, _info):
        return str(event_type.value)


# ============ Acquisition Events ============
class AcquisitionEventBase(GenericEventMessageBody):
    """Base model for acquisition events"""

    pass


class AcquisitionCreatedEvent(AcquisitionEventBase):
    """Event emitted when an acquisition is created"""

    id: str
    name: str | None = None
    status: str | None = None
    epu_id: str | None = None
    start_time: str | None = None
    end_time: str | None = None
    metadata: dict[str, Any] | None = None


class AcquisitionUpdatedEvent(AcquisitionEventBase):
    """Event emitted when an acquisition is updated"""

    id: str
    name: str | None = None
    status: str | None = None
    epu_id: str | None = None
    start_time: str | None = None
    end_time: str | None = None
    metadata: dict[str, Any] | None = None


class AcquisitionDeletedEvent(AcquisitionEventBase):
    """Event emitted when an acquisition is deleted"""

    id: str


# ============ Atlas Events ============
class AtlasEventBase(GenericEventMessageBody):
    """Base model for atlas events"""

    pass


class AtlasCreatedEvent(AtlasEventBase):
    """Event emitted when an atlas is created"""

    id: str
    name: str
    grid_id: str
    pixel_size: float | None = None
    metadata: dict[str, Any] | None = None


class AtlasUpdatedEvent(AtlasEventBase):
    """Event emitted when an atlas is updated"""

    id: str
    name: str | None = None
    grid_id: str | None = None
    pixel_size: float | None = None
    metadata: dict[str, Any] | None = None


class AtlasDeletedEvent(AtlasEventBase):
    """Event emitted when an atlas is deleted"""

    id: str


# ============ Atlas Tile Events ============
class AtlasTileEventBase(GenericEventMessageBody):
    """Base model for atlas tile events"""

    pass


class AtlasTileCreatedEvent(AtlasTileEventBase):
    """Event emitted when an atlas tile is created"""

    id: str
    name: str
    atlas_id: str
    position_x: float | None = None
    position_y: float | None = None
    metadata: dict[str, Any] | None = None


class AtlasTileUpdatedEvent(AtlasTileEventBase):
    """Event emitted when an atlas tile is updated"""

    id: str
    name: str | None = None
    atlas_id: str | None = None
    position_x: float | None = None
    position_y: float | None = None
    metadata: dict[str, Any] | None = None


class AtlasTileDeletedEvent(AtlasTileEventBase):
    """Event emitted when an atlas tile is deleted"""

    id: str


# ============ Grid Events ============

# TODO could definitely be refactored to reduce duplication.
#  Since GridCreatedEvent and GridUpdatedEvent share the same fields, with the only difference being
#  that the fields are optional in the updated event.


class GridEventBase(GenericEventMessageBody):
    """Base model for grid events"""

    pass


class GridCreatedEvent(GridEventBase):
    """Event emitted when a grid is created"""

    id: str
    name: str
    acquisition_id: str
    status: str | None = None
    data_dir: str | None = None  # Add this field
    atlas_dir: str | None = None  # Add this field
    scan_start_time: datetime | None = None  # Add if needed
    scan_end_time: datetime | None = None  # Add if needed
    metadata: dict[str, Any] | None = None


class GridUpdatedEvent(GridEventBase):
    """Event emitted when a grid is updated"""

    id: str
    name: str
    acquisition_id: str
    status: str | None = None
    data_dir: str | None = None  # Add this field
    atlas_dir: str | None = None  # Add this field
    scan_start_time: datetime | None = None  # Add if needed
    scan_end_time: datetime | None = None  # Add if needed
    metadata: dict[str, Any] | None = None


class GridDeletedEvent(GridEventBase):
    """Event emitted when a grid is deleted"""

    id: str


# ============ Grid Square Events ============
class GridSquareEventBase(GenericEventMessageBody):
    """Base model for grid square events"""

    pass


class GridSquareCreatedEvent(GridSquareEventBase):
    """Event emitted when a grid square is created"""

    id: str
    name: str
    grid_id: str
    status: str | None = None
    metadata: dict[str, Any] | None = None


class GridSquareUpdatedEvent(GridSquareEventBase):
    """Event emitted when a grid square is updated"""

    id: str
    name: str | None = None
    grid_id: str | None = None
    status: str | None = None
    metadata: dict[str, Any] | None = None


class GridSquareDeletedEvent(GridSquareEventBase):
    """Event emitted when a grid square is deleted"""

    id: str


# ============ Foil Hole Events ============
class FoilHoleEventBase(GenericEventMessageBody):
    """Base model for foil hole events"""

    pass


class FoilHoleCreatedEvent(FoilHoleEventBase):
    """Event emitted when a foil hole is created"""

    id: str
    name: str
    gridsquare_id: str
    position_x: float | None = None
    position_y: float | None = None
    diameter: float | None = None
    status: str | None = None
    metadata: dict[str, Any] | None = None


class FoilHoleUpdatedEvent(FoilHoleEventBase):
    """Event emitted when a foil hole is updated"""

    id: str
    name: str | None = None
    gridsquare_id: str | None = None
    position_x: float | None = None
    position_y: float | None = None
    diameter: float | None = None
    status: str | None = None
    metadata: dict[str, Any] | None = None


class FoilHoleDeletedEvent(FoilHoleEventBase):
    """Event emitted when a foil hole is deleted"""

    id: str


# ============ Micrograph Events ============
class MicrographEventBase(GenericEventMessageBody):
    """Base model for micrograph events"""

    pass


class MicrographCreatedEvent(MicrographEventBase):
    """Event emitted when a micrograph is created"""

    id: str
    name: str
    foilhole_id: str
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

    id: str
    name: str | None = None
    foilhole_id: str | None = None
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

    id: str


# ============ Data Processing and ML Events ============
class MotionCorrectionStartBody(GenericEventMessageBody):
    micrograph_id: str


class MotionCorrectionCompleteBody(GenericEventMessageBody):
    micrograph_id: str
    total_motion: float
    average_motion: float
    ctf_max_resolution_estimate: float

    @model_validator(mode="after")
    def check_model(self):
        if self.total_motion < 0:
            raise ValueError("Total Motion should be a non-negative float")
        if self.average_motion < 0:
            raise ValueError("Average Motion should be a non-negative float")
        if self.ctf_max_resolution_estimate < 0:
            raise ValueError("CTF Max Resolution should be a non-negative float")
        return self


class CtfStartBody(GenericEventMessageBody):
    micrograph_id: str


class CtfCompleteBody(BaseModel):
    micrograph_id: str
    total_motion: float
    average_motion: float
    ctf_max_resolution_estimate: float

    @model_validator(mode="after")
    def check_model(self):
        if self.total_motion < 0:
            raise ValueError("Total Motion should be a non-negative float")
        if self.average_motion < 0:
            raise ValueError("Average Motion should be a non-negative float")
        if self.ctf_max_resolution_estimate < 0:
            raise ValueError("CTF Max Resolution should be a non-negative float")
        return self


class ParticlePickingStartBody(GenericEventMessageBody):
    micrograph_id: str


class ParticlePickingCompleteBody(GenericEventMessageBody):
    micrograph_id: str
    number_of_particles_picked: int
    pick_distribution: dict

    @model_validator(mode="after")
    def check_model(self):
        if self.number_of_particles_picked < 0:
            raise ValueError("Number of Particles Picked should be a non-negative int")
        # TODO validate that number of particles picked equals to the size of pick distribution
        return self


class ParticleSelectionStartBody(GenericEventMessageBody):
    """TODO For particle selection start see:
    https://github.com/DiamondLightSource/cryoem-services/blob/main/src/cryoemservices/services/select_particles.py#L16C1-L21C41
    class ParticleSelectionStart(BaseModel):
        input_file: str = Field(..., min_length=1)
        batch_size: int
        image_size: int
        incomplete_batch_size: int = 10000
        relion_options: RelionServiceOptions
    """

    micrograph_id: str


class ParticleSelectionCompleteBody(GenericEventMessageBody):
    micrograph_id: str
    number_of_particles_selected: int
    number_of_particles_rejected: int
    selection_distribution: dict

    @computed_field
    @property
    def total_number_of_particles(self) -> int:
        return self.number_of_particles_selected + self.number_of_particles_rejected

    @model_validator(mode="after")
    def check_model(self):
        if self.number_of_particles_selected < 0:
            raise ValueError("Number of Particles Selected should be a non-negative int")
        if self.number_of_particles_rejected < 0:
            raise ValueError("Number of Particles Rejected should be a non-negative int")
        return self
