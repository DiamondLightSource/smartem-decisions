from datetime import datetime, timedelta

import numpy as np
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased
from sqlmodel import and_, or_, select

from smartem_backend.model.database import (
    CurrentQualityGroupPrediction,
    CurrentQualityPrediction,
    CurrentQualityPredictionModelWeight,
    FoilHole,
    FoilHoleGroupMembership,
    Grid,
    GridSquare,
    Micrograph,
    OverallQualityPrediction,
    QualityMetric,
    QualityPredictionModel,
    QualityPredictionModelWeight,
)
from smartem_common.entity_status import ModelLevel


async def prior_update(
    quality: float,
    micrograph_uuid: str,
    metric: str,
    session: AsyncSession,
) -> None:
    # get the grid uuid from the micrograph
    # this should only ever produce a single response
    hierarchy_response = (
        await session.execute(
            select(Micrograph, FoilHole, GridSquare)
            .where(Micrograph.uuid == micrograph_uuid)
            .where(FoilHole.uuid == Micrograph.foilhole_uuid)
            .where(FoilHole.gridsquare_uuid == GridSquare.uuid)
        )
    ).one()
    grid_uuid = hierarchy_response[2].grid_uuid
    square_uuid = hierarchy_response[2].uuid
    hole_uuid = hierarchy_response[1].uuid

    model_rows = (await session.execute(select(QualityPredictionModel))).scalars().all()
    model_names = [(n.name, n.level) for n in model_rows]

    # main prior update logic
    posterior = 0
    delta_missing = 1
    updates = []
    for m, model_level in model_names:
        weight_row = (
            (
                await session.execute(
                    select(CurrentQualityPredictionModelWeight)
                    .where(CurrentQualityPredictionModelWeight.grid_uuid == grid_uuid)
                    .where(CurrentQualityPredictionModelWeight.prediction_model_name == m)
                    .where(CurrentQualityPredictionModelWeight.metric_name == metric)
                )
            )
            .scalars()
            .one()
        )

        if model_level == ModelLevel.FOILHOLEGROUP:
            # predictions are stored once per group; look up via group membership
            pred_value = (
                (
                    await session.execute(
                        select(CurrentQualityGroupPrediction.value)
                        .where(CurrentQualityGroupPrediction.group_uuid == FoilHoleGroupMembership.group_uuid)
                        .where(FoilHoleGroupMembership.foilhole_uuid == hole_uuid)
                        .where(CurrentQualityGroupPrediction.prediction_model_name == m)
                        .where(
                            or_(
                                CurrentQualityGroupPrediction.metric_name == metric,
                                CurrentQualityGroupPrediction.metric_name == None,  # noqa: E711
                            )
                        )
                    )
                )
                .scalars()
                .first()
            )
        else:
            # FOILHOLE and GRIDSQUARE predictions stored in CurrentQualityPrediction
            pred_row = (
                (
                    await session.execute(
                        select(CurrentQualityPrediction)
                        .where(
                            or_(
                                and_(
                                    CurrentQualityPrediction.foilhole_uuid == hole_uuid,
                                    CurrentQualityPrediction.gridsquare_uuid == square_uuid,
                                ),
                                and_(
                                    CurrentQualityPrediction.foilhole_uuid == None,  # noqa: E711
                                    CurrentQualityPrediction.gridsquare_uuid == square_uuid,
                                ),
                            )
                        )
                        .where(CurrentQualityPrediction.prediction_model_name == m)
                        .where(
                            or_(
                                CurrentQualityPrediction.metric_name == metric,
                                CurrentQualityPrediction.metric_name == None,  # noqa: E711
                            )
                        )
                    )
                )
                .scalars()
                .first()
            )
            pred_value = pred_row.value if pred_row is not None else None

        if pred_value is None:
            delta_missing -= weight_row.weight
            continue

        updated_value = weight_row.weight * (quality * pred_value + (1 - quality) * (1 - pred_value))
        weight_row.weight = updated_value
        updates.append(weight_row)
        updates.append(
            QualityPredictionModelWeight(
                grid_uuid=weight_row.grid_uuid,
                micrograph_uuid=micrograph_uuid,
                micrograph_quality=quality >= 0.5,
                metric_name=metric,
                prediction_model_name=weight_row.prediction_model_name,
                weight=updated_value,
                prediction_value=pred_value,
                quality_score=quality,
            )
        )
        posterior += updated_value

    # normalise with posterior
    for update in updates:
        update.weight = delta_missing * update.weight / posterior
        session.add(update)
    await session.commit()
    return None


