from datetime import datetime
from sqlalchemy import text, Column
from sqlmodel import (
    Field,
    Session as SQLModelSession,
    SQLModel,
    Relationship,
)

from src.smartem_decisions.utils import (
    logger,
    setup_postgres_connection,
)
from src.smartem_decisions.model.entity_status import (
    AcquisitionStatus,
    AcquisitionStatusType,
    GridStatus,
    GridStatusType,
    GridSquareStatus,
    GridSquareStatusType,
    FoilHoleStatus,
    FoilHoleStatusType,
    MicrographStatus,
    MicrographStatusType,
)


class Acquisition(SQLModel, table=True, table_name="acquisition"):
    __table_args__ = {"extend_existing": True}
    id: int = Field(default=None, primary_key=True)
    epu_id: str = Field(default=None)
    name: str
    status: AcquisitionStatus = Field(default=AcquisitionStatus.PLANNED, sa_column=Column(AcquisitionStatusType()))
    start_time: datetime = Field(default=None)
    end_time: datetime = Field(default=None)
    paused_time: datetime = Field(default=None)
    grids: list["Grid"] = Relationship(back_populates="acquisition", cascade_delete=True)


class Grid(SQLModel, table=True, table_name="grid"):
    __table_args__ = {"extend_existing": True}
    id: int = Field(default=None, primary_key=True)
    acquisition_id: int = Field(default=None, foreign_key="acquisition.id")
    status: GridStatus = Field(default=GridStatus.NONE, sa_column=Column(GridStatusType()))
    name: str
    scan_start_time: datetime = Field(default=None)
    scan_end_time: datetime = Field(default=None)
    acquisition: Acquisition = Relationship(back_populates="grids")
    gridsquares: list["GridSquare"] = Relationship(back_populates="grid", cascade_delete=True)


class GridSquare(SQLModel, table=True, table_name="gridsquare"):
    __table_args__ = {"extend_existing": True}
    id: int = Field(default=None, primary_key=True)
    grid_id: int = Field(default=None, foreign_key="grid.id")
    status: GridSquareStatus = Field(default=GridSquareStatus.NONE, sa_column=Column(GridSquareStatusType()))
    # grid_position 5 by 5
    atlastile_img: str = Field(default="")  # path to tile image
    name: str
    grid: Grid = Relationship(back_populates="gridsquares")
    foilholes: list["FoilHole"] = Relationship(back_populates="gridsquare", cascade_delete=True)


class FoilHole(SQLModel, table=True, table_name="foilhole"):
    __table_args__ = {"extend_existing": True}
    id: int = Field(default=None, primary_key=True)
    gridsquare_id: int = Field(default=None, foreign_key="gridsquare.id")
    status: FoilHoleStatus = Field(default=FoilHoleStatus.NONE, sa_column=Column(FoilHoleStatusType()))
    name: str
    gridsquare: GridSquare = Relationship(back_populates="foilholes")
    micrographs: list["Micrograph"] = Relationship(back_populates="foilhole", cascade_delete=True)


class Micrograph(SQLModel, table=True, table_name="micrograph"):
    __table_args__ = {"extend_existing": True}
    id: int = Field(default=None, primary_key=True)
    foilhole_id: int = Field(default=None, foreign_key="foilhole.id")
    status: MicrographStatus = Field(default=MicrographStatus.NONE, sa_column=Column(MicrographStatusType()))
    total_motion: float = Field(default=None)  # TODO non-negative or null
    average_motion: float = Field(default=None)  # TODO non-negative or null
    ctf_max_resolution_estimate: float = Field(default=None)  # TODO non-negative or null
    number_of_particles_selected: int = Field(default=None)
    number_of_particles_rejected: int = Field(default=None)
    selection_distribution: str = Field(default=None)  # TODO dict type (create a user-defined?)
    number_of_particles_picked: int = Field(default=None)  # TODO non-negative or null
    pick_distribution: str = Field(default=None)  # TODO dict type (create a user-defined?)
    foilhole: FoilHole = Relationship(back_populates="micrographs")


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
