import random
from datetime import datetime, timezone
from sqlmodel import select
from sqlalchemy.exc import SQLAlchemyError

from src.smartem_decisions.utils import logger

from src.smartem_decisions.model.mq_event import (
    AcquisitionStartBody,
    GridScanStartBody,
    GridScanCompleteBody,
    GridSquaresDecisionStartBody,
    GridSquaresDecisionCompleteBody,
    FoilHolesDetectedBody,
    FoilHolesDecisionStartBody,
    FoilHolesDecisionCompleteBody,
    MicrographsDetectedBody,
    MotionCorrectionStartBody,
    MotionCorrectionCompleteBody,
    CtfStartBody,
    CtfCompleteBody,
    ParticlePickingStartBody,
    ParticlePickingCompleteBody,
    ParticleSelectionStartBody,
    ParticleSelectionCompleteBody,
    AcquisitionEndBody,
)

from src.smartem_decisions.model.database import (
    Acquisition,
    Grid,
    GridSquare,
    FoilHole,
    Micrograph,
    AcquisitionStatus,
    GridStatus,
    GridSquareStatus,
    FoilHoleStatus,
    MicrographStatus,
)

"""
The number of micrographs in a single foil hole will be typically between 4 and 10.
The total number of micrographs collected from a grid is normally 10-50k.
The number of particles picked is about 300 per micrograph.
About half of those are selected and half rejected
"""
# TODO move this stuff to config
num_of_grids_in_sample_container = random.randint(1, 12)  # TODO yield from generator fn
num_of_grid_squares_in_grid = 200
num_of_foilholes_in_gridsquare = 100
num_of_micrographs_in_foilhole = random.randint(4, 10)  # TODO yield from generator fn


def acquisition_start(msg: AcquisitionStartBody, sess) -> Acquisition | None:
    """
    Start a new session and create associated grids.

    Args:
        msg: Session start request body
        sess: Database session

    Returns:
        The newly created session
    """
    try:
        new_acquisition = Acquisition(
            name=msg.name,
            status=AcquisitionStatus.STARTED,
            start_time=datetime.now(timezone.utc),
            **({"epu_id": msg.epu_id} if msg.epu_id is not None else {}),
        )
        sess.add(new_acquisition)
        sess.flush()
        grids = [
            Grid(name=f"Grid {i:02}", acquisition_id=new_acquisition.id) for i in range(1, num_of_grids_in_sample_container + 1)
        ]
        sess.add_all(grids)
        sess.commit()
        return new_acquisition

    except SQLAlchemyError as e:
        sess.rollback()
        logger.error(f"Database error occurred: {str(e)}")
        raise

    except Exception as e:
        sess.rollback()
        logger.error(f"Unexpected error occurred: {str(e)}")
        raise


def grid_scan_start(msg: GridScanStartBody, sess) -> Grid | None:
    """
    Start a grid scan and update its status.

    Args:
        msg (GridScanStartBody): The message body containing the grid_id.
        sess: The database session.

    Returns:
        Optional[Grid]: The updated Grid object if found, None otherwise.

    Raises:
        SQLAlchemyError: If there's a database-related error.
    """
    try:
        grid = sess.exec(select(Grid).where(Grid.id == msg.grid_id)).first()
        if not grid:
            logger.warning(f"Grid with id {msg.grid_id} not found.")
            return None

        grid.status = GridStatus.SCAN_STARTED
        sess.add(grid)
        sess.commit()
        sess.refresh(grid)
        return grid

    except SQLAlchemyError as e:
        sess.rollback()
        logger.error(f"Database error occurred: {str(e)}")
        raise

    except Exception as e:
        sess.rollback()
        logger.error(f"Unexpected error occurred: {str(e)}")
        raise


