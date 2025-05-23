import typer
from sqlmodel import Session, select

from smartem_decisions.model.database import Grid, QualityPredictionModelWeight
from smartem_decisions.utils import setup_postgres_connection


def initialise(name: str, weight: float, grid_uuid: str | None = None) -> None:
    engine = setup_postgres_connection()
    with Session(engine) as sess:
        if grid_uuid is None:
            grid = sess.exec(select(Grid)).first()
            grid_uuid = grid.uuid
        sess.add(QualityPredictionModelWeight(grid_id=grid_uuid, prediction_model_name=name, weight=weight))
        sess.commit()
    return None


def run() -> None:
    typer.run(initialise)
    return None
