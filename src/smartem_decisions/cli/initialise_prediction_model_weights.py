import typer
from sqlmodel import Session, select

from smartem_decisions.model.database import Grid, QualityPredictionModel, QualityPredictionModelWeight
from smartem_decisions.utils import logger, setup_postgres_connection


def initialise_all_models_for_grid(grid_uuid: str) -> None:
    """
    Initialise prediction model weights for all available models for a specific grid.

    Args:
        grid_uuid: UUID of the grid to initialise weights for
        default_weight: Default weight value to assign (default: DEFAULT_PREDICTION_MODEL_WEIGHT)
    """
    engine = setup_postgres_connection()
    with Session(engine) as sess:
        # Get all available prediction models
        models = sess.exec(select(QualityPredictionModel)).all()

        if not models:
            logger.warning(f"No prediction models found to initialise for grid {grid_uuid}")
            return

        # Initialise weights for each model
        default_weight = 1 / len(models)
        for model in models:
            # Check if weight already exists for this grid-model combination
            existing_weight = sess.exec(
                select(QualityPredictionModelWeight).where(
                    QualityPredictionModelWeight.grid_uuid == grid_uuid,
                    QualityPredictionModelWeight.prediction_model_name == model.name,
                )
            ).first()

            if existing_weight is None:
                weight_entry = QualityPredictionModelWeight(
                    grid_uuid=grid_uuid, prediction_model_name=model.name, weight=default_weight
                )
                sess.add(weight_entry)
                logger.info(f"Initialised weight {default_weight} for model '{model.name}' on grid {grid_uuid}")
            else:
                logger.debug(f"Weight already exists for model '{model.name}' on grid {grid_uuid}")

        sess.commit()


def initialise_prediction_model_for_grid(name: str, weight: float, grid_uuid: str | None = None) -> None:
    """
    Initialise a single prediction model weight for a grid (CLI interface).

    Args:
        name: Prediction model name
        weight: Weight value to assign
        grid_uuid: Grid UUID (if None, uses first available grid)
    """
    engine = setup_postgres_connection()
    with Session(engine) as sess:
        if grid_uuid is None:
            grid = sess.exec(select(Grid)).first()
            if grid is None:
                logger.error("No grids found in database")
                return
            grid_uuid = grid.uuid

        sess.add(QualityPredictionModelWeight(grid_uuid=grid_uuid, prediction_model_name=name, weight=weight))
        sess.commit()
        logger.info(f"Initialised weight {weight} for model '{name}' on grid {grid_uuid}")
    return None


def run() -> None:
    typer.run(initialise_prediction_model_for_grid)
    return None
