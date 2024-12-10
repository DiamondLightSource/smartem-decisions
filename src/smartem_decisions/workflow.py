import random
from sqlmodel import select

from .model.mq_event import (
    SessionStartBody,
    GridScanStartBody,
    GridScanCompleteBody,
    GridSquaresDecisionStartBody,
    GridSquaresDecisionCompleteBody,
    FoilHolesDetectedBody,
    FoilHolesDecisionStartBody,
    FoilHolesDecisionCompleteBody,
    MotionCorrectionStartBody,
    MotionCorrectionCompleteBody,
    CtfStartBody,
    CtfCompleteBody,
    ParticlePickingStartBody,
    ParticlePickingCompleteBody,
    ParticleSelectionStartBody,
    ParticleSelectionCompleteBody,
    SessionEndBody,
)

from .model.database import (
    Session,
    Grid,
    GridSquare,
    FoilHole,
    Micrograph,
)

"""
The number of micrographs in a single foil hole will be typically between 4 and 10.
The total number of micrographs collected from a grid is normally 10-50k.
The number of particles picked is about 300 per micrograph.
About half of those are selected and half rejected
"""
# TODO move this stuff to config
num_of_grids_in_sample_container = random.randint(1, 12) # TODO yield from generator fn
num_of_grid_squares_in_grid = 200
num_of_foilholes_in_gridsquare = 100
num_of_micrographs_in_foilhole = random.randint(4, 10)  # TODO yield from generator fn


def session_start(msg: SessionStartBody, sess):
    new_session = Session(
        name=msg.name,
        epu_id=msg.epu_id,
        status="started",
    )
    sess.add(new_session)
    sess.commit()
    grids = [
        Grid(name=f"Grid {i:02}", status="none", session_id=new_session.id)
        for i in range(1, num_of_grids_in_sample_container + 1)
    ]
    sess.add_all(grids)
    sess.commit()


def grid_scan_start(msg: GridScanStartBody, sess):
    grid = sess.exec(select(Grid).where(Grid.id == msg.grid_id)).first()
    grid.status = "scan started"
    sess.add(grid)
    sess.commit()


def grid_scan_complete(msg: GridScanCompleteBody, sess):
    grid = sess.exec(select(Grid).where(Grid.id == msg.grid_id)).first()
    grid.status = "scan complete"
    sess.add(grid)
    sess.commit()
    gridsquares = [
        GridSquare(name=f"Grid Square {i:02}", status="none", grid_id=grid.id)
        for i in range(1, num_of_grid_squares_in_grid + 1)
    ]
    sess.add_all(gridsquares)
    sess.commit()


def grid_squares_decision_start(msg: GridSquaresDecisionStartBody, sess):
    grid = sess.exec(select(Grid).where(Grid.id == msg.grid_id)).first()
    grid.status = "grid squares decision start"
    sess.add(grid)
    sess.commit()


def grid_squares_decision_complete(msg: GridSquaresDecisionCompleteBody, sess):
    # TODO record the actual grid squares decision
    grid = sess.exec(select(Grid).where(Grid.id == msg.grid_id)).first()
    grid.status = "grid squares decision complete"
    sess.add(grid)
    sess.commit()


def foil_holes_detected(msg: FoilHolesDetectedBody, sess):
    gridsquares = sess.exec(select(GridSquare).where(GridSquare.grid_id == msg.grid_id)).all()
    foilholes = [
        FoilHole(name=f"Foil Hole {i:02} of GridSquare {square.id:02}", gridsquare_id=square.id)
        for square in gridsquares
        for i in range(1, random.randint(2, num_of_foilholes_in_gridsquare + 1))
    ]
    sess.add_all(foilholes)
    # TODO update status of each GridSquare
    sess.commit()


def foil_holes_decision_start(msg: FoilHolesDecisionStartBody, sess):
    gridsquare = sess.exec(select(GridSquare).where(GridSquare.id == msg.gridsquare_id)).first()
    gridsquare.status = "foil holes decision start"
    sess.add(gridsquare)
    # TODO: figure out when in the flow micrographs get added
    foilholes = sess.exec(select(FoilHole).where(FoilHole.gridsquare_id == msg.gridsquare_id)).all()
    micrographs = [
        Micrograph(name=f"Micrograph {i:02} of FoilHole {foilhole.id:02}", foilhole_id=foilhole.id)
        for foilhole in foilholes
        for i in range(1, random.randint(2, num_of_micrographs_in_foilhole))
    ]
    sess.add_all(micrographs)
    sess.commit()


def foil_holes_decision_complete(msg: FoilHolesDecisionCompleteBody, sess):
    gridsquare = sess.exec(select(GridSquare).where(GridSquare.id == msg.gridsquare_id)).first()
    gridsquare.status = "foil holes decision complete"
    sess.add(gridsquare)
    # TODO record the actual foil holes decision
    sess.commit()


def motion_correction_start(msg: MotionCorrectionStartBody, sess):
    micrograph = sess.exec(select(Micrograph).where(Micrograph.id == msg.micrograph_id)).first()
    micrograph.status = "motion correction start"
    sess.add(micrograph)
    sess.commit()


def motion_correction_complete(msg: MotionCorrectionCompleteBody, sess):
    micrograph = sess.exec(select(Micrograph).where(Micrograph.id == msg.micrograph_id)).first()
    micrograph.status = "motion correction complete"
    sess.add(micrograph)
    sess.commit()


def ctf_start(msg: CtfStartBody, sess):
    micrograph = sess.exec(select(Micrograph).where(Micrograph.id == msg.micrograph_id)).first()
    micrograph.status = "ctf start"
    sess.add(micrograph)
    sess.commit()


def ctf_complete(msg: CtfCompleteBody, sess):
    micrograph = sess.exec(select(Micrograph).where(Micrograph.id == msg.micrograph_id)).first()
    micrograph.status = "ctf complete"
    micrograph.total_motion = 0.234
    micrograph.average_motion = 0.235
    micrograph.ctf_max_resolution_estimate = 0.236
    sess.add(micrograph)
    sess.commit()


def particle_picking_start(msg: ParticlePickingStartBody, sess):
    micrograph = sess.exec(select(Micrograph).where(Micrograph.id == msg.micrograph_id)).first()
    micrograph.status = "particle picking start"
    sess.add(micrograph)
    sess.commit()


def particle_picking_complete(msg: ParticlePickingCompleteBody, sess):
    micrograph = sess.exec(select(Micrograph).where(Micrograph.id == msg.micrograph_id)).first()
    micrograph.status = "particle picking complete"
    micrograph.number_of_particles_picked = 10
    sess.add(micrograph)
    sess.commit()


def particle_selection_start(msg: ParticleSelectionStartBody, sess):
    micrograph = sess.exec(select(Micrograph).where(Micrograph.id == msg.micrograph_id)).first()
    micrograph.status = "particle selection start"
    sess.add(micrograph)
    sess.commit()


def particle_selection_complete(msg: ParticleSelectionCompleteBody, sess):
    micrograph = sess.exec(select(Micrograph).where(Micrograph.id == msg.micrograph_id)).first()
    micrograph.status = "particle selection complete"
    micrograph.number_of_particles_selected = 10
    micrograph.number_of_particles_rejected = 10
    sess.add(micrograph)
    sess.commit()


def session_end(msg: SessionEndBody, sess):
    existing_session = sess.exec(select(Session).where(Session.id == msg.session_id)).first()
    # TODO work out some stats, perform deposition
    existing_session.status = 'complete'
    sess.add(existing_session)
    sess.commit()


# sess.close()
