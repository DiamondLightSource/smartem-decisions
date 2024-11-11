from enum import Enum
from pydantic import BaseModel

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

class MessageQueueEventBody(BaseModel):
    """These are likely to vary wildly, so each event type will have a distinct
    model, but they should all inherit from this one any shared parts of the schema.
    """
    pass
