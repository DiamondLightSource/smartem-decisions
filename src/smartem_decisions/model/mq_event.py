from enum import Enum

from pydantic import (
    BaseModel,
    computed_field,
    field_serializer,
    model_validator,
)


class MessageQueueEventType(str, Enum):
    """Enum listing various system events that are mapped to messages in RabbitMQ"""

    ACQUISITION_START = "acquisition started"
    ACQUISITION_PAUSE = "acquisition paused"
    ACQUISITION_RESUME = "acquisition resumed"
    ACQUISITION_END = "acquisition ended"
    GRID_SCAN_START = "grid scan started"
    GRID_SCAN_COMPLETE = "grid scan completed"
    GRID_SQUARES_DECISION_START = "grid squares decision started"
    GRID_SQUARES_DECISION_COMPLETE = "grid squares decision completed"
    FOIL_HOLES_DETECTED = "foil holes detected"
    FOIL_HOLES_DECISION_START = "foil holes decision started"
    FOIL_HOLES_DECISION_COMPLETE = "foil holes decision completed"
    MICROGRAPHS_DETECTED = "micrographs detected"
    MOTION_CORRECTION_START = "motion correction started"
    MOTION_CORRECTION_COMPLETE = "motion correction completed"
    CTF_START = "ctf started"
    CTF_COMPLETE = "ctf completed"
    PARTICLE_PICKING_START = "particle picking started"
    PARTICLE_PICKING_COMPLETE = "particle picking completed"
    PARTICLE_SELECTION_START = "particle selection started"
    PARTICLE_SELECTION_COMPLETE = "particle selection completed"


def non_negative_float(v: float):
    return v >= 0


class GenericEventMessageBody(BaseModel):
    event_type: MessageQueueEventType

    @field_serializer("event_type")
    def serialize_event_type(self, event_type: MessageQueueEventType, _info):
        return str(event_type.value)


class AcquisitionStartBody(GenericEventMessageBody):
    name: str
    epu_id: str | None = None


class GridScanStartBody(GenericEventMessageBody):
    grid_id: int


class GridScanCompleteBody(GenericEventMessageBody):
    grid_id: int


class GridSquaresDecisionStartBody(GenericEventMessageBody):
    grid_id: int


class GridSquaresDecisionCompleteBody(GenericEventMessageBody):
    grid_id: int


class FoilHolesDetectedBody(GenericEventMessageBody):
    grid_id: int


class FoilHolesDecisionStartBody(GenericEventMessageBody):
    gridsquare_id: int


class FoilHolesDecisionCompleteBody(GenericEventMessageBody):
    gridsquare_id: int


class MicrographsDetectedBody(GenericEventMessageBody):
    foilhole_id: int
    # micrographs: dict TODO


class MotionCorrectionStartBody(GenericEventMessageBody):
    micrograph_id: int


class MotionCorrectionCompleteBody(GenericEventMessageBody):
    micrograph_id: int
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
    micrograph_id: int


class CtfCompleteBody(BaseModel):
    micrograph_id: int
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
    micrograph_id: int


class ParticlePickingCompleteBody(BaseModel):
    micrograph_id: int
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

    micrograph_id: int


class ParticleSelectionCompleteBody(BaseModel):
    micrograph_id: int
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


class AcquisitionEndBody(GenericEventMessageBody):
    acquisition_id: int