# TODO check if list[GridSquare] | None could be replaced with Grid | None as that would presumably
#   contain gridsquares via a backref anyway?
def grid_scan_complete(msg: GridScanCompleteBody, sess) -> list[GridSquare] | None:
    """
    Complete a grid scan, update its status, and create associated grid squares.

    Args:
        msg (GridScanCompleteBody): The message body containing the grid_id.
        sess: The database session.

    Returns:
        Optional[List[GridSquare]]: A list of newly created GridSquare objects if successful, None otherwise.

    Raises:
        SQLAlchemyError: If there's a database-related error.
    """
    try:
        grid = sess.exec(select(Grid).where(Grid.id == msg.grid_id)).first()
        if not grid:
            logger.warning(f"Grid with id {msg.grid_id} not found.")
            return None

        grid.status = GridStatus.SCAN_COMPLETED
        sess.add(grid)
        sess.flush()

        gridsquares = [
            GridSquare(name=f"Grid Square {i:02}", grid_id=grid.id) for i in range(1, num_of_grid_squares_in_grid + 1)
        ]
        sess.add_all(gridsquares)
        sess.commit()

        # Refresh the gridsquares to ensure they have their database-generated IDs
        # for gridsquare in gridsquares:
        #     sess.refresh(gridsquare)
        sess.refresh(grid, attribute_names=["gridsquares"])
        gridsquares = grid.gridsquares

        return gridsquares

    except SQLAlchemyError as e:
        sess.rollback()
        logger.error(f"Database error occurred: {str(e)}")
        raise

    except Exception as e:
        sess.rollback()
        logger.error(f"Unexpected error occurred: {str(e)}")
        raise


# TODO check if list[GridSquare] | None could be replaced with Grid | None as that would presumably
#   contain gridsquares via a backref anyway?
def grid_squares_decision_start(msg: GridSquaresDecisionStartBody, sess) -> Grid | None:
    """
    Start the grid squares decision process for a grid.

    Args:
        msg (GridSquaresDecisionStartBody): The message body containing the grid_id.
        sess: The database session.

    Returns:
        Optional[Grid]: The updated Grid object if found, None otherwise.

    Raises:
        SQLAlchemyError: If there's a database-related error.
    """
    try:
        grid = sess.exec(select(Grid).where(Grid.id == msg.grid_id)).first()
        if not grid:
            logger.warning(f"Grid with id {msg.grid_id} not found.")
            return None

        grid.status = GridStatus.GRID_SQUARES_DECISION_STARTED
        sess.add(grid)
        sess.commit()
        sess.refresh(grid)
        return grid

    except SQLAlchemyError as e:
        sess.rollback()
        logger.error(f"Database error occurred: {str(e)}")
        raise

    except Exception as e:
        sess.rollback()
        logger.error(f"Unexpected error occurred: {str(e)}")
        raise


# TODO record the actual grid squares decision
# TODO check if list[GridSquare] | None could be replaced with Grid | None as that would presumably
#   contain gridsquares via a backref anyway?
def grid_squares_decision_complete(msg: GridSquaresDecisionCompleteBody, sess) -> Grid | None:
    """
    Complete the grid squares decision process for a grid.

    Args:
        msg (GridSquaresDecisionCompleteBody): The message body containing the grid_id.
        sess: The database session.

    Returns:
        Optional[Grid]: The updated Grid object if found, None otherwise.

    Raises:
        SQLAlchemyError: If there's a database-related error.
    """
    try:
        grid = sess.exec(select(Grid).where(Grid.id == msg.grid_id)).first()
        if not grid:
            logger.warning(f"Grid with id {msg.grid_id} not found.")
            return None

        grid.status = GridStatus.GRID_SQUARES_DECISION_COMPLETED
        sess.add(grid)
        sess.commit()
        sess.refresh(grid)
        return grid

    except SQLAlchemyError as e:
        sess.rollback()
        logger.error(f"Database error occurred: {str(e)}")
        raise

    except Exception as e:
        sess.rollback()
        logger.error(f"Unexpected error occurred: {str(e)}")
        raise


