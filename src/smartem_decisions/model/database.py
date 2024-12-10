import os
from datetime import datetime
import random
from typing import Optional, List

# import logging
# logging.basicConfig()
# logging.getLogger("sqlalchemy.engine").setLevel(logging.DEBUG)

from dotenv import load_dotenv
from sqlalchemy import text
from sqlmodel import (
    Field,
    Session as SQLModelSession,
    SQLModel,
    create_engine,
    Relationship,
)


class Session(SQLModel, table=True):  # type: ignore
    id: Optional[int] = Field(default=None, primary_key=True)
    epu_id: Optional[str] = Field(default=None)
    name: str
    status: str = Field(default="planned")  # planned, started, completed, paused, abandoned
    time_started: Optional[datetime] = Field(default=None)
    time_finished: Optional[datetime] = Field(default=None)
    time_paused: Optional[datetime] = Field(default=None)
    grids: List["Grid"] = Relationship(back_populates="session", cascade_delete=True)


class Grid(SQLModel, table=True):  # type: ignore
    id: Optional[int] = Field(default=None, primary_key=True)
    session_id: Optional[int] = Field(default=None, foreign_key="session.id")
    status: str = Field(default="none")
    name: str
    session: Optional[Session] = Relationship(back_populates="grids")
    gridsquares: List["GridSquare"] = Relationship(back_populates="grid", cascade_delete=True)


class GridSquare(SQLModel, table=True):  # type: ignore
    id: Optional[int] = Field(default=None, primary_key=True)
    grid_id: Optional[int] = Field(default=None, foreign_key="grid.id")
    status: str = Field(default="none")
    # grid_position 5 by 5
    atlastile_img: str = ""  # path to tile image
    name: str
    grid: Optional[Grid] = Relationship(back_populates="gridsquares")
    foilholes: List["FoilHole"] = Relationship(back_populates="gridsquare", cascade_delete=True)


class FoilHole(SQLModel, table=True):  # type: ignore
    id: Optional[int] = Field(default=None, primary_key=True)
    gridsquare_id: Optional[int] = Field(default=None, foreign_key="gridsquare.id")
    name: str
    gridsquare: Optional[GridSquare] = Relationship(back_populates="foilholes")
    micrographs: List["Micrograph"] = Relationship(back_populates="foilhole", cascade_delete=True)


