import random

import typer
from sqlmodel import Session, select

from smartem_decisions.model.database import FoilHole, Grid, GridSquare, Micrograph
from smartem_decisions.predictions.update import prior_update
from smartem_decisions.utils import setup_postgres_connection


def perform_random_updates(
    grid_uuid: str | None = None,
    random_range: tuple[float, float] = (0, 1),
    origin: str = "motion_correction",
) -> None:
    engine = setup_postgres_connection()
    with Session(engine) as sess:
        if grid_uuid is None:
            grid = sess.exec(select(Grid)).first()
            grid_uuid = grid.uuid
        mics = sess.exec(
            select(Micrograph, FoilHole, GridSquare)
            .where(Micrograph.foilhole_uuid == FoilHole.uuid)
            .where(FoilHole.gridsquare_uuid == GridSquare.uuid)
            .where(GridSquare.grid_uuid == grid_uuid)
        ).all()
        for m in mics:
            prior_update(random.uniform(random_range[0], random_range[1]) < 0.5, m[0].uuid, sess, origin=origin)
    return None


def run() -> None:
    typer.run(perform_random_updates)
    return None
