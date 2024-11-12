from enum import Enum
from pydantic import (
    BaseModel,
    Field,
    model_validator,
)
from uuid import UUID, uuid4

class MessageQueueEventType(str, Enum):
    """Enum listing various system events that are mapped to messages in RabbitMQ
    """
    session_start = 'session start'
    session_pause = 'session pause'
    session_resume = 'session resume'
    session_end = 'session end'
    grid_scan_start = 'grid scan start'
    grid_scan_complete = 'grid scan complete'
    grid_squares_decision_start = 'grid squares decision start'
    grid_squares_decision_complete = 'grid squares decision complete'
    foil_holes_detected = 'foil holes detected'
    foil_holes_decision_start = 'foil holes decision start'
    foil_holes_decision_complete = 'foil holes decision complete'
    motion_correct_start = 'motion correct start'
    motion_correct_complete = 'motion correct complete'
    ctf_start = 'ctf start'
    ctf_complete = 'ctf complete'
    particle_picking_start = 'particle picking start'
    particle_picking_complete = 'particle picking complete'
    particle_selection_start = 'particle selection start'
    particle_selection_complete = 'particle selection complete'

def non_negative_float(v: float):
    return v >= 0

class MotionCorrectionCompleteBody(BaseModel):
    micrograph_id: UUID = Field(..., default_factory=uuid4)
    total_motion: float
    average_motion: float
    ctf_max_resolution_estimate: float

    @model_validator(mode='after')
    def check_model(self):
        if self.total_motion < 0:
            raise ValueError('Total Motion should be a non-negative float')
        if self.average_motion < 0:
            raise ValueError('Average Motion should be a non-negative float')
        if self.ctf_max_resolution_estimate < 0:
            raise ValueError('CTF Max Resolution should be a non-negative float')
        return self


class CtfCompleteBody(BaseModel):
    micrograph_id: UUID = Field(..., default_factory=uuid4)
    total_motion: float
    average_motion: float
    ctf_max_resolution_estimate: float

    @model_validator(mode='after')
    def check_model(self):
        if self.total_motion < 0:
            raise ValueError('Total Motion should be a non-negative float')
        if self.average_motion < 0:
            raise ValueError('Average Motion should be a non-negative float')
        if self.ctf_max_resolution_estimate < 0:
            raise ValueError('CTF Max Resolution should be a non-negative float')
        return self


class ParticlePickingCompleteBody(BaseModel):
    micrograph_id: UUID = Field(..., default_factory=uuid4)
    number_of_particles_picked: int
    pick_distribution: dict

    @model_validator(mode='after')
    def check_model(self):
        if self.number_of_particles_picked < 0:
            raise ValueError('Number of Particles Picked should be a non-negative int')
        return self


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
    selection_distribution: dict

    @model_validator(mode='after')
    def check_model(self):
        if self.number_of_particles_selected < 0:
            raise ValueError('Number of Particles Selected should be a non-negative int')
        return self



valid_external_data_1 = {
    'micrograph_id': uuid4(),
    'total_motion': 0.123,
    'average_motion': 0.006,
    'ctf_max_resolution_estimate': 0.123123,
}
invalid_external_data_1 = {
    'micrograf_id': 'xx',
    'total_lotion': None,
    'averag_emotion': -0.006,
    'ctf_max_revolution_estimate': '0.123123',
}

try:
    test_obj_1_valid = MotionCorrectionCompleteBody(**valid_external_data_1)
    assert test_obj_1_valid.model_dump() == valid_external_data_1

    # test_obj_1_invalid = MotionCorrectionCompleteBody(**invalid_external_data_1)
except RuntimeError:
    print(f"Failed ot instantiate MotionCorrectionCTFCompleteBody from: {valid_external_data_1}")
