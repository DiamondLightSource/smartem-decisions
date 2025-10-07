from sqlalchemy import Enum as SQLAlchemyEnum
from sqlalchemy.types import TypeDecorator

from smartem_common.entity_status import (
    AcquisitionStatus,
    FoilHoleStatus,
    GridSquareStatus,
    GridStatus,
    MicrographStatus,
    ModelLevel,
)


class AcquisitionStatusType(TypeDecorator):
    impl = SQLAlchemyEnum(AcquisitionStatus, name="acquisitionstatus")
    cache_ok = True


class GridStatusType(TypeDecorator):
    impl = SQLAlchemyEnum(GridStatus, name="gridstatus")
    cache_ok = True


class GridSquareStatusType(TypeDecorator):
    impl = SQLAlchemyEnum(GridSquareStatus, name="gridsquarestatus")
    cache_ok = True


class FoilHoleStatusType(TypeDecorator):
    impl = SQLAlchemyEnum(FoilHoleStatus, name="foilholestatus")
    cache_ok = True


class MicrographStatusType(TypeDecorator):
    impl = SQLAlchemyEnum(MicrographStatus, name="micrographstatus")
    cache_ok = True


class ModelLevelType(TypeDecorator):
    impl = SQLAlchemyEnum(ModelLevel, name="modellevel")
    cache_ok = True
