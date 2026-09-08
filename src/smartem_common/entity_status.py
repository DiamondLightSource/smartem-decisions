from enum import StrEnum


class AcquisitionStatus(StrEnum):
    PLANNED = "planned"
    STARTED = "started"
    COMPLETED = "completed"
    PAUSED = "paused"
    ABANDONED = "abandoned"


class GridStatus(StrEnum):
    NONE = "none"
    SCAN_STARTED = "scan started"
    SCAN_COMPLETED = "scan completed"
    GRID_SQUARES_DECISION_STARTED = "grid squares decision started"
    GRID_SQUARES_DECISION_COMPLETED = "grid squares decision completed"


class GridSquareStatus(StrEnum):
    NONE = "none"
    REGISTERED = "all foil holes registered"
    FOIL_HOLES_DECISION_STARTED = "foil holes decision started"
    FOIL_HOLES_DECISION_COMPLETED = "foil holes decision completed"


class FoilHoleStatus(StrEnum):
    NONE = "none"
    MICROGRAPHS_DETECTED = "micrographs detected"


class MicrographStatus(StrEnum):
    NONE = "none"
    MOTION_CORRECTION_STARTED = "motion correction started"
    MOTION_CORRECTION_COMPLETED = "motion correction completed"
    CTF_STARTED = "ctf started"
    CTF_COMPLETED = "ctf completed"
    PARTICLE_PICKING_STARTED = "particle picking started"
    PARTICLE_PICKING_COMPLETED = "particle picking completed"
    PARTICLE_SELECTION_STARTED = "particle selection started"
    PARTICLE_SELECTION_COMPLETED = "particle selection completed"


class ModelLevel(StrEnum):
    GRIDSQUARE = "gridsquare"
    FOILHOLE = "foilhole"
    FOILHOLEGROUP = "foilholegroup"
