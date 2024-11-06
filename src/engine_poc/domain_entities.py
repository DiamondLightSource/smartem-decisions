from enum import Enum
from pydantic import BaseModel, PositiveInt, PastDatetime, ValidationError, UUID4

"""
Enum listing various system events that are mapped to messages in RabbitMQ
"""
class MessageQueueEventType(str, Enum):
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
    motion_correct_and_ctf_start = 'motion correct and ctf start'
    motion_correct_and_ctf_complete = 'motion correct and ctf complete'
    particle_picking_start = 'particle picking start'
    particle_picking_complete = 'particle picking complete'
    particle_selection_start = 'particle selection start'
    particle_selection_complete = 'particle selection complete'

class MessageQueueEventHeaders(BaseModel):
    event_type: MessageQueueEventType

# TODO these will likely vary wildly, possibly best to just have a distinct model for each one?
# class MessageQueueEventBody(BaseModel):
#     pass


# Where ProcessingResults will be specific to the processing step.
# It may be the value of the CTF max resolution, or the number of particles picked,
#   or the number of particles that passed the filtering stage.
class ProcessingResults(BaseModel):
    results: PositiveInt

# cassette ha 12 slots, we don't know if grids in different slots are related.
# can I use decisions from the first grid on the second grid? are they same protein/thickness of ice?

class ProcessingPipelineMessage(BaseModel):
    """The messages received from the processing pipeline"""
    micrograph_name: str
    foil_hole_id: UUID4 | PositiveInt | str
    grid_square_id: PositiveInt
    processing_results: ProcessingResults

class MicroGraph(BaseModel):
    micrograph_id: PositiveInt
    path_to_image: str # todo filepath

# TODO may or may not have an image
class FoilHole(BaseModel):
    foil_hole_id: PositiveInt
    score: float # TODO we may also want to record info about which model scored it?
    similarity_matrix: list[list[float]]
    micrographs: list[MicroGraph]

class GridSquare(BaseModel):
    grid_square_id: PositiveInt
    foil_holes: list[FoilHole]
    score: float # TODO we may also want to record info about which model scored it?
    similarity_matrix: list[list[float]]
    path_to_image: str # TODO filepath - get some examples of what these look like

class Grid(BaseModel):
    sample_id: PositiveInt
    alignment_timestamp: PastDatetime
    path_to_image: str # todo filepath (we just want the most recent image)
    atlas_id: str # TODO is actually a filepath e.g. `Z:\nt32457-6\atlas\Supervisor_20240404_093820_Pete_Miriam_HexAuFoil\Sample4\Atlas\Atlas.dm`
    squares: list[GridSquare]


# TODO
#  people are sometimes switching out grids between cassettes so we need some way to
#  declare that "these grids are actually parts of a single cassette/sample".
class SessionState(BaseModel):
    session_id: PositiveInt
    grids: list[Grid] # TODO Samples or Grids - what is better naming?
    # grids: [] # max 12 -> squares -> holes -> micrographs
    # squares and holes will have a ranking
