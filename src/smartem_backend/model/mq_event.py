from datetime import datetime
from enum import Enum

from pydantic import BaseModel, computed_field, field_serializer, model_validator


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
    GRID_REGISTERED = "grid.registered"

    GRIDSQUARE_CREATED = "gridsquare.created"
    GRIDSQUARE_UPDATED = "gridsquare.updated"
    GRIDSQUARE_DELETED = "gridsquare.deleted"

    GRIDSQUARE_LOWMAG_CREATED = "gridsquare_lowmag.created"
    GRIDSQUARE_LOWMAG_UPDATED = "gridsquare_lowmag.updated"
    GRIDSQUARE_LOWMAG_DELETED = "gridsquare_lowmag.deleted"

    FOILHOLE_CREATED = "foilhole.created"
    FOILHOLE_UPDATED = "foilhole.updated"
    FOILHOLE_DELETED = "foilhole.deleted"

    MICROGRAPH_CREATED = "micrograph.created"
    MICROGRAPH_UPDATED = "micrograph.updated"
    MICROGRAPH_DELETED = "micrograph.deleted"

    # ACQUISITION_SESSION_START = "acquisition.session_started"
    # ACQUISITION_SESSION_PAUSE = "acquisition.session_paused"
    # ACQUISITION_SESSION_RESUME = "acquisition.session_resumed"
    # ACQUISITION_SESSION_END = "acquisition.session_ended"
    # GRID_SCAN_SESSION_START = "grid.scan_started"
    # GRID_SCAN_SESSION_COMPLETE = "grid.scan_completed"
    # GRIDSQUARES_DECISION_START = "gridsquares.decision_started"
    GRIDSQUARES_DECISION_COMPLETE = "gridsquares.decision_completed"
    FOILHOLES_DETECTED = "foilholes.detected"  # TODO is this redundant?
    # FOILHOLES_DECISION_START = "foilholes.decision_started"
    FOILHOLES_DECISION_COMPLETE = "foilholes.decision_completed"
    MICROGRAPHS_DETECTED = "micrographs.detected"  # TODO is this redundant?
    # MOTION_CORRECTION_START = "motion_correction.started"
    MOTION_CORRECTION_COMPLETE = "motion_correction.completed"
    # CTF_START = "ctf.started"
    CTF_COMPLETE = "ctf.completed"
    # PARTICLE_PICKING_START = "particle_picking.started"
    PARTICLE_PICKING_COMPLETE = "particle_picking.completed"
    # PARTICLE_SELECTION_START = "particle_selection.started"
    PARTICLE_SELECTION_COMPLETE = "particle_selection.completed"

    GRIDSQUARE_MODEL_PREDICTION = "gridsquare.model_prediction"
    FOILHOLE_MODEL_PREDICTION = "foilhole.model_prediction"
    MODEL_PARAMETER_UPDATE = "gridsquare.model_parameter_update"


class GenericEventMessageBody(BaseModel):
    event_type: MessageQueueEventType

    @field_serializer("event_type")
    def serialize_event_type(self, event_type: MessageQueueEventType, _info):
        return str(event_type.value)

    @field_serializer("*", when_used="json")
    def serialize_datetime_fields(self, v, _info):
        if isinstance(v, datetime):
            return v.isoformat()
        return v


# ============ Acquisition Events ============
class AcquisitionEventBase(GenericEventMessageBody):
    """Base model for acquisition events"""

    pass


class AcquisitionCreatedEvent(AcquisitionEventBase):
    """Event emitted when an acquisition is created"""

    uuid: str
    id: str | None = None


class AcquisitionUpdatedEvent(AcquisitionEventBase):
    """Event emitted when an acquisition is updated"""

    uuid: str
    id: str | None = None


class AcquisitionDeletedEvent(AcquisitionEventBase):
    """Event emitted when an acquisition is deleted"""

    uuid: str


# ============ Atlas Events ============
class AtlasEventBase(GenericEventMessageBody):
    """Base model for atlas events"""

    pass


class AtlasCreatedEvent(AtlasEventBase):
    """Event emitted when an atlas is created"""

    uuid: str
    id: str | None = None
    grid_uuid: str | None = None


class AtlasUpdatedEvent(AtlasEventBase):
    """Event emitted when an atlas is updated"""

    uuid: str
    id: str | None = None
    grid_uuid: str | None = None


class AtlasDeletedEvent(AtlasEventBase):
    """Event emitted when an atlas is deleted"""

    uuid: str


# ============ Atlas Tile Events ============
class AtlasTileEventBase(GenericEventMessageBody):
    """Base model for atlas tile events"""

    pass