# TODO update status of each GridSquare for which foil holes were detected
def foil_holes_detected(msg: FoilHolesDetectedBody, sess) -> list[FoilHole] | None:
    """
    Detect and create foil holes for grid squares associated with a given grid.

    Args:
        msg (FoilHolesDetectedBody): The message body containing the grid_id.
        sess (Acquisition): The database session.

    Returns:
        Optional[List[FoilHole]]: A list of newly created FoilHole objects if successful, None otherwise.

    Raises:
        SQLAlchemyError: If there's a database-related error.
    """
    try:
        gridsquares = sess.exec(select(GridSquare).where(GridSquare.grid_id == msg.grid_id)).all()
        if not gridsquares:
            logger.warning(f"No grid squares found for grid id {msg.grid_id}.")
            return None

        foilholes = [
            FoilHole(name=f"Foil Hole {i:02} of GridSquare {square.id:02}", gridsquare_id=square.id)
            for square in gridsquares
            for i in range(1, random.randint(2, num_of_foilholes_in_gridsquare + 1))
        ]
        sess.add_all(foilholes)
        sess.commit()

        # Refresh all foilholes in a single operation
        sess.refresh(gridsquares[0], attribute_names=["foilholes"])
        foilholes = [foilhole for gridsquare in gridsquares for foilhole in gridsquare.foilholes]

        return foilholes

    except SQLAlchemyError as e:
        sess.rollback()
        logger.error(f"Database error occurred: {str(e)}")
        raise

    except Exception as e:
        sess.rollback()
        logger.error(f"Unexpected error occurred: {str(e)}")
        raise


def foil_holes_decision_start(msg: FoilHolesDecisionStartBody, sess) -> list[Micrograph] | None:
    """
    Start the foil holes decision process for a grid square and create associated micrographs.

    Args:
        msg (FoilHolesDecisionStartBody): The message body containing the gridsquare_id.
        sess: The database session.

    Returns:
        Optional[List[Micrograph]]: A list of newly created Micrograph objects if successful, None otherwise.

    Raises:
        SQLAlchemyError: If there's a database-related error.
    """
    try:
        gridsquare = sess.exec(select(GridSquare).where(GridSquare.id == msg.gridsquare_id)).first()
        if not gridsquare:
            logger.warning(f"GridSquare with id {msg.gridsquare_id} not found.")
            return None

        gridsquare.status = GridSquareStatus.FOIL_HOLES_DECISION_STARTED
        sess.add(gridsquare)

        foilholes = sess.exec(select(FoilHole).where(FoilHole.gridsquare_id == msg.gridsquare_id)).all()
        if not foilholes:
            logger.warning(f"No foil holes found for GridSquare id {msg.gridsquare_id}.")
            return None

        sess.commit()

        # Refresh all micrographs to ensure they have their database-generated IDs
        sess.refresh(gridsquare, attribute_names=["foilholes"])
        micrographs = [micrograph for foilhole in gridsquare.foilholes for micrograph in foilhole.micrographs]

        return micrographs

    except SQLAlchemyError as e:
        sess.rollback()
        logger.error(f"Database error occurred: {str(e)}")
        raise

    except Exception as e:
        sess.rollback()
        logger.error(f"Unexpected error occurred: {str(e)}")
        raise


# TODO record the actual foilholes decision and identify what format that might have
def foil_holes_decision_complete(msg: FoilHolesDecisionCompleteBody, sess) -> GridSquare | None:
    """
    Complete the foil holes decision process for a grid square.

    Args:
        msg (FoilHolesDecisionCompleteBody): The message body containing the gridsquare_id.
        sess: The database session.

    Returns:
        Optional[GridSquare]: The updated GridSquare object if found, None otherwise.

    Raises:
        SQLAlchemyError: If there's a database-related error.
    """
    try:
        gridsquare = sess.exec(select(GridSquare).where(GridSquare.id == msg.gridsquare_id)).first()
        if not gridsquare:
            logger.warning(f"GridSquare with id {msg.gridsquare_id} not found.")
            return None

        gridsquare.status = GridSquareStatus.FOIL_HOLES_DECISION_COMPLETED
        sess.add(gridsquare)
        sess.commit()
        sess.refresh(gridsquare)

        return gridsquare

    except SQLAlchemyError as e:
        sess.rollback()
        logger.error(f"Database error occurred: {str(e)}")
        raise

    except Exception as e:
        sess.rollback()
        logger.error(f"Unexpected error occurred: {str(e)}")
        raise


