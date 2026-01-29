import numpy as np
from sqlalchemy.dialects.postgresql import array_agg
from sqlmodel import Session, select

from smartem_backend.model.database import (
    OverallQualityPrediction,
)


def get_all_scores_for_grid(grid_uuid: str, session: Session) -> dict[str, tuple[str, float]]:
    overall_predictions = session.exec(
        select(
            OverallQualityPrediction.gridsquare_uuid,
            array_agg(OverallQualityPrediction.foilhole_uuid),
            array_agg(OverallQualityPrediction.value),
        )
        .where(OverallQualityPrediction.grid_uuid == grid_uuid)
        .group_by(OverallQualityPrediction.gridsquare_uuid)
    ).all()
    return {
        el[0]: sorted(zip(el[1], el[2], strict=False), key=lambda x: x[1], reverse=True) for el in overall_predictions
    }


def select_holes(foilhole_scores_square01: np.array, foilhole_scores_square02: np.array) -> tuple[int, int]:
    foilhole_scores01_restricted = foilhole_scores_square01[foilhole_scores_square01 >= 0]
    foilhole_scores02_restricted = foilhole_scores_square02[foilhole_scores_square02 >= 0]
    if not len(foilhole_scores01_restricted) + len(foilhole_scores02_restricted):
        return (len(foilhole_scores_square01), len(foilhole_scores_square02))
    expectation = int(np.sum(foilhole_scores01_restricted) + np.sum(foilhole_scores02_restricted)) or 1
    penalty = 10
    size_ordered_squares = (
        (foilhole_scores01_restricted, foilhole_scores02_restricted)
        if len(foilhole_scores01_restricted) >= len(foilhole_scores02_restricted)
        else (foilhole_scores02_restricted, foilhole_scores01_restricted)
    )
    num_on_second_square = (
        0
        if len(size_ordered_squares[0]) > expectation - penalty
        else expectation - penalty - len(size_ordered_squares[0])
    )
    num_skipped = 0 if len(size_ordered_squares[0]) <= expectation else len(size_ordered_squares[0]) - expectation
    comparisons = []
    skips = []
    seconds = []
    for _i in range(len(size_ordered_squares[0]) + len(size_ordered_squares[1]) + 1):
        if num_on_second_square > expectation or num_on_second_square > len(size_ordered_squares[1]):
            break
        comparisons.append(
            (np.sum(size_ordered_squares[0][:-num_skipped]) if num_skipped else np.sum(size_ordered_squares[0]))
            + np.sum(size_ordered_squares[1][:num_on_second_square])
        )
        skips.append(num_skipped)
        seconds.append(num_on_second_square)
        if num_skipped < len(size_ordered_squares[0]):
            num_skipped += 1
        if num_skipped > penalty:
            num_on_second_square += 1
        if len(comparisons) > 1:
            if num_skipped == len(size_ordered_squares[0]) and comparisons[-1] < comparisons[-2]:
                break
    best_index = np.argmax(comparisons)
    if len(size_ordered_squares[0]) <= 10:
        skips[best_index] = 0
    if len(size_ordered_squares[1]) <= 10:
        seconds[best_index] = len(size_ordered_squares[1])
    if len(foilhole_scores01_restricted) >= len(foilhole_scores02_restricted):
        return (len(size_ordered_squares[0]) - skips[best_index], seconds[best_index])
    return (seconds[best_index], len(size_ordered_squares[0]) - skips[best_index])


def _ordered_holes(square_scores_and_uuids: dict[str, tuple[str, float]]) -> list[str]:
    def _stitched_sort(names, scores):
        stitched_sort = sorted(
            zip(names, scores, strict=False),
            key=lambda x: np.sum(x[1][x[1] > 0]) if len(x[1][x[1] > 0]) > 0 else np.sum(x[1]),
            reverse=True,
        )
        return [s[0] for s in stitched_sort], [s[1] for s in stitched_sort]

    square_scores = {k: np.array([el[1] for el in v]) for k, v in square_scores_and_uuids.items()}
    hole_uuids = {k: [el[0] for el in v] for k, v in square_scores_and_uuids.items()}

    square_names = []
    square_score_list = []

    for k, v in square_scores.items():
        square_names.append(k)
        square_score_list.append(v)

    square_score_list = [2 * v - 1 for v in square_score_list]

    square_names, square_score_list = _stitched_sort(square_names, square_score_list)

    num_holes_collected = 0
    num_holes = np.sum([len(el) for el in square_score_list])
    square_counters = dict.fromkeys(square_names, 0)

    hole_order = []

    while num_holes_collected < num_holes:
        if len(square_score_list) == 1:
            num_holes_collected += len(square_score_list)
            hole_order.extend(hole_uuids[square_names[0]][square_counters[square_names[0]] :])
            square_counters[square_names[0]] = len(hole_uuids[square_names[0]])
            continue
        num_from_squares = select_holes(square_score_list[0], square_score_list[1])
        if num_from_squares[0] >= num_from_squares[1]:
            hole_order.extend(
                hole_uuids[square_names[0]][
                    square_counters[square_names[0]] : square_counters[square_names[0]] + num_from_squares[0]
                ]
            )
            square_counters[square_names[0]] += num_from_squares[0]
            num_holes_collected += num_from_squares[0]
            square_score_list[0] = square_score_list[0][num_from_squares[0] :]
            if not len(square_score_list[0]):
                square_score_list = square_score_list[1:]
                square_names = square_names[1:]
        else:
            hole_order.extend(
                hole_uuids[square_names[1]][
                    square_counters[square_names[1]] : square_counters[square_names[1]] + num_from_squares[1]
                ]
            )
            square_counters[square_names[1]] += num_from_squares[1]
            num_holes_collected += num_from_squares[1]
            square_score_list[1] = square_score_list[1][num_from_squares[1] :]
            if not len(square_score_list[1]):
                square_score_list = [square_score_list[0]] + square_score_list[2:]
                square_names = [square_names[0]] + square_names[2:]

        if not num_from_squares[0] and not num_from_squares[1]:
            continue
        square_names, square_score_list = _stitched_sort(square_names, square_score_list)

    return hole_order


def ordered_holes(grid_uuid: str, session: Session) -> list[str]:
    square_scores_and_uuids = get_all_scores_for_grid(grid_uuid, session)
    holes = _ordered_holes(square_scores_and_uuids)
    overall_predictions = session.exec(
        select(OverallQualityPrediction).where(OverallQualityPrediction.grid_uuid == grid_uuid)
    ).all()
    overall_prediction_map = {p.foilhole_uuid: p for p in overall_predictions}
    updated_predictions = []
    for i, h in enumerate(holes):
        pred = overall_prediction_map[h]
        pred.suggested_acquisition_index = i + 1
        updated_predictions.append(pred)
    session.add_all(updated_predictions)
    session.commit()
    return holes
