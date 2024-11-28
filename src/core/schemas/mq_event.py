from enum import Enum
from uuid import UUID, uuid4

from pydantic import (
    BaseModel,
    computed_field,
    # ValidationError,
    Field,
    field_serializer,
    model_validator,
)

# import json
# from typing import no_type_check, Type, Any


class MessageQueueEventType(str, Enum):
    """Enum listing various system events that are mapped to messages in RabbitMQ"""

    session_start = "session start"
    session_pause = "session pause"
    session_resume = "session resume"
    session_end = "session end"
    grid_scan_start = "grid scan start"
    grid_scan_complete = "grid scan complete"
    grid_squares_decision_start = "grid squares decision start"
    grid_squares_decision_complete = "grid squares decision complete"
    foil_holes_detected = "foil holes detected"
    foil_holes_decision_start = "foil holes decision start"
    foil_holes_decision_complete = "foil holes decision complete"
    motion_correction_start = "motion correction start"
    motion_correction_complete = "motion correction complete"
    ctf_start = "ctf start"
    ctf_complete = "ctf complete"
    particle_picking_start = "particle picking start"
    particle_picking_complete = "particle picking complete"
    particle_selection_start = "particle selection start"
    particle_selection_complete = "particle selection complete"


def non_negative_float(v: float):
    return v >= 0


class GenericEventMessageBody(BaseModel):
    event_type: MessageQueueEventType

    @field_serializer("event_type")
    def serialize_event_type(self, event_type: MessageQueueEventType, _info):
        return str(event_type.value)


class MotionCorrectionCompleteBody(GenericEventMessageBody):
    micrograph_id: UUID = Field(..., default_factory=uuid4)
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

    @field_serializer("micrograph_id")
    def serialize_micrograph_id(self, micrograph_id: UUID, _info):
        return str(micrograph_id)


class CtfCompleteBody(BaseModel):
    micrograph_id: UUID = Field(..., default_factory=uuid4)
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

    @field_serializer("micrograph_id")
    def serialize_micrograph_id(self, micrograph_id: UUID, _info):
        return str(micrograph_id)


class ParticlePickingCompleteBody(BaseModel):
    micrograph_id: UUID = Field(..., default_factory=uuid4)
    number_of_particles_picked: int
    pick_distribution: dict

    @model_validator(mode="after")
    def check_model(self):
        if self.number_of_particles_picked < 0:
            raise ValueError("Number of Particles Picked should be a non-negative int")
        # TODO validate that number of particles picked equals to the size of pick distribution
        return self

    @field_serializer("micrograph_id")
    def serialize_micrograph_id(self, micrograph_id: UUID, _info):
        return str(micrograph_id)


"""For particle selection start see:
https://github.com/DiamondLightSource/cryoem-services/blob/main/src/cryoemservices/services/select_particles.py#L16C1-L21C41
class ParticleSelectionStart(BaseModel):
    input_file: str = Field(..., min_length=1)
    batch_size: int
    image_size: int
    incomplete_batch_size: int = 10000
    relion_options: RelionServiceOptions
"""


class ParticleSelectionCompleteBody(BaseModel):
    micrograph_id: UUID = Field(..., default_factory=uuid4)
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

    @field_serializer("micrograph_id")
    def serialize_micrograph_id(self, micrograph_id: UUID, _info):
        return str(micrograph_id)
