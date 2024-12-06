from typing import Optional

from sqlmodel import Field, SQLModel, create_engine


class Session(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str


class Grid(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    session_id: Optional[int] = Field(default=None, foreign_key="session.id") # ON DELETE CASCADE
    name: str


class GridSquare(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    grid_id: Optional[int] = Field(default=None, foreign_key="grid.id") # ON DELETE CASCADE
    # grid_position
    name: str


class FoilHole(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    gridsquare_id: Optional[int] = Field(default=None, foreign_key="gridsquare.id") # ON DELETE CASCADE
    name: str


class Micrograph(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    foilhole_id: Optional[int] = Field(default=None, foreign_key="foilhole.id") # ON DELETE CASCADE
    ctf_complete: bool
    total_motion: float  # TODO non-negative or null
    average_motion: float  # TODO non-negative or null
    ctf_max_resolution_estimate: float  # TODO non-negative or null
    particle_selection_complete: bool
    number_of_particles_selected: int
    number_of_particles_rejected: int
    selection_distribution: int # TODO dict type (create a user-defined?)
    particle_picking_complete: bool
    number_of_particles_picked: int # TODO non-negative or null
    pick_distribution: int # TODO dict type (create a user-defined?)

# TODO use env vars
engine = create_engine("postgresql+psycopg2://username:password@localhost:5432/default", echo=True)


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

def main():
    create_db_and_tables()

if __name__ == "__main__":
    main()
