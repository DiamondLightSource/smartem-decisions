from datetime import datetime
from sqlalchemy import text, Column
from sqlmodel import (
    Field,
    Relationship,
    SQLModel,
    create_engine,
)
from sqlmodel import (
    Session as SQLModelSession,
)

from src.smartem_decisions.utils import (
    setup_postgres_connection,
)
from src.smartem_decisions.model.entity_status import (
    AcquisitionStatus,
    AcquisitionStatusType,
    FoilHoleStatus,
    FoilHoleStatusType,
    GridSquareStatus,
    GridSquareStatusType,
    GridStatus,
    GridStatusType,
    MicrographStatus,
    MicrographStatusType,
)


class Acquisition(SQLModel, table=True, table_name="acquisition"):
    __table_args__ = {"extend_existing": True}
    id: int | None = Field(default=None, primary_key=True)
    epu_id: str | None = Field(default=None)
    name: str
    status: AcquisitionStatus = Field(default=AcquisitionStatus.PLANNED, sa_column=Column(AcquisitionStatusType()))
    start_time: datetime | None = Field(default=None)
    end_time: datetime | None = Field(default=None)
    paused_time: datetime | None = Field(default=None)
    grids: list["Grid"] = Relationship(back_populates="acquisition", cascade_delete=True)


class Grid(SQLModel, table=True, table_name="grid"):
    __table_args__ = {"extend_existing": True}
    id: int | None = Field(default=None, primary_key=True)
    acquisition_id: int | None = Field(default=None, foreign_key="acquisition.id")
    status: GridStatus = Field(default=GridStatus.NONE, sa_column=Column(GridStatusType()))
    name: str
    scan_start_time: datetime | None = Field(default=None)
    scan_end_time: datetime | None = Field(default=None)
    acquisition: Acquisition | None = Relationship(back_populates="grids")
    gridsquares: list["GridSquare"] = Relationship(back_populates="grid", cascade_delete=True)
    quality_model_parameters: list["QualityPredictionModelParameter"] = Relationship(
        back_populates="grid", cascade_delete=True
    )
    quality_model_weights: list["QualityPredictionModelWeight"] = Relationship(
        back_populates="grid", cascade_delete=True
    )

class GridSquare(SQLModel, table=True, table_name="gridsquare"):
    __table_args__ = {"extend_existing": True}
    id: int | None = Field(default=None, primary_key=True)
    grid_id: int | None = Field(default=None, foreign_key="grid.id")
    status: GridSquareStatus = Field(default=GridSquareStatus.NONE, sa_column=Column(GridSquareStatusType()))
    # grid_position 5 by 5
    atlastile_img: str = Field(default="")  # path to tile image
    gridsquare_img: str = Field(default="")
    name: str
    grid: Grid | None = Relationship(back_populates="gridsquares")
    foilholes: list["FoilHole"] = Relationship(back_populates="gridsquare", cascade_delete=True)
    prediction: list["QualityPrediction"] = Relationship(back_populates="gridsquare", cascade_delete=True)


class FoilHole(SQLModel, table=True, table_name="foilhole"):  # type: ignore
    __table_args__ = {"extend_existing": True}
    id: int | None = Field(default=None, primary_key=True)
    gridsquare_id: int | None = Field(default=None, foreign_key="gridsquare.id")
    status: FoilHoleStatus = Field(default=FoilHoleStatus.NONE, sa_column=Column(FoilHoleStatusType()))
    name: str
    gridsquare: GridSquare | None = Relationship(back_populates="foilholes")
    micrographs: list["Micrograph"] = Relationship(back_populates="foilhole", cascade_delete=True)
    prediction: list["QualityPrediction"] = Relationship(back_populates="foilhole", cascade_delete=True)


class Micrograph(SQLModel, table=True, table_name="micrograph"):  # type: ignore
    __table_args__ = {"extend_existing": True}
    id: int | None = Field(default=None, primary_key=True)
    foilhole_id: int | None = Field(default=None, foreign_key="foilhole.id")
    status: MicrographStatus = Field(default=MicrographStatus.NONE, sa_column=Column(MicrographStatusType()))
    total_motion: float | None = Field(default=None)  # TODO non-negative or null
    average_motion: float | None = Field(default=None)  # TODO non-negative or null
    ctf_max_resolution_estimate: float | None = Field(default=None)  # TODO non-negative or null
    number_of_particles_selected: int | None = Field(default=None)
    number_of_particles_rejected: int | None = Field(default=None)
    selection_distribution: str | None = Field(default=None)  # TODO dict type (create a user-defined?)
    number_of_particles_picked: int | None = Field(default=None)  # TODO non-negative or null
    pick_distribution: str | None = Field(default=None)  # TODO dict type (create a user-defined?)
    foilhole: FoilHole | None = Relationship(back_populates="micrographs")
    quality_model_weights: list["QualityPredictionModelWeight"] = Relationship(
        back_populates="micrograph", cascade_delete=True
    )