async def overall_predictions_update(grid_uuid: str, session: AsyncSession) -> None:
    # check grid to see if it has been long enough to refresh predictions
    grid = (await session.execute(select(Grid).where(Grid.uuid == grid_uuid))).scalars().one()
    if grid.prediction_updated_time > datetime.now() - timedelta(seconds=60):
        return None

    # seems easier to just collect the model name for future use here
    model_rows = (await session.execute(select(QualityPredictionModel))).scalars().all()
    model_names = [(n.name, n.level) for n in model_rows]
    # also get all quality metric names
    metric_rows = (await session.execute(select(QualityMetric))).scalars().all()
    metric_names = [m.name for m in metric_rows]
    weight_rows = (
        (
            await session.execute(
                select(CurrentQualityPredictionModelWeight).where(
                    CurrentQualityPredictionModelWeight.grid_uuid == grid_uuid
                )
            )
        )
        .scalars()
        .all()
    )
    weights = {(w.metric_name, w.prediction_model_name): w.weight for w in weight_rows}

    grid_square_counts = (
        await session.execute(
            select(GridSquare.uuid, func.count(FoilHole.uuid))
            .where(GridSquare.uuid == FoilHole.gridsquare_uuid)
            .where(FoilHole.x_location != None)  # noqa: E711
            .where(GridSquare.grid_uuid == grid_uuid)
            .order_by(GridSquare.uuid)
            .group_by(GridSquare.uuid)
        )
    ).all()
    num_foil_holes = np.sum([gc[1] for gc in grid_square_counts])
    value_matrix = np.zeros((len(metric_names), len(model_names), num_foil_holes))

    # Ordered list of (gridsquare_uuid, foilhole_uuid) matching the value_matrix column order
    ordered_foilhole_ids = (
        await session.execute(
            select(GridSquare.uuid, FoilHole.uuid)
            .where(GridSquare.uuid == FoilHole.gridsquare_uuid)
            .where(FoilHole.x_location != None)  # noqa: E711
            .where(GridSquare.grid_uuid == grid_uuid)
            .order_by(GridSquare.uuid, FoilHole.uuid)
        )
    ).all()

    for imet, metric in enumerate(metric_names):
        for imod, (model, model_level) in enumerate(model_names):
            metric_filter = or_(
                CurrentQualityPrediction.metric_name == metric,
                CurrentQualityPrediction.metric_name == None,  # noqa: E711
            )
            if model_level == ModelLevel.FOILHOLE:
                pred_query = (
                    select(CurrentQualityPrediction)
                    .where(metric_filter)
                    .where(CurrentQualityPrediction.grid_uuid == grid_uuid)
                    .where(CurrentQualityPrediction.prediction_model_name == model)
                )
                count = (
                    (
                        await session.execute(
                            select(func.count(CurrentQualityPrediction.id))
                            .where(metric_filter)
                            .where(CurrentQualityPrediction.grid_uuid == grid_uuid)
                            .where(CurrentQualityPrediction.prediction_model_name == model)
                        )
                    )
                    .scalars()
                    .one()
                )
                if count == num_foil_holes:
                    preds = (
                        (
                            await session.execute(
                                pred_query.order_by(
                                    CurrentQualityPrediction.gridsquare_uuid, CurrentQualityPrediction.foilhole_uuid
                                )
                            )
                        )
                        .scalars()
                        .all()
                    )
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
                    preds = (await session.execute(preds_query)).scalars().all()
                value_matrix[imet, imod] = np.array(
                    [
                        weights[(metric, model)] * p.value if p is not None else weights[(metric, model)] * 0.5
                        for p in preds
                    ]
                )
            elif model_level == ModelLevel.GRIDSQUARE:
                pred_query = (
                    select(CurrentQualityPrediction)
                    .where(metric_filter)
                    .where(CurrentQualityPrediction.gridsquare_uuid.in_([gc[0] for gc in grid_square_counts]))
                    .where(CurrentQualityPrediction.grid_uuid == grid_uuid)
                    .where(CurrentQualityPrediction.prediction_model_name == model)
                )
                count = (
                    (
                        await session.execute(
                            select(func.count(CurrentQualityPrediction.id))
                            .where(metric_filter)
                            .where(CurrentQualityPrediction.gridsquare_uuid.in_([gc[0] for gc in grid_square_counts]))
                            .where(CurrentQualityPrediction.grid_uuid == grid_uuid)
                            .where(CurrentQualityPrediction.prediction_model_name == model)
                        )
                    )
                    .scalars()
                    .one()
                )
                if count == len(grid_square_counts):
                    preds = (
                        (await session.execute(pred_query.order_by(CurrentQualityPrediction.gridsquare_uuid)))
                        .scalars()
                        .all()
                    )
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
                    preds = (await session.execute(preds_query)).scalars().all()
                ctotal = 0
                for p, c in zip(preds, grid_square_counts, strict=True):
                    sub_values = np.ndarray(c[1])
                    sub_values[:] = (
                        weights[(metric, model)] * p.value if p is not None else weights[(metric, model)] * 0.5
                    )
                    value_matrix[imet, imod, ctotal : ctotal + c[1]] = sub_values
                    ctotal += c[1]
            elif model_level == ModelLevel.FOILHOLEGROUP:
                # Build a foilhole_uuid -> value map from group predictions for this model/metric
                group_preds = (
                    await session.execute(
                        select(FoilHoleGroupMembership.foilhole_uuid, CurrentQualityGroupPrediction.value)
                        .where(CurrentQualityGroupPrediction.grid_uuid == grid_uuid)
                        .where(CurrentQualityGroupPrediction.prediction_model_name == model)
                        .where(
                            or_(
                                CurrentQualityGroupPrediction.metric_name == metric,
                                CurrentQualityGroupPrediction.metric_name == None,  # noqa: E711
                            )
                        )
                        .where(FoilHoleGroupMembership.group_uuid == CurrentQualityGroupPrediction.group_uuid)
                    )
                ).all()
                group_value_by_fh = dict(group_preds)
                value_matrix[imet, imod] = np.array(
                    [
                        weights[(metric, model)] * group_value_by_fh.get(fh_uuid, 0.5)
                        for _, fh_uuid in ordered_foilhole_ids
                    ]
                )

    summed = np.sum(value_matrix, axis=1)
    results = np.prod(summed, axis=0) ** (1 / len(summed))
    overall_preds = (
        (
            await session.execute(
                select(OverallQualityPrediction)
                .where(OverallQualityPrediction.grid_uuid == grid_uuid)
                .order_by(OverallQualityPrediction.gridsquare_uuid, OverallQualityPrediction.foilhole_uuid)
            )
        )
        .scalars()
        .all()
    )
    if not overall_preds:
        ids = (
            await session.execute(
                select(GridSquare.uuid, FoilHole.uuid)
                .where(GridSquare.uuid == FoilHole.gridsquare_uuid)
                .where(FoilHole.x_location != None)  # noqa: E711
                .where(GridSquare.uuid == grid_uuid)
                .order_by(GridSquare.uuid, FoilHole.uuid)
            )
        ).all()
        overall_preds = [
            OverallQualityPrediction(grid_uuid=grid_uuid, gridsquare_uuid=i[0], foilhole_uuid=i[1], value=float(v))
            for v, i in zip(results, ids, strict=True)
        ]
    else:
        for v, op in zip(results, overall_preds, strict=True):
            op.value = float(v)
    grid.prediction_updated_time = datetime.now()
    session.add_all(overall_preds)
    session.add(grid)
    await session.commit()
    return None
