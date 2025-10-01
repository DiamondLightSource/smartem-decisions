from datetime import datetime, timedelta

import numpy as np
from sqlalchemy import func
from sqlalchemy.orm import aliased
from sqlmodel import Session, or_, select

from smartem_backend.model.database import (
    CurrentQualityPrediction,
    CurrentQualityPredictionModelWeight,
    FoilHole,
    Grid,
    GridSquare,
    Micrograph,
    OverallQualityPrediction,
    QualityMetric,
    QualityPredictionModel,
    QualityPredictionModelWeight,
)
from smartem_common.entity_status import ModelLevel


def prior_update(
    quality: float,
    micrograph_uuid: str,
    metric: str,
    session: Session,
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

    # seems easier to just collect the model names for future use here
    model_names = [n.name for n in session.exec(select(QualityPredictionModel)).all()]

    # main prior update logic
    posterior = 0
    delta_missing = 1
    updates = []
    for m in model_names:
        # predictions are attached to either the foil hole or the grid square
        # whereas model weights are attached to grids
        pred = session.exec(
            select(CurrentQualityPrediction, CurrentQualityPredictionModelWeight)
            .where(
                or_(
                    CurrentQualityPrediction.foilhole_uuid == hole_uuid,
                    CurrentQualityPrediction.gridsquare_uuid == square_uuid,
                )
            )
            .where(CurrentQualityPredictionModelWeight.grid_uuid == grid_uuid)
            .where(
                CurrentQualityPrediction.prediction_model_name
                == CurrentQualityPredictionModelWeight.prediction_model_name
            )
            .where(CurrentQualityPredictionModelWeight.prediction_model_name == m)
            .where(CurrentQualityPredictionModelWeight.metric_name == metric)
            .where(or_(CurrentQualityPrediction.metric_name == metric, CurrentQualityPrediction.metric_name == None))  # noqa: E711
        ).first()
        if pred is None:
            weight = (
                session.exec(
                    select(CurrentQualityPredictionModelWeight)
                    .where(CurrentQualityPredictionModelWeight.grid_uuid == grid_uuid)
                    .where(CurrentQualityPredictionModelWeight.prediction_model_name == m)
                    .where(CurrentQualityPredictionModelWeight.metric_name == metric)
                )
                .one()
                .weight
            )
            delta_missing -= weight
            continue
        # logging here to make the results less swingy
        # need to check this is a legitimate thing to do
        # hopefully you still converge to the same answer as the log is monotonic
        updated_value = pred[1].weight * (quality * pred[0].value + (1 - quality) * (1 - pred[0].value))
        pred[1].weigth = updated_value
        updates.append(pred[1])
        updates.append(
            QualityPredictionModelWeight(
                grid_uuid=pred[1].grid_uuid,
                micrograph_uuid=micrograph_uuid,
                micrograph_quality=quality,
                metric_name=metric,
                prediction_model_name=pred[1].prediction_model_name,
                weight=updated_value,
            )
        )
        posterior += updated_value

    # normalise with posterior
    for update in updates:
        update.weight = delta_missing * update.weight / posterior
        session.add(update)
    session.commit()
    return None


def overall_predictions_update(grid_uuid: str, session: Session) -> None:
    # check grid to see if it has been long enough to refresh predictions
    grid = session.exec(select(Grid).where(Grid.uuid == grid_uuid)).one()
    if grid.prediction_updated_time > datetime.now() - timedelta(seconds=60):
        return None

    # seems easier to just collect the model name for future use here
    model_names = [(n.name, n.level) for n in session.exec(select(QualityPredictionModel)).all()]
    # also get all quality metric names
    metric_names = [m.name for m in session.exec(select(QualityMetric)).all()]
    weights = {
        (w.metric_name, w.prediction_model_name): w.weight
        for w in session.exec(
            select(CurrentQualityPredictionModelWeight).where(
                CurrentQualityPredictionModelWeight.grid_uuid == grid_uuid
            )
        ).all()
    }

    grid_square_counts = session.exec(
        select(GridSquare.uuid, func.count(FoilHole.uuid))
        .where(GridSquare.uuid == FoilHole.gridsquare_uuid)
        .where(FoilHole.x_location != None)  # noqa: E711
        .where(GridSquare.grid_uuid == grid_uuid)
        .order_by(GridSquare.uuid)
        .group_by(GridSquare.uuid)
    ).all()
    num_foil_holes = np.sum([gc[1] for gc in grid_square_counts])
    value_matrix = np.zeros((len(metric_names), len(model_names), num_foil_holes))

    for imet, metric in enumerate(metric_names):
        for imod, (model, model_level) in enumerate(model_names):
            foil_hole_level = model_level == ModelLevel.FOILHOLE
            if foil_hole_level:
                pred_query = (
                    select(CurrentQualityPrediction)
                    .where(
                        or_(
                            CurrentQualityPrediction.metric_name == metric,
                            CurrentQualityPrediction.metric_name == None,  # noqa: E711
                        )
                    )
                    .where(CurrentQualityPrediction.grid_uuid == grid_uuid)
                    .where(CurrentQualityPrediction.prediction_model_name == model)
                )
                if (
                    session.exec(
                        select(func.count(CurrentQualityPrediction.id))
                        .where(
                            or_(
                                CurrentQualityPrediction.metric_name == metric,
                                CurrentQualityPrediction.metric_name == None,  # noqa: E711
                            )
                        )
                        .where(CurrentQualityPrediction.grid_uuid == grid_uuid)
                        .where(CurrentQualityPrediction.prediction_model_name == model)
                    ).one()
                    == num_foil_holes
                ):
                    preds = session.exec(
                        pred_query.order_by(
                            CurrentQualityPrediction.gridsquare_uuid, CurrentQualityPrediction.foilhole_uuid
                        )
                    ).all()
                else:
                    pred_alias = aliased(CurrentQualityPrediction, pred_query.subquery())
                    gridsquare_subquery = (
                        select(GridSquare, FoilHole)
                        .where(GridSquare.grid_uuid == grid_uuid)
                        .where(FoilHole.x_location != None)  # noqa: E711
                        .where(FoilHole.gridsquare_uuid == GridSquare.uuid)
                        .subquery()
                    )
                    gridsquare_alias = aliased(FoilHole, gridsquare_subquery)
                    preds_query = (
                        select(pred_alias)
                        .select_from(gridsquare_alias)
                        .outerjoin(pred_alias, gridsquare_alias.uuid == pred_alias.foilhole_uuid)
                        .order_by(gridsquare_alias.gridsquare_uuid, gridsquare_alias.uuid)
                    )
                    preds = session.exec(preds_query).all()
                value_matrix[imet, imod] = np.array(
                    [
                        weights[(metric, model)] * p.value if p is not None else weights[(metric, model)] * 0.5
                        for p in preds
                    ]
                )
            else:
                pred_query = (
                    select(CurrentQualityPrediction)
                    .where(
                        or_(
                            CurrentQualityPrediction.metric_name == metric,
                            CurrentQualityPrediction.metric_name == None,  # noqa: E711
                        )
                    )
                    .where(CurrentQualityPrediction.gridsquare_uuid.in_([gc[0] for gc in grid_square_counts]))
                    .where(CurrentQualityPrediction.grid_uuid == grid_uuid)
                    .where(CurrentQualityPrediction.prediction_model_name == model)
                )
                if session.exec(
                    select(func.count(CurrentQualityPrediction.id))
                    .where(
                        or_(
                            CurrentQualityPrediction.metric_name == metric,
                            CurrentQualityPrediction.metric_name == None,  # noqa: E711
                        )
                    )
                    .where(CurrentQualityPrediction.gridsquare_uuid.in_([gc[0] for gc in grid_square_counts]))
                    .where(CurrentQualityPrediction.grid_uuid == grid_uuid)
                    .where(CurrentQualityPrediction.prediction_model_name == model)
                ).one() == len(grid_square_counts):
                    preds = session.exec(pred_query.order_by(CurrentQualityPrediction.gridsquare_uuid)).all()
                else:
                    pred_alias = aliased(CurrentQualityPrediction, pred_query.subquery())
                    gridsquare_subquery = (
                        select(GridSquare)
                        .where(GridSquare.grid_uuid == grid_uuid)
                        .where(GridSquare.image_path != None)  # noqa: E711
                        .subquery()
                    )
                    gridsquare_alias = aliased(GridSquare, gridsquare_subquery)
                    preds_query = (
                        select(pred_alias)
                        .select_from(gridsquare_alias)
                        .outerjoin(pred_alias, gridsquare_alias.uuid == pred_alias.gridsquare_uuid)
                        .order_by(gridsquare_alias.uuid)
                    )
                    preds = session.exec(preds_query).all()
                ctotal = 0.5
                for p, c in zip(preds, grid_square_counts, strict=True):
                    sub_values = np.ndarray(c[1])
                    sub_values[:] = (
                        weights[(metric, model)] * p.value if p is not None else weights[(metric, model)] * 0.5
                    )
                    value_matrix[imet, imod, ctotal : ctotal + c[1]] = sub_values
                    ctotal += c[1]

    summed = np.sum(value_matrix, axis=1)
    results = np.prod(summed, axis=0) ** (1 / len(summed))
    overall_preds = session.exec(
        select(OverallQualityPrediction)
        .where(OverallQualityPrediction.grid_uuid == grid_uuid)
        .order_by(OverallQualityPrediction.gridsquare_uuid, OverallQualityPrediction.foilhole_uuid)
    ).all()
    if not overall_preds:
        ids = session.exec(
            select(OverallQualityPrediction)
            .where(OverallQualityPrediction.grid_uuid == grid_uuid)
            .order_by(OverallQualityPrediction.gridsquare_uuid, OverallQualityPrediction.foilhole_uuid)
        ).all()
        overall_preds = [
            OverallQualityPrediction(grid_uuid == grid_uuid, gridsquare_uuid=i[0], foilhole_uuid=i[1], value=float(v))
            for v, i in zip(results, ids, strict=True)
        ]
    else:
        for v, op in zip(results, overall_preds, strict=True):
            op.value = float(v)
    grid.prediction_updated_time = datetime.now()
    session.add_all(overall_preds)
    session.add(grid)
    session.commit()
    return None
