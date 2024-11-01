from pydantic import BaseModel, PositiveInt

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
    foil_hole_id: PositiveInt
    grid_square_id: PositiveInt
    processing_results: ProcessingResults


class SessionState(BaseModel):
    session_id: PositiveInt
    # grids: [] # max 12 -> squares -> holes -> micrographs
    # squares and holes will have a ranking

# people are sometimes switching out grids between cassettes so we need some way to
# declare that "these grids are actually parts of a single cassette/sample".
