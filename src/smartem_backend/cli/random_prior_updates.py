import random
import threading
import time

import typer
from sqlalchemy.engine import Engine
from sqlmodel import Session, select

from smartem_backend.model.database import FoilHole, Grid, GridSquare, Micrograph
from smartem_backend.predictions.update import prior_update
from smartem_backend.utils import get_db_engine, logger

# Default time ranges for processing steps (in seconds)
DEFAULT_MOTION_CORRECTION_DELAY = (1.0, 3.0)
DEFAULT_CTF_DELAY = (2.0, 5.0)
DEFAULT_PARTICLE_PICKING_DELAY = (3.0, 8.0)
DEFAULT_PARTICLE_SELECTION_DELAY = (2.0, 6.0)


def perform_random_updates(
    grid_uuid: str | None = None,
    random_range: tuple[float, float] = (0, 1),
    origin: str = "motion_correction",
    engine: Engine = None,
) -> None:
    if engine is None:
        engine = get_db_engine()

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


def simulate_processing_pipeline(micrograph_uuid: str, engine: Engine = None) -> None:
    """
    Simulate the data processing pipeline for a micrograph with random delays.

    Pipeline: motion correction → ctf → particle picking → particle selection

    Args:
        micrograph_uuid: UUID of the micrograph to process
        engine: Optional database engine (uses singleton if not provided)
    """
    if engine is None:
        engine = get_db_engine()

    processing_steps = [
        ("motion_correction", DEFAULT_MOTION_CORRECTION_DELAY),
        ("ctf", DEFAULT_CTF_DELAY),
        ("particle_picking", DEFAULT_PARTICLE_PICKING_DELAY),
        ("particle_selection", DEFAULT_PARTICLE_SELECTION_DELAY),
    ]

    logger.info(f"Starting processing pipeline simulation for micrograph {micrograph_uuid}")

    for step_name, delay_range in processing_steps:
        # Random delay for this processing step
        delay = random.uniform(delay_range[0], delay_range[1])
        logger.debug(f"Simulating {step_name} for micrograph {micrograph_uuid}, delay: {delay:.2f}s")
        time.sleep(delay)

        # Perform random weight update for this step - reuse the same engine
        try:
            with Session(engine) as sess:
                # Generate random quality result (True/False)
                quality_result = random.choice([True, False])
                prior_update(quality=quality_result, micrograph_uuid=micrograph_uuid, session=sess, origin=step_name)
                logger.info(f"Completed {step_name} for micrograph {micrograph_uuid}, quality: {quality_result}")
        except Exception as e:
            logger.error(f"Error in {step_name} for micrograph {micrograph_uuid}: {e}")
            # Continue with next step even if one fails

    logger.info(f"Completed processing pipeline simulation for micrograph {micrograph_uuid}")


def simulate_processing_pipeline_async(micrograph_uuid: str, engine: Engine = None) -> None:
    """
    Start the processing pipeline simulation in a background thread.

    Args:
        micrograph_uuid: UUID of the micrograph to process
        engine: Optional database engine (uses singleton if not provided)
    """
    if engine is None:
        engine = get_db_engine()

    def run_simulation():
        simulate_processing_pipeline(micrograph_uuid, engine)

    # Start simulation in background thread so it doesn't block the consumer
    thread = threading.Thread(target=run_simulation, daemon=True)
    thread.start()
    logger.debug(f"Started background processing simulation for micrograph {micrograph_uuid}")


def run() -> None:
    typer.run(perform_random_updates)
    return None
