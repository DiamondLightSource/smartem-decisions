import random
from typing import Annotated

import typer
from sqlmodel import Session, select

from smartem_decisions.model.database import FoilHole, Grid, GridSquare, QualityPrediction
from smartem_decisions.utils import setup_postgres_connection


def generate_random_predictions(
    model_name: str,
    grid_id: int | None = None,
    random_range: tuple[float, float] = (0, 1),
    level: Annotated[
        str, typer.Option(help="Magnification level at which to generate predictions. Options are 'hole' or 'square'")
    ] = "hole",
) -> None:
    if level not in ("hole", "square"):
        raise ValueError(f"Level must be set to either 'hole' or 'square' not {level}")
    engine = setup_postgres_connection()
    with Session(engine) as sess:
        if grid_id is None:
            grid = sess.exec(select(Grid)).first()
            grid_id = grid.id
        if level == "hole":
            holes = sess.exec(
                select(FoilHole, GridSquare)
                .where(FoilHole.gridsquare_id == GridSquare.id)
                .where(GridSquare.grid_id == grid_id)
            ).all()
            preds = [
                QualityPrediction(
                    value=random.uniform(random_range[0], random_range[1]),
                    prediction_model_name=model_name,
                    foilhole_id=h[0].id,
                )
                for h in holes
            ]
            sess.add_all(preds)
            sess.commit()
        else:
            squares = sess.exec(select(GridSquare).where(GridSquare.grid_id == grid_id)).all()
            preds = [
                QualityPrediction(
                    value=random.uniform(random_range[0], random_range[1]),
                    prediction_model_name=model_name,
                    gridsquare_id=s.id,
                )
                for s in squares
            ]
            sess.add_all(preds)
            sess.commit()

    return None


def run() -> None:
    typer.run(generate_random_predictions)
    return None