class AtlasTileCreatedEvent(AtlasTileEventBase):
    """Event emitted when an atlas tile is created"""

    uuid: str
    id: str | None = None
    atlas_uuid: str | None = None


class AtlasTileUpdatedEvent(AtlasTileEventBase):
    """Event emitted when an atlas tile is updated"""

    uuid: str
    id: str | None = None
    atlas_uuid: str | None = None


class AtlasTileDeletedEvent(AtlasTileEventBase):
    """Event emitted when an atlas tile is deleted"""

    uuid: str


# ============ Grid Events ============

# TODO could definitely be refactored to reduce duplication.
#  Since GridCreatedEvent and GridUpdatedEvent share the same fields, with the only difference being
#  that the fields are optional in the updated event.


class GridEventBase(GenericEventMessageBody):
    """Base model for grid events"""

    pass


class GridCreatedEvent(GridEventBase):
    """Event emitted when a grid is created"""

    uuid: str
    acquisition_uuid: str | None = None


class GridUpdatedEvent(GridEventBase):
    """Event emitted when a grid is updated"""

    uuid: str
    acquisition_uuid: str | None = None


class GridDeletedEvent(GridEventBase):
    """Event emitted when a grid is deleted"""

    uuid: str


class GridRegisteredEvent(GridEventBase):
    """Event emitted when all squares at atlas mag have been registered for a grid"""

    grid_uuid: str


# ============ Grid Square Events ============
class GridSquareEventBase(GenericEventMessageBody):
    """Base model for grid square events"""

    pass


class GridSquareCreatedEvent(GridSquareEventBase):
    """Event emitted when a grid square is created"""

    uuid: str
    grid_uuid: str | None = None
    gridsquare_id: str | None = None


class GridSquareUpdatedEvent(GridSquareEventBase):
    """Event emitted when a grid square is updated"""

    uuid: str
    grid_uuid: str | None = None
    gridsquare_id: str | None = None


class GridSquareDeletedEvent(GridSquareEventBase):
    """Event emitted when a grid square is deleted"""

    uuid: str


# ============ Foil Hole Events ============
class FoilHoleEventBase(GenericEventMessageBody):
    """Base model for foil hole events"""

    pass


class FoilHoleCreatedEvent(FoilHoleEventBase):
    """Event emitted when a foil hole is created"""

    uuid: str
    foilhole_id: str | None = None
    gridsquare_uuid: str | None = None
    gridsquare_id: str | None = None


class FoilHoleUpdatedEvent(FoilHoleEventBase):
    """Event emitted when a foil hole is updated"""

    uuid: str
    foilhole_id: str | None = None
    gridsquare_uuid: str | None = None
    gridsquare_id: str | None = None


class FoilHoleDeletedEvent(FoilHoleEventBase):
    """Event emitted when a foil hole is deleted"""

    uuid: str


# ============ Micrograph Events ============
class MicrographEventBase(GenericEventMessageBody):
    """Base model for micrograph events"""

    pass


class MicrographCreatedEvent(MicrographEventBase):
    """Event emitted when a micrograph is created"""

    uuid: str
    foilhole_uuid: str | None = None
    foilhole_id: str | None = None
    micrograph_id: str | None = None


class MicrographUpdatedEvent(MicrographEventBase):
    """Event emitted when a micrograph is updated"""

    uuid: str
    foilhole_uuid: str | None = None
    foilhole_id: str | None = None
    micrograph_id: str | None = None


class MicrographDeletedEvent(MicrographEventBase):
    """Event emitted when a micrograph is deleted"""

    uuid: str


# ============ Data Processing and ML Events ============
class MotionCorrectionStartBody(GenericEventMessageBody):
    micrograph_uuid: str


class MotionCorrectionCompleteBody(GenericEventMessageBody):
    micrograph_uuid: str
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
    micrograph_uuid: str


class CtfCompleteBody(BaseModel):
    micrograph_uuid: str
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
    micrograph_uuid: str


class ParticlePickingCompleteBody(GenericEventMessageBody):
    micrograph_uuid: str
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

    micrograph_uuid: str


class ParticleSelectionCompleteBody(GenericEventMessageBody):
    micrograph_uuid: str
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


class GridSquareModelPredictionEvent(GenericEventMessageBody):
    gridsquare_uuid: str
    prediction_model_name: str
    prediction_value: float


class FoilHoleModelPredictionEvent(GenericEventMessageBody):
    foilhole_uuid: str
    prediction_model_name: str
    prediction_value: float


class ModelParameterUpdateEvent(GenericEventMessageBody):
    grid_uuid: str
    prediction_model_name: str
    ket: str
    value: float
