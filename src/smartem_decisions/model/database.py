import os
from datetime import datetime
from typing import Optional, List

# import logging
# logging.basicConfig()
# logging.getLogger("sqlalchemy.engine").setLevel(logging.DEBUG)

from dotenv import load_dotenv
from sqlalchemy import text, Column, Enum as SQLAlchemyEnum
from sqlmodel import (
    Field,
    Session as SQLModelSession,
    SQLModel,
    create_engine,
    Relationship,
)

from .entity_status import (
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


class Acquisition(SQLModel, table=True, table_name="acquisition"):  # type: ignore
    __table_args__ = {"extend_existing": True}
    id: Optional[int] = Field(default=None, primary_key=True)
    epu_id: Optional[str] = Field(default=None)
    name: str
    status: AcquisitionStatus = Field(default=AcquisitionStatus.PLANNED, sa_column=Column(AcquisitionStatusType()))
    start_time: Optional[datetime] = Field(default=None)
    end_time: Optional[datetime] = Field(default=None)
    paused_time: Optional[datetime] = Field(default=None)
    grids: List["Grid"] = Relationship(back_populates="acquisition", cascade_delete=True)


class Grid(SQLModel, table=True, table_name="grid"):  # type: ignore
    __table_args__ = {"extend_existing": True}
    id: Optional[int] = Field(default=None, primary_key=True)
    acquisition_id: Optional[int] = Field(default=None, foreign_key="acquisition.id")
    status: GridStatus = Field(default=GridStatus.NONE, sa_column=Column(GridStatusType()))
    name: str
    scan_start_time: Optional[datetime] = Field(default=None)
    scan_end_time: Optional[datetime] = Field(default=None)
    acquisition: Optional[Acquisition] = Relationship(back_populates="grids")
    gridsquares: List["GridSquare"] = Relationship(back_populates="grid", cascade_delete=True)


class GridSquare(SQLModel, table=True, table_name="gridsquare"):  # type: ignore
    __table_args__ = {"extend_existing": True}
    id: Optional[int] = Field(default=None, primary_key=True)
    grid_id: Optional[int] = Field(default=None, foreign_key="grid.id")
    status: GridSquareStatus = Field(default=GridSquareStatus.NONE, sa_column=Column(GridSquareStatusType()))
    # grid_position 5 by 5
    atlastile_img: str = Field(default="")  # path to tile image
    name: str
    grid: Optional[Grid] = Relationship(back_populates="gridsquares")
    foilholes: List["FoilHole"] = Relationship(back_populates="gridsquare", cascade_delete=True)


class FoilHole(SQLModel, table=True, table_name="foilhole"):  # type: ignore
    __table_args__ = {"extend_existing": True}
    id: Optional[int] = Field(default=None, primary_key=True)
    gridsquare_id: Optional[int] = Field(default=None, foreign_key="gridsquare.id")
    status: FoilHoleStatus = Field(default=FoilHoleStatus.NONE, sa_column=Column(FoilHoleStatusType()))
    name: str
    gridsquare: Optional[GridSquare] = Relationship(back_populates="foilholes")
    micrographs: List["Micrograph"] = Relationship(back_populates="foilhole", cascade_delete=True)


class Micrograph(SQLModel, table=True, table_name="micrograph"):  # type: ignore
    __table_args__ = {"extend_existing": True}
    id: Optional[int] = Field(default=None, primary_key=True)
    foilhole_id: Optional[int] = Field(default=None, foreign_key="foilhole.id")
    status: MicrographStatus = Field(default=MicrographStatus.NONE, sa_column=Column(MicrographStatusType()))
    total_motion: Optional[float] = Field(default=None)  # TODO non-negative or null
    average_motion: Optional[float] = Field(default=None)  # TODO non-negative or null
    ctf_max_resolution_estimate: Optional[float] = Field(default=None)  # TODO non-negative or null
    number_of_particles_selected: Optional[int] = Field(default=None)
    number_of_particles_rejected: Optional[int] = Field(default=None)
    selection_distribution: Optional[str] = Field(default=None)  # TODO dict type (create a user-defined?)
    number_of_particles_picked: Optional[int] = Field(default=None)  # TODO non-negative or null
    pick_distribution: Optional[str] = Field(default=None)  # TODO dict type (create a user-defined?)
    foilhole: Optional[FoilHole] = Relationship(back_populates="micrographs")


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
    load_dotenv()

    assert os.getenv("POSTGRES_USER") is not None, "Could not get env var POSTGRES_USER"
    assert os.getenv("POSTGRES_PASSWORD") is not None, "Could not get env var POSTGRES_PASSWORD"
    assert os.getenv("POSTGRES_PORT") is not None, "Could not get env var POSTGRES_PORT"
    assert os.getenv("POSTGRES_DB") is not None, "Could not get env var POSTGRES_DB"
    engine = create_engine(
        f"postgresql+psycopg2://{os.getenv("POSTGRES_USER")}:{os.getenv("POSTGRES_PASSWORD")}@localhost:{os.getenv("POSTGRES_PORT")}/{os.getenv("POSTGRES_DB")}",
        echo=True,
    )

    _create_db_and_tables(engine)


if __name__ == "__main__":
    main()
