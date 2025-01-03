from enum import Enum
from sqlalchemy import Enum as SQLAlchemyEnum
from sqlalchemy.types import TypeDecorator, VARCHAR


class SessionStatus(str, Enum):
    PLANNED = "planned"
    STARTED = "started"
    COMPLETED = "completed"
    PAUSED = "paused"
    ABANDONED = "abandoned"


class SessionStatusType(TypeDecorator):
    impl = VARCHAR
    cache_ok = True

    def __init__(self):
        super().__init__()
        self.impl = SQLAlchemyEnum(SessionStatus, name="sessionstatus")


class GridStatus(str, Enum):
    NONE = "none"
    SCAN_STARTED = "scan started"
    SCAN_COMPLETED = "scan completed"
    GRID_SQUARES_DECISION_STARTED = "grid squares decision started"
    GRID_SQUARES_DECISION_COMPLETED = "grid squares decision completed"


class GridStatusType(TypeDecorator):
    impl = VARCHAR
    cache_ok = True

    def __init__(self):
        super().__init__()
        self.impl = SQLAlchemyEnum(GridStatus, name="gridstatus")


class GridSquareStatus(str, Enum):
    NONE = "none"
    FOIL_HOLES_DECISION_STARTED = "foil holes decision started"
    FOIL_HOLES_DECISION_COMPLETED = "foil holes decision completed"


class GridSquareStatusType(TypeDecorator):
    impl = VARCHAR
    cache_ok = True

    def __init__(self):
        super().__init__()
        self.impl = SQLAlchemyEnum(GridSquareStatus, name="gridsquarestatus")


class FoilHoleStatus(str, Enum):
    NONE = "none"
    MICROGRAPHS_DETECTED = "micrographs detected"


class FoilHoleStatusType(TypeDecorator):
    impl = VARCHAR
    cache_ok = True

    def __init__(self):
        super().__init__()
        self.impl = SQLAlchemyEnum(FoilHoleStatus, name="foilholestatus")


class MicrographStatus(str, Enum):
    NONE = "none"
    MOTION_CORRECTION_STARTED = "motion correction started"
    MOTION_CORRECTION_COMPLETED = "motion correction completed"
    CTF_STARTED = "ctf started"
    CTF_COMPLETED = "ctf completed"
    PARTICLE_PICKING_STARTED = "particle picking started"
    PARTICLE_PICKING_COMPLETED = "particle picking completed"
    PARTICLE_SELECTION_STARTED = "particle selection started"
    PARTICLE_SELECTION_COMPLETED = "particle selection completed"


class MicrographStatusType(TypeDecorator):
    impl = VARCHAR
    cache_ok = True

    def __init__(self):
        super().__init__()
        self.impl = SQLAlchemyEnum(MicrographStatus, name="micrographstatus")
