from sqlalchemy import Enum as SQLAlchemyEnum
from sqlalchemy.types import VARCHAR, TypeDecorator

from smartem_common.entity_status import (
    AcquisitionStatus,
    FoilHoleStatus,
    GridSquareStatus,
    GridStatus,
    MicrographStatus,
    ModelLevel,
)


class AcquisitionStatusType(TypeDecorator):
    impl = VARCHAR
    cache_ok = True

    def __init__(self):
        super().__init__()
        self.impl = SQLAlchemyEnum(AcquisitionStatus, name="acquisitionstatus")


class GridStatusType(TypeDecorator):
    impl = VARCHAR
    cache_ok = True

    def __init__(self):
        super().__init__()
        self.impl = SQLAlchemyEnum(GridStatus, name="gridstatus")


class GridSquareStatusType(TypeDecorator):
    impl = VARCHAR
    cache_ok = True

    def __init__(self):
        super().__init__()
        self.impl = SQLAlchemyEnum(GridSquareStatus, name="gridsquarestatus")


class FoilHoleStatusType(TypeDecorator):
    impl = VARCHAR
    cache_ok = True

    def __init__(self):
        super().__init__()
        self.impl = SQLAlchemyEnum(FoilHoleStatus, name="foilholestatus")


class MicrographStatusType(TypeDecorator):
    impl = VARCHAR
    cache_ok = True

    def __init__(self):
        super().__init__()
        self.impl = SQLAlchemyEnum(MicrographStatus, name="micrographstatus")


class ModelLevelType(TypeDecorator):
    impl = VARCHAR
    cache_ok = True

    def __init__(self):
        super().__init__()
        self.impl = SQLAlchemyEnum(ModelLevel, name="modellevel")