class QualityPredictionModel(SQLModel, table=True):  # type: ignore
    __table_args__ = {"extend_existing": True}
    name: str = Field(primary_key=True)
    description: str = ""
    parameters: list["QualityPredictionModelParameter"] = Relationship(back_populates="model", cascade_delete=True)
    weights: list["QualityPredictionModelWeight"] = Relationship(back_populates="model", cascade_delete=True)
    predictions: list["QualityPrediction"] = Relationship(back_populates="model", cascade_delete=True)


class QualityPredictionModelParameter(SQLModel, table=True):  # type: ignore
    __table_args__ = {"extend_existing": True}
    id: int | None = Field(default=None, primary_key=True)
    id: int | None = Field(default=None, primary_key=True)
    grid_id: int = Field(foreign_key="grid.id")
    timestamp: datetime = Field(default_factory=datetime.now)
    prediction_model_name: str = Field(foreign_key="qualitypredictionmodel.name")
    key: str
    value: float
    model: QualityPredictionModel | None = Relationship(back_populates="parameters")
    grid: Grid | None = Relationship(back_populates="quality_model_parameters")


class QualityPredictionModelWeight(SQLModel, table=True):  # type: ignore
    __table_args__ = {"extend_existing": True}
    id: int | None = Field(default=None, primary_key=True)
    grid_id: int = Field(foreign_key="grid.id")
    micrograph_id: int | None = Field(default=None, foreign_key="micrograph.id")
    micrograph_quality: bool | None = Field(default=None)
    timestamp: datetime = Field(default_factory=datetime.now)
    origin: str | None = Field(default=None)
    prediction_model_name: str = Field(foreign_key="qualitypredictionmodel.name")
    weight: float
    model: QualityPredictionModel | None = Relationship(back_populates="weights")
    grid: Grid | None = Relationship(back_populates="quality_model_weights")
    micrograph: Micrograph | None = Relationship(back_poopulates="quality_model_weights")


class QualityPrediction(SQLModel, table=True):  # type: ignore
    __table_args__ = {"extend_existing": True}
    id: int | None = Field(default=None, primary_key=True)
    timestamp: datetime = Field(default_factory=datetime.now)
    value: float
    prediction_model_name: str = Field(foreign_key="qualitypredictionmodel.name")
    foilhole_id: int | None = Field(default=None, foreign_key="foilhole.id")
    gridsquare_id: int | None = Field(default=None, foreign_key="gridsquare.id")
    foilhole: FoilHole | None = Relationship(back_populates="prediction")
    gridsquare: GridSquare | None = Relationship(back_populates="prediction")
    model: QualityPredictionModel | None = Relationship(back_populates="predictions")


def _create_db_and_tables(engine):
    with SQLModelSession(engine) as sess:
        teardown_query = text("""
            DO $$
            DECLARE
                drop_statement text;
            BEGIN
                FOR drop_statement IN
                    SELECT 'DROP TABLE IF EXISTS "' || table_name || '" CASCADE;'
                    FROM information_schema.tables
                    WHERE table_schema = 'public'
                LOOP
                    EXECUTE drop_statement;
                END LOOP;
                -- Drop the enum type if it exists
                DROP TYPE IF EXISTS acquisitionstatus CASCADE;
                DROP TYPE IF EXISTS gridstatus CASCADE;
                DROP TYPE IF EXISTS gridsquarestatus CASCADE;
                DROP TYPE IF EXISTS foilholestatus CASCADE;
                DROP TYPE IF EXISTS micrographstatus CASCADE;
            END $$;
        """)
        sess.execute(teardown_query)
        sess.commit()

    SQLModel.metadata.create_all(engine)
    """
    SELECT enum_range(NULL::acquisitionstatus);
    SELECT enum_range(NULL::gridstatus);
    SELECT enum_range(NULL::gridsquarestatus);
    SELECT enum_range(NULL::foilholestatus);
    SELECT enum_range(NULL::micrographstatus);
    """


def main():
    db_engine = setup_postgres_connection()
    _create_db_and_tables(db_engine)


if __name__ == "__main__":
    main()