class Micrograph(SQLModel, table=True):  # type: ignore
    id: Optional[int] = Field(default=None, primary_key=True)
    foilhole_id: Optional[int] = Field(default=None, foreign_key="foilhole.id")
    status: str = Field(default="none")
    ctf_complete: Optional[bool] = Field(default=None)
    total_motion: Optional[float] = Field(default=None)  # TODO non-negative or null
    average_motion: Optional[float] = Field(default=None)  # TODO non-negative or null
    ctf_max_resolution_estimate: Optional[float] = Field(default=None)  # TODO non-negative or null
    particle_selection_complete: Optional[bool] = Field(default=None)
    number_of_particles_selected: Optional[int] = Field(default=None)
    number_of_particles_rejected: Optional[int] = Field(default=None)
    selection_distribution: Optional[str] = Field(default=None)  # TODO dict type (create a user-defined?)
    particle_picking_complete: Optional[bool] = Field(default=None)
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
            END $$;
        """)
        sess.execute(teardown_query)
        sess.commit()

    SQLModel.metadata.create_all(engine)


def _add_test_data(engine):
    # TODO remove this function or convert it into a test script

    """
    The number of micrographs in a single foil hole will be typically between 4 and 10.
    The total number of micrographs collected from a grid is normally 10-50k.
    The number of particles picked is about 300 per micrograph.
    About half of those are selected and half rejected
    """
    num_of_grids_in_sample_container = random.randint(1, 12) # TODO yield from generator fn
    num_of_grid_squares_in_grid = 200
    num_of_foilholes_in_gridsquare = 100
    num_of_micrographs_in_foilhole = random.randint(4, 10)  # TODO yield from generator fn

    with SQLModelSession(engine) as sess:
        # session start
        session_01 = Session(name="Untitled 01")
        sess.add(session_01)
        sess.commit()
        sess.refresh(session_01)
        grids = [
            Grid(name=f"Grid {i:02}", status="none", session_id=session_01.id)
            for i in range(1, num_of_grids_in_sample_container + 1)
        ]
        sess.add_all(grids)
        sess.commit()

        # grid scan start
        grids[0].status = "scan started"
        sess.add(grids[0])
        sess.commit()

        # grid scan complete
        sess.refresh(grids[0])
        grids[0].status = "scan complete"
        sess.add(grids[0])
        gridsquares = [
            GridSquare(name=f"Grid Square {i:02}", status="none", grid_id=grids[0].id)
            for i in range(1, num_of_grid_squares_in_grid + 1)
        ]
        sess.add_all(gridsquares)
        sess.commit()

        # grid_squares_decision_start = "grid squares decision start"
        grids[0].status = "grid squares decision start"
        sess.add(grids[0])
        sess.commit()

        # grid squares decision complete
        grids[0].status = "grid squares decision complete"
        sess.add(grids[0])
        # TODO record the actual grid squares decision
        sess.commit()

        # foil holes detected
        foilholes = [
            FoilHole(name=f"Foil Hole {i:02} of GridSquare {square.id:02}", gridsquare_id=square.id)
            for square in gridsquares
            for i in range(1, random.randint(2, num_of_foilholes_in_gridsquare + 1))
        ]
        sess.add_all(foilholes)
        # TODO update status of each GridSquare
        sess.commit()

        # foil holes decision start
        # TODO update status (on Grid Square?)
        gridsquares[0].status = "foil holes decision start"
        sess.add(gridsquares[0])
        # TODO: figure out when in the flow micrographs get added
        micrographs = [
            Micrograph(name=f"Micrograph {i:02} of FoilHole {foilhole.id:02}", foilhole_id=foilhole.id)
            for foilhole in foilholes
            for i in range(1, random.randint(2, num_of_micrographs_in_foilhole))
        ]
        sess.add_all(micrographs)
        sess.commit()

        # foil holes decision complete
        gridsquares[0].status = "foil holes decision complete"
        sess.add(gridsquares[0])
        # TODO record the actual foil holes decision
        sess.commit()

        # motion correction start
        micrographs[0].status = "motion correction start"
        sess.add(micrographs[0])
        sess.commit()

        # motion_correction_complete = "motion correction complete"
        micrographs[0].status = "motion correction complete"
        sess.add(micrographs[0])
        sess.commit()

        # ctf_start = "ctf start"
        micrographs[0].status = "ctf start"
        sess.add(micrographs[0])
        sess.commit()

        # ctf_complete = "ctf complete"
        micrographs[0].status = "ctf complete"
        micrographs[0].total_motion = 0.234
        micrographs[0].average_motion = 0.235
        micrographs[0].ctf_max_resolution_estimate = 0.236
        sess.add(micrographs[0])
        sess.commit()

        # particle_picking_start = "particle picking start"
        micrographs[0].status = "particle picking start"
        sess.add(micrographs[0])
        sess.commit()

        # particle_picking_complete = "particle picking complete"
        micrographs[0].status = "particle picking complete"
        micrographs[0].number_of_particles_picked = 10
        sess.add(micrographs[0])
        sess.commit()

        # particle_selection_start = "particle selection start"
        micrographs[0].status = "particle selection start"
        sess.add(micrographs[0])
        sess.commit()

        # particle_selection_complete = "particle selection complete"
        micrographs[0].status = "particle selection complete"
        micrographs[0].number_of_particles_selected = 10
        micrographs[0].number_of_particles_rejected = 10
        sess.add(micrographs[0])
        sess.commit()

        sess.close()


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
    # _add_test_data(engine)


if __name__ == "__main__":
    main()