def micrographs_detected(msg: MicrographsDetectedBody, sess) -> list[Micrograph] | None:
    """
    Detect and create micrographs for foil holes associated with a given grid square.
    On the microscope the user will create a template for the micrograph shots they want to take in the foil holes,
    and that template is then applied to every hole during collection.
    Then once the micrographs are collected we know which hole they are in as the first part of
    the name is always `FoilHole_XXXX`

    Args:
        msg (MicrographsDetectedBody): The message body containing foilhole_id.
        sess: The database session.

    Returns:
        Optional[List[Micrograph]]: A list of newly created Micrograph objects with database IDs if successful, None otherwise.

    Raises:
        SQLAlchemyError: If there's a database-related error.
    """
    try:
        # Check if the foil hole exists
        foil_hole = sess.exec(select(FoilHole).where(FoilHole.id == msg.foilhole_id)).first()
        if not foil_hole:
            logger.warning(f"FoilHole with id {msg.foilhole_id} not found.")
            return None

        micrographs = [
            Micrograph(name=f"Micrograph {i:02} of FoilHole {msg.foilhole_id:02}", foilhole_id=msg.foilhole_id)
            for i in range(1, random.randint(2, num_of_micrographs_in_foilhole))
        ]
        sess.add_all(micrographs)

        foil_hole.status = FoilHoleStatus.MICROGRAPHS_DETECTED
        sess.add(foil_hole)

        sess.commit()

        # Refresh the micrographs to ensure they have their database-generated IDs
        for micrograph in micrographs:
            sess.refresh(micrograph)

        return micrographs

    except SQLAlchemyError as e:
        sess.rollback()
        logger.error(f"Database error occurred: {str(e)}")
        raise

    except Exception as e:
        sess.rollback()
        logger.error(f"Unexpected error occurred: {str(e)}")
        raise


def motion_correction_start(msg: MotionCorrectionStartBody, sess) -> Micrograph | None:
    """
    Start the motion correction process for a micrograph.

    Args:
        msg (MotionCorrectionStartBody): The message body containing the micrograph_id.
        sess: The database session.

    Returns:
        Optional[Micrograph]: The updated Micrograph object if found, None otherwise.

    Raises:
        SQLAlchemyError: If there's a database-related error.
    """
    try:
        micrograph = sess.exec(select(Micrograph).where(Micrograph.id == msg.micrograph_id)).first()
        if not micrograph:
            logger.warning(f"Micrograph with id {msg.micrograph_id} not found.")
            return None

        micrograph.status = MicrographStatus.MOTION_CORRECTION_STARTED
        sess.add(micrograph)
        sess.commit()
        sess.refresh(micrograph)

        return micrograph

    except SQLAlchemyError as e:
        sess.rollback()
        logger.error(f"Database error occurred: {str(e)}")
        raise

    except Exception as e:
        sess.rollback()
        logger.error(f"Unexpected error occurred: {str(e)}")
        raise


def motion_correction_complete(msg: MotionCorrectionCompleteBody, sess) -> Micrograph | None:
    """
    Complete the motion correction process for a micrograph.

    Args:
        msg (MotionCorrectionCompleteBody): The message body containing the micrograph_id.
        sess: The database session.

    Returns:
        Optional[Micrograph]: The updated Micrograph object if found, None otherwise.

    Raises:
        SQLAlchemyError: If there's a database-related error.
    """
    try:
        micrograph = sess.exec(select(Micrograph).where(Micrograph.id == msg.micrograph_id)).first()
        if not micrograph:
            logger.warning(f"Micrograph with id {msg.micrograph_id} not found.")
            return None

        micrograph.status = MicrographStatus.MOTION_CORRECTION_COMPLETED
        sess.add(micrograph)
        sess.commit()
        sess.refresh(micrograph)

        return micrograph

    except SQLAlchemyError as e:
        sess.rollback()
        logger.error(f"Database error occurred: {str(e)}")
        raise

    except Exception as e:
        sess.rollback()
        logger.error(f"Unexpected error occurred: {str(e)}")
        raise


