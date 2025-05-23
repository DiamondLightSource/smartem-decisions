import math

from sqlalchemy import desc
from sqlmodel import Session, or_, select

from smartem_decisions.model.database import (
    FoilHole,
    GridSquare,
    Micrograph,
    QualityPrediction,
    QualityPredictionModel,
    QualityPredictionModelWeight,
)


def prior_update(
    quality: bool,
    micrograph_uuid: str,
    session: Session,
    origin: str | None = None,
    ignore_if_matches_previous: bool = True,
) -> None:
    # get the grid uuid from the micrograph
    # this should only ever produce a single response
    hierarchy_response = session.exec(
        select(Micrograph, FoilHole, GridSquare)
        .where(Micrograph.uuid == micrograph_uuid)
        .where(FoilHole.uuid == Micrograph.foilhole_uuid)
        .where(FoilHole.gridsquare_uuid == GridSquare.uuid)
    ).one()
    grid_uuid = hierarchy_response[2].grid_uuid
    square_uuid = hierarchy_response[2].uuid
    hole_uuid = hierarchy_response[1].uuid

    # if checking for previous updates coming from this micrograph,
    # check if there was a previous result and whether it matches this one
    previous_update_matches = True
    if ignore_if_matches_previous:
        previous_update_check = session.exec(
            select(QualityPredictionModelWeight)
            .where(QualityPredictionModelWeight.micrograph_uuid == micrograph_uuid)
            .order_by(QualityPredictionModelWeight.timestamp)
        ).all()
        if previous_update_check and previous_update_check[-1].micrograph_quality is quality:
            # matched previous update, no need to correct it
            return None
        previous_update_matches = not previous_update_check

    # seems easier to just collect the model names for future use here
    model_names = [n.name for n in session.exec(select(QualityPredictionModel)).all()]

    # main prior update logic
    posterior = 0
    updates = []
    for m in model_names:
        # predictions are attached to either the foil hole or the grid square
        # whereas model weights are attached to grids
        pred = session.exec(
            select(QualityPrediction, QualityPredictionModelWeight)
            .where(
                or_(
                    QualityPrediction.foilhole_uuid == hole_uuid,
                    QualityPrediction.gridsquare_uuid == square_uuid,
                )
            )
            .where(QualityPredictionModelWeight.grid_uuid == grid_uuid)
            .where(QualityPrediction.prediction_model_name == QualityPredictionModelWeight.prediction_model_name)
            .where(QualityPredictionModelWeight.prediction_model_name == m)
            .order_by(desc(QualityPrediction.timestamp))
            .order_by(desc(QualityPredictionModelWeight.timestamp))
        ).first()
        # logging here to make the results less swingy
        # need to check this is a legitimate thing to do
        # hopefully you still converge to the same answer as the log is monotonic
        updated_value = float(math.log(pred[1].weight * (pred[0].value if quality else (1 - pred[0].value))))
        if ignore_if_matches_previous and not previous_update_matches:
            # this may also be mathematically suspect
            updated_value = updated_value**2
        updates.append(
            QualityPredictionModelWeight(
                grid_uuid=pred[1].grid_uuid,
                micrograph_uuid=micrograph_uuid,
                micrograph_quality=quality,
                origin=origin,
                prediction_model_name=pred[1].prediction_model_name,
                weight=updated_value,
            )
        )
        posterior += updated_value

    # normalise with posterior
    for update in updates:
        update.weight = update.weight / posterior
        session.add(update)
    session.commit()
    return None
