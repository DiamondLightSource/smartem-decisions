import asyncio

import typer
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from sqlmodel import select

from smartem_backend.model.database import (
    CurrentQualityPredictionModelWeight,
    Grid,
    QualityMetric,
    QualityPredictionModel,
    QualityPredictionModelWeight,
)
from smartem_backend.utils import logger, setup_postgres_async_connection


def _make_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        bind=engine, class_=AsyncSession, autocommit=False, autoflush=False, expire_on_commit=False
    )


async def initialise_all_models_for_grid(grid_uuid: str, engine: AsyncEngine | None = None) -> None:
    if engine is None:
        engine = setup_postgres_async_connection()
    session_factory = _make_session_factory(engine)

    async with session_factory() as sess:
        models = (await sess.execute(select(QualityPredictionModel))).scalars().all()
        metrics = (await sess.execute(select(QualityMetric))).scalars().all()

        if not models:
            logger.warning(f"No prediction models found to initialise for grid {grid_uuid}")
            return

        default_weight = 1 / len(models)
        for metric in metrics:
            for model in models:
                existing_weight = (
                    (
                        await sess.execute(
                            select(QualityPredictionModelWeight).where(
                                QualityPredictionModelWeight.grid_uuid == grid_uuid,
                                QualityPredictionModelWeight.prediction_model_name == model.name,
                                QualityPredictionModelWeight.metric_name == metric.name,
                            )
                        )
                    )
                    .scalars()
                    .first()
                )

                if existing_weight is None:
                    weight_entry = QualityPredictionModelWeight(
                        grid_uuid=grid_uuid,
                        prediction_model_name=model.name,
                        weight=default_weight,
                        metric_name=metric.name,
                    )
                    current_weight_entry = CurrentQualityPredictionModelWeight(
                        grid_uuid=grid_uuid,
                        prediction_model_name=model.name,
                        weight=default_weight,
                    )
                    sess.add(weight_entry)
                    sess.add(current_weight_entry)
                    logger.info(f"Initialised weight {default_weight} for model '{model.name}' on grid {grid_uuid}")
                else:
                    logger.debug(f"Weight already exists for model '{model.name}' on grid {grid_uuid}")

        await sess.commit()


async def initialise_prediction_model_for_grid(
    name: str, weight: float, grid_uuid: str | None = None, engine: AsyncEngine | None = None
) -> None:
    if engine is None:
        engine = setup_postgres_async_connection()
    session_factory = _make_session_factory(engine)

    async with session_factory() as sess:
        if grid_uuid is None:
            grid = (await sess.execute(select(Grid))).scalars().first()
            if grid is None:
                logger.error("No grids found in database")
                return
            grid_uuid = grid.uuid

        sess.add(QualityPredictionModelWeight(grid_uuid=grid_uuid, prediction_model_name=name, weight=weight))
        await sess.commit()
        logger.info(f"Initialised weight {weight} for model '{name}' on grid {grid_uuid}")
    return None


def _typer_entry(name: str, weight: float, grid_uuid: str | None = None) -> None:
    asyncio.run(initialise_prediction_model_for_grid(name, weight, grid_uuid))


def run() -> None:
    typer.run(_typer_entry)
    return None
