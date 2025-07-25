import random
from typing import Annotated

import typer
from sqlalchemy.engine import Engine
from sqlmodel import Session, select

from smartem_decisions.model.database import FoilHole, Grid, GridSquare, QualityPrediction, QualityPredictionModel
from smartem_decisions.utils import get_db_engine, logger

DEFAULT_PREDICTION_RANGE = (0.0, 1.0)


def generate_random_predictions(
    model_name: str,
    grid_uuid: str | None = None,
    random_range: tuple[float, float] = (0, 1),
    level: Annotated[
        str, typer.Option(help="Magnification level at which to generate predictions. Options are 'hole' or 'square'")
    ] = "hole",
    engine: Engine = None,
) -> None:
    if level not in ("hole", "square"):
        raise ValueError(f"Level must be set to either 'hole' or 'square' not {level}")

    if engine is None:
        engine = get_db_engine()

    with Session(engine) as sess:
        if grid_uuid is None:
            grid = sess.exec(select(Grid)).first()
            grid_uuid = grid.uuid
        if level == "hole":
            holes = sess.exec(
                select(FoilHole, GridSquare)
                .where(FoilHole.gridsquare_uuid == GridSquare.uuid)
                .where(GridSquare.grid_uuid == grid_uuid)
            ).all()
            preds = [
                QualityPrediction(
                    value=random.uniform(random_range[0], random_range[1]),
                    prediction_model_name=model_name,
                    foilhole_uuid=h[0].uuid,
                )
                for h in holes
            ]
            sess.add_all(preds)
            sess.commit()
        else:
            squares = sess.exec(select(GridSquare).where(GridSquare.grid_uuid == grid_uuid)).all()
            preds = [
                QualityPrediction(
                    value=random.uniform(random_range[0], random_range[1]),
                    prediction_model_name=model_name,
                    gridsquare_uuid=s.uuid,
                )
                for s in squares
            ]
            sess.add_all(preds)
            sess.commit()

    return None


def generate_predictions_for_gridsquare(
    gridsquare_uuid: str, grid_uuid: str | None = None, engine: Engine = None
) -> None:
    """
    Generate random predictions for a single gridsquare using all available models.

    Args:
        gridsquare_uuid: UUID of the gridsquare to generate predictions for
        grid_uuid: UUID of the parent grid (optional, will be looked up if not provided)
        engine: Optional database engine (uses singleton if not provided)
    """
    if engine is None:
        engine = get_db_engine()

    with Session(engine) as sess:
        # Get all available prediction models
        models = sess.exec(select(QualityPredictionModel)).all()

        if not models:
            logger.warning(f"No prediction models found to generate predictions for gridsquare {gridsquare_uuid}")
            return

        # If grid_uuid not provided, look it up
        if grid_uuid is None:
            gridsquare = sess.get(GridSquare, gridsquare_uuid)
            if gridsquare is None:
                logger.error(f"GridSquare {gridsquare_uuid} not found in database")
                return
            grid_uuid = gridsquare.grid_uuid

        # Generate predictions for each model
        predictions = []
        for model in models:
            # Check if prediction already exists for this gridsquare-model combination
            existing_prediction = sess.exec(
                select(QualityPrediction).where(
                    QualityPrediction.gridsquare_uuid == gridsquare_uuid,
                    QualityPrediction.prediction_model_name == model.name,
                )
            ).first()

            if existing_prediction is None:
                prediction = QualityPrediction(
                    value=random.uniform(DEFAULT_PREDICTION_RANGE[0], DEFAULT_PREDICTION_RANGE[1]),
                    prediction_model_name=model.name,
                    gridsquare_uuid=gridsquare_uuid,
                )
                predictions.append(prediction)
                logger.info(
                    f"Generated prediction {prediction.value:.3f} for model '{model.name}' "
                    f"on gridsquare {gridsquare_uuid}"
                )
            else:
                logger.debug(f"Prediction already exists for model '{model.name}' on gridsquare {gridsquare_uuid}")

        if predictions:
            sess.add_all(predictions)
            sess.commit()
            logger.info(f"Generated {len(predictions)} predictions for gridsquare {gridsquare_uuid}")


def generate_predictions_for_foilhole(
    foilhole_uuid: str, gridsquare_uuid: str | None = None, engine: Engine = None
) -> None:
    """
    Generate random predictions for a single foilhole using all available models.

    Args:
        foilhole_uuid: UUID of the foilhole to generate predictions for
        gridsquare_uuid: UUID of the parent gridsquare (optional, for validation if provided)
        engine: Optional database engine (uses singleton if not provided)
    """
    if engine is None:
        engine = get_db_engine()

    with Session(engine) as sess:
        # Get all available prediction models
        models = sess.exec(select(QualityPredictionModel)).all()

        if not models:
            logger.warning(f"No prediction models found to generate predictions for foilhole {foilhole_uuid}")
            return

        # Optional validation: if gridsquare_uuid provided, verify the foilhole belongs to it
        if gridsquare_uuid is not None:
            foilhole = sess.get(FoilHole, foilhole_uuid)
            if foilhole is None:
                logger.error(f"FoilHole {foilhole_uuid} not found in database")
                return
            if foilhole.gridsquare_uuid != gridsquare_uuid:
                logger.error(
                    f"FoilHole {foilhole_uuid} belongs to gridsquare {foilhole.gridsquare_uuid}, not {gridsquare_uuid}"
                )
                return

        # Generate predictions for each model
        predictions = []
        for model in models:
            # Check if prediction already exists for this foilhole-model combination
            existing_prediction = sess.exec(
                select(QualityPrediction).where(
                    QualityPrediction.foilhole_uuid == foilhole_uuid,
                    QualityPrediction.prediction_model_name == model.name,
                )
            ).first()

            if existing_prediction is None:
                prediction = QualityPrediction(
                    value=random.uniform(DEFAULT_PREDICTION_RANGE[0], DEFAULT_PREDICTION_RANGE[1]),
                    prediction_model_name=model.name,
                    foilhole_uuid=foilhole_uuid,
                )
                predictions.append(prediction)
                logger.info(
                    f"Generated prediction {prediction.value:.3f} for model '{model.name}' on foilhole {foilhole_uuid}"
                )
            else:
                logger.debug(f"Prediction already exists for model '{model.name}' on foilhole {foilhole_uuid}")

        if predictions:
            sess.add_all(predictions)
            sess.commit()
            logger.info(f"Generated {len(predictions)} predictions for foilhole {foilhole_uuid}")


def run() -> None:
    typer.run(generate_random_predictions)
    return None