def ctf_start(msg: CtfStartBody, sess) -> Micrograph | None:
    """
    Start the Contrast Transfer Function (CTF) process for a micrograph.

    Args:
        msg (CtfStartBody): The message body containing the micrograph_id.
        sess: The database session.

    Returns:
        Optional[Micrograph]: The updated Micrograph object if found, None otherwise.

    Raises:
        SQLAlchemyError: If there's a database-related error.
    """
    try:
        micrograph = sess.exec(select(Micrograph).where(Micrograph.id == msg.micrograph_id)).first()
        if not micrograph:
            logger.warning(f"Micrograph with id {msg.micrograph_id} not found.")
            return None

        micrograph.status = MicrographStatus.CTF_STARTED
        sess.add(micrograph)
        sess.commit()
        sess.refresh(micrograph)

        return micrograph

    except SQLAlchemyError as e:
        sess.rollback()
        logger.error(f"Database error occurred: {str(e)}")
        raise

    except Exception as e:
        sess.rollback()
        logger.error(f"Unexpected error occurred: {str(e)}")
        raise


def ctf_complete(msg: CtfCompleteBody, sess) -> Micrograph | None:
    """
    Complete the Contrast Transfer Function (CTF) process for a micrograph.

    Args:
        msg (CtfCompleteBody): The message body containing the micrograph_id.
        sess: The database session.

    Returns:
        Optional[Micrograph]: The updated Micrograph object if found, None otherwise.

    Raises:
        SQLAlchemyError: If there's a database-related error.
    """
    try:
        micrograph = sess.exec(select(Micrograph).where(Micrograph.id == msg.micrograph_id)).first()
        if not micrograph:
            logger.warning(f"Micrograph with id {msg.micrograph_id} not found.")
            return None

        micrograph.status = MicrographStatus.CTF_COMPLETED
        # TODO all these values should be coming from `msg`
        micrograph.total_motion = 0.234  # Replace with actual value as needed
        micrograph.average_motion = 0.235  # Replace with actual value as needed
        micrograph.ctf_max_resolution_estimate = 0.236  # Replace with actual value as needed

        sess.add(micrograph)
        sess.commit()
        sess.refresh(micrograph)

        return micrograph

    except SQLAlchemyError as e:
        sess.rollback()
        logger.error(f"Database error occurred: {str(e)}")
        raise

    except Exception as e:
        sess.rollback()
        logger.error(f"Unexpected error occurred: {str(e)}")
        raise


def particle_picking_start(msg: ParticlePickingStartBody, sess) -> Micrograph | None:
    """
    Start the particle picking process for a micrograph.

    Args:
        msg (ParticlePickingStartBody): The message body containing the micrograph_id.
        sess: The database session.

    Returns:
        Optional[Micrograph]: The updated Micrograph object if found, None otherwise.

    Raises:
        SQLAlchemyError: If there's a database-related error.
    """
    try:
        micrograph = sess.exec(select(Micrograph).where(Micrograph.id == msg.micrograph_id)).first()
        if not micrograph:
            logger.warning(f"Micrograph with id {msg.micrograph_id} not found.")
            return None

        micrograph.status = MicrographStatus.PARTICLE_PICKING_STARTED
        sess.add(micrograph)
        sess.commit()
        sess.refresh(micrograph)

        return micrograph

    except SQLAlchemyError as e:
        sess.rollback()
        logger.error(f"Database error occurred: {str(e)}")
        raise

    except Exception as e:
        sess.rollback()
        logger.error(f"Unexpected error occurred: {str(e)}")
        raise


def particle_picking_complete(msg: ParticlePickingCompleteBody, sess) -> Micrograph | None:
    """
    Complete the particle picking process for a micrograph.

    Args:
        msg (ParticlePickingCompleteBody): The message body containing the micrograph_id.
        sess: The database session.

    Returns:
        Optional[Micrograph]: The updated Micrograph object if found, None otherwise.

    Raises:
        SQLAlchemyError: If there's a database-related error.
    """
    try:
        micrograph = sess.exec(select(Micrograph).where(Micrograph.id == msg.micrograph_id)).first()
        if not micrograph:
            logger.warning(f"Micrograph with id {msg.micrograph_id} not found.")
            return None

        micrograph.status = MicrographStatus.PARTICLE_PICKING_COMPLETED
        micrograph.number_of_particles_picked = 10  # Replace this with actual value as needed
        sess.add(micrograph)
        sess.commit()
        sess.refresh(micrograph)

        return micrograph

    except SQLAlchemyError as e:
        sess.rollback()
        logger.error(f"Database error occurred: {str(e)}")
        raise

    except Exception as e:
        sess.rollback()
        logger.error(f"Unexpected error occurred: {str(e)}")
        raise


