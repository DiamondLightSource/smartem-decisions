import asyncio
import random

import typer
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from sqlmodel import select

from smartem_backend.model.database import FoilHole, Grid, GridSquare, Micrograph
from smartem_backend.predictions.update import prior_update
from smartem_backend.utils import logger, setup_postgres_async_connection

DEFAULT_MOTION_CORRECTION_DELAY = (1.0, 3.0)
DEFAULT_CTF_DELAY = (2.0, 5.0)
DEFAULT_PARTICLE_PICKING_DELAY = (3.0, 8.0)
DEFAULT_PARTICLE_SELECTION_DELAY = (2.0, 6.0)

# Hold strong references to background simulation tasks so they aren't garbage
# collected mid-flight (asyncio only weakly retains tasks unless something awaits them).
_background_tasks: set[asyncio.Task] = set()


def _make_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        bind=engine, class_=AsyncSession, autocommit=False, autoflush=False, expire_on_commit=False
    )


async def perform_random_updates(
    grid_uuid: str | None = None,
    random_range: tuple[float, float] = (0, 1),
    metric: str = "motioncorrection",
    engine: AsyncEngine | None = None,
) -> None:
    if engine is None:
        engine = setup_postgres_async_connection()
    session_factory = _make_session_factory(engine)

    async with session_factory() as sess:
        if grid_uuid is None:
            grid = (await sess.execute(select(Grid))).scalars().first()
            grid_uuid = grid.uuid
        mics = (
            await sess.execute(
                select(Micrograph, FoilHole, GridSquare)
                .where(Micrograph.foilhole_uuid == FoilHole.uuid)
                .where(FoilHole.gridsquare_uuid == GridSquare.uuid)
                .where(GridSquare.grid_uuid == grid_uuid)
            )
        ).all()
        for m in mics:
            quality = float(random.uniform(random_range[0], random_range[1]) < 0.5)
            await prior_update(quality, m[0].uuid, metric, sess)
    return None


async def simulate_processing_pipeline(micrograph_uuid: str, engine: AsyncEngine | None = None) -> None:
    """Simulate the data processing pipeline for a micrograph with random delays.

    Pipeline: motion correction -> ctf -> particle picking -> particle selection.
    """
    if engine is None:
        engine = setup_postgres_async_connection()
    session_factory = _make_session_factory(engine)

    processing_steps = [
        ("motion_correction", DEFAULT_MOTION_CORRECTION_DELAY),
        ("ctf", DEFAULT_CTF_DELAY),
        ("particle_picking", DEFAULT_PARTICLE_PICKING_DELAY),
        ("particle_selection", DEFAULT_PARTICLE_SELECTION_DELAY),
    ]

    logger.info(f"Starting processing pipeline simulation for micrograph {micrograph_uuid}")

    for step_name, delay_range in processing_steps:
        delay = random.uniform(delay_range[0], delay_range[1])
        logger.debug(f"Simulating {step_name} for micrograph {micrograph_uuid}, delay: {delay:.2f}s")
        await asyncio.sleep(delay)

        try:
            async with session_factory() as sess:
                quality_result = float(random.choice([True, False]))
                await prior_update(quality_result, micrograph_uuid, step_name, sess)
                logger.info(f"Completed {step_name} for micrograph {micrograph_uuid}, quality: {quality_result}")
        except Exception as e:
            logger.error(f"Error in {step_name} for micrograph {micrograph_uuid}: {e}")

    logger.info(f"Completed processing pipeline simulation for micrograph {micrograph_uuid}")


async def simulate_processing_pipeline_async(micrograph_uuid: str, engine: AsyncEngine | None = None) -> None:
    """Spawn the processing pipeline simulation as a background asyncio task.

    Returns once the task is scheduled; the simulation runs concurrently on the
    consumer's event loop and does not block the caller.
    """
    task = asyncio.create_task(simulate_processing_pipeline(micrograph_uuid, engine))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    logger.debug(f"Started background processing simulation for micrograph {micrograph_uuid}")


def _typer_entry(
    grid_uuid: str | None = None,
    random_range: tuple[float, float] = (0, 1),
    metric: str = "motioncorrection",
) -> None:
    asyncio.run(perform_random_updates(grid_uuid, random_range, metric))


def run() -> None:
    typer.run(_typer_entry)
    return None