def particle_selection_start(msg: ParticleSelectionStartBody, sess) -> Micrograph | None:
    """
    Start the particle selection process for a micrograph.

    Args:
        msg (ParticleSelectionStartBody): The message body containing the micrograph_id.
        sess: The database session.

    Returns:
        Optional[Micrograph]: The updated Micrograph object if found, None otherwise.

    Raises:
        SQLAlchemyError: If there's a database-related error.
    """
    try:
        micrograph = sess.exec(select(Micrograph).where(Micrograph.id == msg.micrograph_id)).first()
        if not micrograph:
            logger.warning(f"Micrograph with id {msg.micrograph_id} not found.")
            return None

        micrograph.status = MicrographStatus.PARTICLE_SELECTION_STARTED
        sess.add(micrograph)
        sess.commit()
        sess.refresh(micrograph)

        return micrograph

    except SQLAlchemyError as e:
        sess.rollback()
        logger.error(f"Database error occurred: {str(e)}")
        raise

    except Exception as e:
        sess.rollback()
        logger.error(f"Unexpected error occurred: {str(e)}")
        raise


def particle_selection_complete(msg: ParticleSelectionCompleteBody, sess) -> Micrograph | None:
    """
    Complete the particle selection process for a micrograph.

    Args:
        msg (ParticleSelectionCompleteBody): The message body containing the micrograph_id.
        sess: The database session.

    Returns:
        Optional[Micrograph]: The updated Micrograph object if found, None otherwise.

    Raises:
        SQLAlchemyError: If there's a database-related error.
    """
    try:
        micrograph = sess.exec(select(Micrograph).where(Micrograph.id == msg.micrograph_id)).first()
        if not micrograph:
            logger.warning(f"Micrograph with id {msg.micrograph_id} not found.")
            return None

        micrograph.status = MicrographStatus.PARTICLE_SELECTION_COMPLETED
        micrograph.number_of_particles_selected = 10  # Replace with actual value as needed
        micrograph.number_of_particles_rejected = 10  # Replace with actual value as needed

        sess.add(micrograph)
        sess.commit()
        sess.refresh(micrograph)

        return micrograph

    except SQLAlchemyError as e:
        sess.rollback()
        logger.error(f"Database error occurred: {str(e)}")
        raise

    except Exception as e:
        sess.rollback()
        logger.error(f"Unexpected error occurred: {str(e)}")
        raise


def acquisition_end(msg: AcquisitionEndBody, sess) -> Acquisition | None:
    """
    Complete the session process for a given session ID. TODO work out some stats, trigger deposition

    Args:
        msg (AcquisitionEndBody): The message body containing the session_id.
        sess: The database session.

    Returns:
        Optional[Session]: The updated Session object if found, None otherwise.

    Raises:
        SQLAlchemyError: If there's a database-related error.
    """
    try:
        existing_acquisition = sess.exec(select(Acquisition).where(Acquisition.id == msg.acquisition_id)).first()
        if not existing_acquisition:
            logger.warning(f"Session with id {msg.acquisition_id} not found.")
            return None

        existing_acquisition.status = AcquisitionStatus.COMPLETED
        existing_acquisition.end_time = datetime.now(timezone.utc)
        sess.add(existing_acquisition)
        sess.commit()
        sess.refresh(existing_acquisition)

        return existing_acquisition

    except SQLAlchemyError as e:
        sess.rollback()
        logger.error(f"Database error occurred: {str(e)}")
        raise

    except Exception as e:
        sess.rollback()
        logger.error(f"Unexpected error occurred: {str(e)}")
        raise
