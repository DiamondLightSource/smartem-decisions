#!/usr/bin/env python

import argparse
import json
import logging
import signal
import sys
import time
import uuid
from collections.abc import Callable
from datetime import datetime
from typing import Any

import numpy as np
import pika
import scipy.stats
from dotenv import load_dotenv
from pydantic import ValidationError
from sqlmodel import Session, select

from smartem_backend.cli.initialise_prediction_model_weights import initialise_all_models_for_grid
from smartem_backend.cli.random_model_predictions import (
    generate_predictions_for_foilhole,
    generate_predictions_for_gridsquare,
)
from smartem_backend.cli.random_prior_updates import simulate_processing_pipeline_async
from smartem_backend.log_manager import LogConfig, LogManager
from smartem_backend.model.database import (
    AgentInstruction,
    AgentSession,
    CurrentQualityPrediction,
    FoilHole,
    GridSquare,
    Micrograph,
    QualityMetricStatistics,
    QualityPrediction,
    QualityPredictionModelParameter,
)
from smartem_backend.model.mq_event import (
    AcquisitionCreatedEvent,
    AcquisitionDeletedEvent,
    AcquisitionUpdatedEvent,
    AgentInstructionCreatedEvent,
    AgentInstructionExpiredEvent,
    AgentInstructionUpdatedEvent,
    AtlasCreatedEvent,
    AtlasDeletedEvent,
    AtlasUpdatedEvent,
    CtfCompleteBody,
    FoilHoleCreatedEvent,
    FoilHoleDeletedEvent,
    FoilHoleModelPredictionEvent,
    FoilHoleUpdatedEvent,
    GridCreatedEvent,
    GridDeletedEvent,
    GridRegisteredEvent,
    GridSquareCreatedEvent,
    GridSquareDeletedEvent,
    GridSquareModelPredictionEvent,
    GridSquareRegisteredEvent,
    GridSquareUpdatedEvent,
    GridUpdatedEvent,
    MessageQueueEventType,
    MicrographCreatedEvent,
    MicrographDeletedEvent,
    MicrographUpdatedEvent,
    ModelParameterUpdateEvent,
    MotionCorrectionCompleteBody,
    MultiFoilHoleModelPredictionEvent,
    RefreshPredictionsEvent,
)
from smartem_backend.mq_publisher import (
    publish_agent_instruction_created,
    publish_ctf_estimation_registered,
    publish_motion_correction_registered,
)
from smartem_backend.predictions.acquisition import ordered_holes
from smartem_backend.predictions.update import overall_predictions_update, prior_update
from smartem_backend.utils import get_db_engine, load_conf, rmq_consumer, setup_logger

load_dotenv(override=False)  # Don't override existing env vars as these might be coming from k8s
conf = load_conf()

# Initialize logger with default ERROR level (will be reconfigured in main())
log_manager = LogManager.get_instance("smartem_backend")
logger = log_manager.configure(LogConfig(level=logging.ERROR, console=True))

# Get singleton database engine for reuse across all event handlers
db_engine = get_db_engine()


def handle_acquisition_created(event_data: dict[str, Any]) -> None:
    """
    Handle acquisition created event by logging the event payload

    Args:
        event_data: Event data for acquisition created
    """
    try:
        event = AcquisitionCreatedEvent(**event_data)
        logger.info(f"Acquisition created event: {event.model_dump()}")

    except ValidationError as e:
        logger.error(f"Validation error processing acquisition created event: {e}")
    except Exception as e:
        logger.error(f"Error processing acquisition created event: {e}")


def handle_acquisition_updated(event_data: dict[str, Any]) -> None:
    """
    Handle acquisition updated event by logging the event payload

    Args:
        event_data: Event data for acquisition updated
    """
    try:
        event = AcquisitionUpdatedEvent(**event_data)
        logger.info(f"Acquisition updated event: {event.model_dump()}")

    except ValidationError as e:
        logger.error(f"Validation error processing acquisition updated event: {e}")
    except Exception as e:
        logger.error(f"Error processing acquisition updated event: {e}")


def handle_acquisition_deleted(event_data: dict[str, Any]) -> None:
    """
    Handle acquisition deleted event by logging the event payload

    Args:
        event_data: Event data for acquisition deleted
    """
    try:
        event = AcquisitionDeletedEvent(**event_data)
        logger.info(f"Acquisition deleted event: {event.model_dump()}")

    except ValidationError as e:
        logger.error(f"Validation error processing acquisition deleted event: {e}")
    except Exception as e:
        logger.error(f"Error processing acquisition deleted event: {e}")


def handle_atlas_created(event_data: dict[str, Any]) -> None:
    """
    Handle atlas created event by logging the event payload

    Args:
        event_data: Event data for atlas created
    """
    try:
        event = AtlasCreatedEvent(**event_data)
        logger.info(f"Atlas created event: {event.model_dump()}")

    except ValidationError as e:
        logger.error(f"Validation error processing atlas created event: {e}")
    except Exception as e:
        logger.error(f"Error processing atlas created event: {e}")


def handle_atlas_updated(event_data: dict[str, Any]) -> None:
    """
    Handle atlas updated event by logging the event payload

    Args:
        event_data: Event data for atlas updated
    """
    try:
        event = AtlasUpdatedEvent(**event_data)
        logger.info(f"Atlas updated event: {event.model_dump()}")

    except ValidationError as e:
        logger.error(f"Validation error processing atlas updated event: {e}")
    except Exception as e:
        logger.error(f"Error processing atlas updated event: {e}")


def handle_atlas_deleted(event_data: dict[str, Any]) -> None:
    """
    Handle atlas deleted event by logging the event payload

    Args:
        event_data: Event data for atlas deleted
    """
    try:
        event = AtlasDeletedEvent(**event_data)
        logger.info(f"Atlas deleted event: {event.model_dump()}")

    except ValidationError as e:
        logger.error(f"Validation error processing atlas deleted event: {e}")
    except Exception as e:
        logger.error(f"Error processing atlas deleted event: {e}")


def handle_grid_created(event_data: dict[str, Any], channel, delivery_tag) -> bool:
    """
    Handle grid created event by logging the event payload and initialising prediction model weights

    Args:
        event_data: Event data for grid created
        channel: RabbitMQ channel
        delivery_tag: Message delivery tag

    Returns:
        bool: True if successful, False if failed (already NACKed)
    """
    try:
        event = GridCreatedEvent(**event_data)
        logger.info(f"Grid created event: {event.model_dump()}")

        # Initialise prediction model weights for all available models
        try:
            initialise_all_models_for_grid(event.uuid, engine=db_engine)
            logger.info(f"Successfully initialised prediction model weights for grid {event.uuid}")
        except Exception as weight_init_error:
            logger.error(f"Failed to initialise prediction model weights for grid {event.uuid}: {weight_init_error}")
            # Don't fail the entire event processing if weight initialisation fails
            # This allows the grid creation to succeed even if weight initialisation has issues

        return True

    except ValidationError as e:
        logger.error(f"Validation error processing grid created event: {e}")
        channel.basic_nack(delivery_tag=delivery_tag, requeue=False)
        return False
    except Exception as e:
        logger.error(f"Error processing grid created event: {e}")
        channel.basic_nack(delivery_tag=delivery_tag, requeue=False)
        return False


def handle_grid_updated(event_data: dict[str, Any]) -> None:
    """
    Handle grid updated event by logging the event payload

    Args:
        event_data: Event data for grid updated
    """
    try:
        event = GridUpdatedEvent(**event_data)
        logger.info(f"Grid updated event: {event.model_dump()}")

    except ValidationError as e:
        logger.error(f"Validation error processing grid updated event: {e}")
    except Exception as e:
        logger.error(f"Error processing grid updated event: {e}")


def handle_grid_deleted(event_data: dict[str, Any]) -> None:
    """
    Handle grid deleted event by logging the event payload

    Args:
        event_data: Event data for grid deleted
    """
    try:
        event = GridDeletedEvent(**event_data)
        logger.info(f"Grid deleted event: {event.model_dump()}")

    except ValidationError as e:
        logger.error(f"Validation error processing grid deleted event: {e}")
    except Exception as e:
        logger.error(f"Error processing grid deleted event: {e}")


def handle_grid_registered(event_data: dict[str, Any]) -> None:
    """
    Handle grid registered event by logging the event payload

    Args:
        event_data: Event data for grid registered
    """
    try:
        event = GridRegisteredEvent(**event_data)
        logger.info(f"Grid registered event: {event.model_dump()}")

    except ValidationError as e:
        logger.error(f"Validation error processing grid registered event: {e}")
    except Exception as e:
        logger.error(f"Error processing grid registered event: {e}")


def handle_gridsquare_lowmag_created(event_data: dict[str, Any], channel, delivery_tag) -> bool:
    """
    Handle low mag gridsquare created event by logging the event payload and generating predictions

    Args:
        event_data: Event data for low mag gridsquare created
        channel: RabbitMQ channel
        delivery_tag: Message delivery tag

    Returns:
        bool: True if successful, False if failed (already NACKed)
    """
    try:
        event = GridSquareCreatedEvent(**event_data)
        logger.info(f"GridSquare low mag created event: {event.model_dump()}")
    except ValidationError as e:
        logger.error(f"Validation error processing gridsquare created event: {e}")
        channel.basic_nack(delivery_tag=delivery_tag, requeue=False)
        return False
    except Exception as e:
        logger.error(f"Error processing gridsquare created event: {e}")
        channel.basic_nack(delivery_tag=delivery_tag, requeue=False)
        return False
    return True


def handle_gridsquare_created(event_data: dict[str, Any], channel, delivery_tag) -> bool:
    """
    Handle gridsquare created event by logging the event payload and generating predictions

    Args:
        event_data: Event data for gridsquare created
        channel: RabbitMQ channel
        delivery_tag: Message delivery tag

    Returns:
        bool: True if successful, False if failed (already NACKed)
    """
    try:
        event = GridSquareCreatedEvent(**event_data)
        logger.info(f"GridSquare created event: {event.model_dump()}")

        # Generate random predictions for all available models
        try:
            generate_predictions_for_gridsquare(event.uuid, event.grid_uuid, engine=db_engine)
            logger.info(f"Successfully generated predictions for gridsquare {event.uuid}")
        except Exception as prediction_error:
            logger.error(f"Failed to generate predictions for gridsquare {event.uuid}: {prediction_error}")
            # Don't fail the entire event processing if prediction generation fails
            # This allows the gridsquare creation to succeed even if prediction generation has issues

        return True

    except ValidationError as e:
        logger.error(f"Validation error processing gridsquare created event: {e}")
        channel.basic_nack(delivery_tag=delivery_tag, requeue=False)
        return False
    except Exception as e:
        logger.error(f"Error processing gridsquare created event: {e}")
        channel.basic_nack(delivery_tag=delivery_tag, requeue=False)
        return False


def handle_gridsquare_lowmag_updated(event_data: dict[str, Any]) -> None:
    """
    Handle gridsquare low mag updated event by logging the event payload

    Args:
        event_data: Event data for low mag gridsquare updated
    """
    try:
        event = GridSquareUpdatedEvent(**event_data)
        logger.info(f"GridSquare low mag updated event: {event.model_dump()}")

    except ValidationError as e:
        logger.error(f"Validation error processing gridsquare low mag updated event: {e}")
    except Exception as e:
        logger.error(f"Error processing gridsquare low mag updated event: {e}")


def handle_gridsquare_updated(event_data: dict[str, Any]) -> None:
    """
    Handle gridsquare updated event by logging the event payload

    Args:
        event_data: Event data for gridsquare updated
    """
    try:
        event = GridSquareUpdatedEvent(**event_data)
        logger.info(f"GridSquare updated event: {event.model_dump()}")

    except ValidationError as e:
        logger.error(f"Validation error processing gridsquare updated event: {e}")
    except Exception as e:
        logger.error(f"Error processing gridsquare updated event: {e}")


def handle_gridsquare_lowmag_deleted(event_data: dict[str, Any]) -> None:
    """
    Handle low mag gridsquare deleted event by logging the event payload

    Args:
        event_data: Event data for low mag gridsquare deleted
    """
    try:
        event = GridSquareDeletedEvent(**event_data)
        logger.info(f"GridSquare low mag deleted event: {event.model_dump()}")

    except ValidationError as e:
        logger.error(f"Validation error processing low mag gridsquare deleted event: {e}")
    except Exception as e:
        logger.error(f"Error processing low mag gridsquare deleted event: {e}")


def handle_gridsquare_deleted(event_data: dict[str, Any]) -> None:
    """
    Handle gridsquare deleted event by logging the event payload

    Args:
        event_data: Event data for gridsquare deleted
    """
    try:
        event = GridSquareDeletedEvent(**event_data)
        logger.info(f"GridSquare deleted event: {event.model_dump()}")

    except ValidationError as e:
        logger.error(f"Validation error processing gridsquare deleted event: {e}")
    except Exception as e:
        logger.error(f"Error processing gridsquare deleted event: {e}")


def handle_gridsquare_registered(event_data: dict[str, Any]) -> None:
    """
    Handle grid square registered event by logging the event payload

    Args:
        event_data: Event data for grid square registered
    """
    try:
        event = GridSquareRegisteredEvent(**event_data)
        logger.info(f"Grid square registered event: {event.model_dump()}")

    except ValidationError as e:
        logger.error(f"Validation error processing grid square registered event: {e}")
    except Exception as e:
        logger.error(f"Error processing grid square registered event: {e}")


def handle_foilhole_created(event_data: dict[str, Any], channel, delivery_tag) -> bool:
    """
    Handle foilhole created event by logging the event payload and generating predictions

    Args:
        event_data: Event data for foilhole created
        channel: RabbitMQ channel
        delivery_tag: Message delivery tag

    Returns:
        bool: True if successful, False if failed (already NACKed)
    """
    try:
        event = FoilHoleCreatedEvent(**event_data)
        logger.info(f"FoilHole created event: {event.model_dump()}")

        # Generate random predictions for all available models
        try:
            generate_predictions_for_foilhole(event.uuid, event.gridsquare_uuid, engine=db_engine)
            logger.info(f"Successfully generated predictions for foilhole {event.uuid}")
        except Exception as prediction_error:
            logger.error(f"Failed to generate predictions for foilhole {event.uuid}: {prediction_error}")
            # Don't fail the entire event processing if prediction generation fails
            # This allows the foilhole creation to succeed even if prediction generation has issues

        return True

    except ValidationError as e:
        logger.error(f"Validation error processing foilhole created event: {e}")
        channel.basic_nack(delivery_tag=delivery_tag, requeue=False)
        return False
    except Exception as e:
        logger.error(f"Error processing foilhole created event: {e}")
        channel.basic_nack(delivery_tag=delivery_tag, requeue=False)
        return False


def handle_foilhole_updated(event_data: dict[str, Any]) -> None:
    """
    Handle foilhole updated event by logging the event payload

    Args:
        event_data: Event data for foilhole updated
    """
    try:
        event = FoilHoleUpdatedEvent(**event_data)
        logger.info(f"FoilHole updated event: {event.model_dump()}")

    except ValidationError as e:
        logger.error(f"Validation error processing foilhole updated event: {e}")
    except Exception as e:
        logger.error(f"Error processing foilhole updated event: {e}")


def handle_foilhole_deleted(event_data: dict[str, Any]) -> None:
    """
    Handle foilhole deleted event by logging the event payload

    Args:
        event_data: Event data for foilhole deleted
    """
    try:
        event = FoilHoleDeletedEvent(**event_data)
        logger.info(f"FoilHole deleted event: {event.model_dump()}")

    except ValidationError as e:
        logger.error(f"Validation error processing foilhole deleted event: {e}")
    except Exception as e:
        logger.error(f"Error processing foilhole deleted event: {e}")


def handle_micrograph_created(event_data: dict[str, Any], channel, delivery_tag) -> bool:
    """
    Handle micrograph created event by logging the event payload and starting processing simulation

    Args:
        event_data: Event data for micrograph created
        channel: RabbitMQ channel
        delivery_tag: Message delivery tag

    Returns:
        bool: True if successful, False if failed (already NACKed)
    """
    try:
        event = MicrographCreatedEvent(**event_data)
        logger.info(f"Micrograph created event: {event.model_dump()}")

        # Start simulated processing pipeline in background
        try:
            simulate_processing_pipeline_async(event.uuid, engine=db_engine)
            logger.info(f"Started processing pipeline simulation for micrograph {event.uuid}")
        except Exception as simulation_error:
            logger.error(f"Failed to start processing simulation for micrograph {event.uuid}: {simulation_error}")
            # Don't fail the entire event processing if simulation startup fails
            # This allows the micrograph creation to succeed even if simulation has issues

        return True

    except ValidationError as e:
        logger.error(f"Validation error processing micrograph created event: {e}")
        channel.basic_nack(delivery_tag=delivery_tag, requeue=False)
        return False
    except Exception as e:
        logger.error(f"Error processing micrograph created event: {e}")
        channel.basic_nack(delivery_tag=delivery_tag, requeue=False)
        return False


def handle_micrograph_updated(event_data: dict[str, Any]) -> None:
    """
    Handle micrograph updated event by logging the event payload

    Args:
        event_data: Event data for micrograph updated
    """
    try:
        event = MicrographUpdatedEvent(**event_data)
        logger.info(f"Micrograph updated event: {event.model_dump()}")

    except ValidationError as e:
        logger.error(f"Validation error processing micrograph updated event: {e}")
    except Exception as e:
        logger.error(f"Error processing micrograph updated event: {e}")


def handle_micrograph_deleted(event_data: dict[str, Any]) -> None:
    """
    Handle micrograph deleted event by logging the event payload

    Args:
        event_data: Event data for micrograph deleted
    """
    try:
        event = MicrographDeletedEvent(**event_data)
        logger.info(f"Micrograph deleted event: {event.model_dump()}")

    except ValidationError as e:
        logger.error(f"Validation error processing micrograph deleted event: {e}")
    except Exception as e:
        logger.error(f"Error processing micrograph deleted event: {e}")


def _check_against_statistics(
    metric_name: str,
    micrograph_uuid: str,
    comparison_value: float,
    larger_better: bool = False,
) -> float:
    with Session(db_engine) as session:
        grid_uuid = (
            session.exec(
                select(GridSquare, FoilHole, Micrograph)
                .where(GridSquare.uuid == FoilHole.gridsquare_uuid)
                .where(FoilHole.uuid == Micrograph.foilhole_uuid)
                .where(Micrograph.uuid == micrograph_uuid)
            )
            .one()[0]
            .grid_uuid
        )
        metric_stats = session.exec(
            select(QualityMetricStatistics)
            .where(QualityMetricStatistics.grid_uuid == grid_uuid)
            .where(QualityMetricStatistics.name == metric_name)
        ).all()
    if not metric_stats:
        return 1
    elif metric_stats[0].count < 2:
        if comparison_value == metric_stats[0].value_sum / metric_stats[0].count:
            return 0.5
        elif comparison_value > metric_stats[0].value_sum / metric_stats[0].count:
            return 1 if larger_better else 0
        else:
            return 0 if larger_better else 1
    else:
        metric_mean = metric_stats[0].value_sum / metric_stats[0].count
        metric_var = metric_stats[0].squared_value_sum / (metric_stats[0].count - 1)
        cdf_value = float(scipy.stats.norm(metric_mean, np.sqrt(metric_var)).cdf(comparison_value))
        return cdf_value if larger_better else 1 - cdf_value


def handle_motion_correction_complete(event_data: dict[str, Any]) -> None:
    try:
        event = MotionCorrectionCompleteBody(**event_data)
        quality = _check_against_statistics("motioncorrection", event.micrograph_uuid, event.total_motion)
        with Session(db_engine) as session:
            grid_uuid = (
                session.exec(
                    select(GridSquare, FoilHole, Micrograph)
                    .where(GridSquare.uuid == FoilHole.gridsquare_uuid)
                    .where(FoilHole.uuid == Micrograph.foilhole_uuid)
                    .where(Micrograph.uuid == event.micrograph_uuid)
                )
                .one()[0]
                .grid_uuid
            )
            metric_stats = session.exec(
                select(QualityMetricStatistics)
                .where(QualityMetricStatistics.grid_uuid == grid_uuid)
                .where(QualityMetricStatistics.name == "motioncorrection")
            ).all()
            if not metric_stats:
                updated_metric_stats = QualityMetricStatistics(
                    grid_uuid=grid_uuid,
                    name="motioncorrection",
                    count=1,
                    value_sum=event.total_motion,
                    squared_value_sum=0,
                )
            else:
                updated_metric_stats = metric_stats[0]
                old_diff = event.total_motion - (updated_metric_stats.value_sum / updated_metric_stats.count)
                updated_metric_stats.count += 1
                updated_metric_stats.value_sum += event.total_motion
                updated_metric_stats.squared_value_sum += old_diff * (
                    event.total_motion - (updated_metric_stats.value_sum / updated_metric_stats.count)
                )
            session.add(updated_metric_stats)
            session.commit()
            prior_update(quality, event.micrograph_uuid, "motioncorrection", session)
        publish_motion_correction_registered(event.micrograph_uuid, quality >= 0.5, metric_name="motioncorrection")
    except ValidationError as e:
        logger.error(f"Validation error processing motion correction event: {e}")
    except Exception as e:
        logger.error(f"Error processing motion correction event: {e}")
    return None


def handle_ctf_estimation_complete(event_data: dict[str, Any]) -> None:
    try:
        event = CtfCompleteBody(**event_data)
        quality = _check_against_statistics(
            "ctfmaxresolution", event.micrograph_uuid, event.ctf_max_resolution_estimate
        )
        with Session(db_engine) as session:
            grid_uuid = (
                session.exec(
                    select(GridSquare, FoilHole, Micrograph)
                    .where(GridSquare.uuid == FoilHole.gridsquare_uuid)
                    .where(FoilHole.uuid == Micrograph.foilhole_uuid)
                    .where(Micrograph.uuid == event.micrograph_uuid)
                )
                .one()[0]
                .grid_uuid
            )
            metric_stats = session.exec(
                select(QualityMetricStatistics)
                .where(QualityMetricStatistics.grid_uuid == grid_uuid)
                .where(QualityMetricStatistics.name == "ctfmaxresolution")
            ).all()
            if not metric_stats:
                updated_metric_stats = QualityMetricStatistics(
                    grid_uuid=grid_uuid,
                    name="ctfmaxresolution",
                    count=1,
                    value_sum=event.ctf_max_resolution_estimate,
                    squared_value_sum=0,
                )
            else:
                updated_metric_stats = metric_stats[0]
                old_diff = event.ctf_max_resolution_estimate - (
                    updated_metric_stats.value_sum / updated_metric_stats.count
                )
                updated_metric_stats.count += 1
                updated_metric_stats.value_sum += event.ctf_max_resolution_estimate
                updated_metric_stats.squared_value_sum += old_diff * (
                    event.ctf_max_resolution_estimate - (updated_metric_stats.value_sum / updated_metric_stats.count)
                )
            session.add(updated_metric_stats)
            session.commit()
            prior_update(quality, event.micrograph_uuid, "ctfmaxresolution", session)
        publish_ctf_estimation_registered(event.micrograph_uuid, quality >= 0.5, metric_name="ctfmaxresolution")
    except ValidationError as e:
        logger.error(f"Validation error processing ctf event: {e}")
    except Exception as e:
        logger.error(f"Error processing ctf event: {e}")
    return None


def handle_gridsquare_model_prediction(event_data: dict[str, Any]) -> None:
    """
    Handle grid square model prediction event by inserting the result into the database

    Args:
        event_data: Event data for grid square model prediction
    """
    try:
        event = GridSquareModelPredictionEvent(**event_data)
        quality_prediction = QualityPrediction(
            gridsquare_uuid=event.gridsquare_uuid,
            prediction_model_name=event.prediction_model_name,
            value=event.prediction_value,
            metric_name=event.metric,
        )
        with Session(db_engine) as session:
            session.add(quality_prediction)
            current_quality_prediction = session.exec(
                select(CurrentQualityPrediction)
                .where(CurrentQualityPrediction.gridsquare_uuid == event.gridsquare_uuid)
                .where(CurrentQualityPrediction.prediction_model_name == event.prediction_model_name)
                .where(CurrentQualityPrediction.metric_name == event.metric)
            ).first()
            if current_quality_prediction is None:
                grid_uuid = (
                    session.exec(select(GridSquare).where(GridSquare.uuid == event.gridsquare_uuid)).one().grid_uuid
                )
                current_quality_prediction = CurrentQualityPrediction(
                    grid_uuid=grid_uuid,
                    gridsquare_uuid=event.gridsquare_uuid,
                    prediction_model_name=event.prediction_model_name,
                    value=event.prediction_value,
                    metric_name=event.metric,
                )
            else:
                current_quality_prediction.value = event.prediction_value
            session.add(current_quality_prediction)
            session.commit()

    except ValidationError as e:
        logger.error(f"Validation error processing grid square model prediction event: {e}")
    except Exception as e:
        logger.error(f"Error processing grid square model prediction event: {e}")


def handle_foilhole_model_prediction(event_data: dict[str, Any]) -> None:
    """
    Handle foil hole model prediction event by inserting the result into the database

    Args:
        event_data: Event data for foil hole model prediction
    """
    try:
        event = FoilHoleModelPredictionEvent(**event_data)
        quality_prediction = QualityPrediction(
            foilhole_uuid=event.foilhole_uuid,
            prediction_model_name=event.prediction_model_name,
            value=event.prediction_value,
            metric_name=event.metric,
        )
        with Session(db_engine) as session:
            session.add(quality_prediction)
            current_quality_prediction = session.exec(
                select(CurrentQualityPrediction)
                .where(CurrentQualityPrediction.foilhole_uuid == event.foilhole_uuid)
                .where(CurrentQualityPrediction.prediction_model_name == event.prediction_model_name)
                .where(CurrentQualityPrediction.metric_name == event.metric)
            ).first()
            if current_quality_prediction is None:
                square = session.exec(
                    select(GridSquare, FoilHole)
                    .where(GridSquare.uuid == FoilHole.gridsquare_uuid)
                    .where(FoilHole.uuid == event.foilhole_uuid)
                ).one()[0]
                current_quality_prediction = CurrentQualityPrediction(
                    grid_uuid=square.grid_uuid,
                    gridsquare_uuid=square.uuid,
                    foilhole_uuid=event.foilhole_uuid,
                    prediction_model_name=event.prediction_model_name,
                    value=event.prediction_value,
                    metric_name=event.metric,
                )
            else:
                current_quality_prediction.value = event.prediction_value
            session.add(current_quality_prediction)
            session.commit()

    except ValidationError as e:
        logger.error(f"Validation error processing foil hole model prediction event: {e}")
    except Exception as e:
        logger.error(f"Error processing foil hole model prediction event: {e}")


def handle_multi_foilhole_model_prediction(event_data: dict[str, Any]) -> None:
    """
    Handle multiple foil hole model predictions event by inserting the result into the database

    Args:
        event_data: Event data for foil hole model predictions
    """
    try:
        event = MultiFoilHoleModelPredictionEvent(**event_data)
        quality_predictions = [
            QualityPrediction(
                foilhole_uuid=fhuuid,
                prediction_model_name=event.prediction_model_name,
                value=event.prediction_value,
                metric_name=event.metric,
            )
            for fhuuid in event.foilhole_uuids
        ]
        with Session(db_engine) as session:
            session.add_all(quality_predictions)
            current_quality_predictions = session.exec(
                select(CurrentQualityPrediction)
                .where(CurrentQualityPrediction.foilhole_uuid.in_(event.foilhole_uuids))
                .where(CurrentQualityPrediction.prediction_model_name == event.prediction_model_name)
                .where(CurrentQualityPrediction.metric_name == event.metric)
            ).all()
            if not current_quality_predictions:
                squares = session.exec(
                    select(GridSquare, FoilHole)
                    .where(GridSquare.uuid == FoilHole.gridsquare_uuid)
                    .where(FoilHole.uuid.in_(event.foilhole_uuids))
                ).all()
                square_lookup = {s[1].uuid: s[0] for s in squares}
                current_quality_predictions = [
                    CurrentQualityPrediction(
                        grid_uuid=square_lookup[fhuuid].grid_uuid,
                        gridsquare_uuid=square_lookup[fhuuid].uuid,
                        foilhole_uuid=fhuuid,
                        prediction_model_name=event.prediction_model_name,
                        value=event.prediction_value,
                        metric_name=event.metric,
                    )
                    for fhuuid in event.foilhole_uuids
                ]
            else:
                for pred in current_quality_predictions:
                    pred.value = event.prediction_value
            session.add_all(current_quality_predictions)
            session.commit()

    except ValidationError as e:
        logger.error(f"Validation error processing multiple foil hole model prediction event: {e}")
    except Exception as e:
        logger.error(f"Error processing multiple foil hole model prediction event: {e}")


def handle_refresh_predictions(event_data: dict[str, Any]) -> None:
    """
    Handle refresh predictions event by calculating the updated values

    Args:
        event_data: Event data for refresh predictions event

    """
    try:
        event = RefreshPredictionsEvent(**event_data)
        with Session(db_engine) as session:
            overall_predictions_update(event.grid_uuid, session)
            ordered_holes(event.grid_uuid, session)

    except ValidationError as e:
        logger.error(f"Validation error processing refresh predictions event: {e}")
    except Exception as e:
        logger.error(f"Error processing refresh predictions event: {e}")


def handle_model_parameter_update(event_data: dict[str, Any]) -> None:
    """
    Handle model parameter update event by inserting the result into the database

    Args:
        event_data: Event data for model parameter update
    """
    try:
        event = ModelParameterUpdateEvent(**event_data)
        model_parameter = QualityPredictionModelParameter(
            grid_uuid=event.grid_uuid,
            prediction_model_name=event.prediction_model_name,
            key=event.key,
            value=event.value,
            metric_name=event.metric,
            group=event.group,
        )
        with Session(db_engine) as session:
            session.add(model_parameter)
            session.commit()

    except ValidationError as e:
        logger.error(f"Validation error processing model parameter update event: {e}")
    except Exception as e:
        logger.error(f"Error processing model parameter update event: {e}")


# ============ External Message Processing Events ============


def handle_external_gridsquare_model_prediction(event_data: dict[str, Any]) -> None:
    """
    Handle external grid square model prediction event by generating agent instructions

    Args:
        event_data: External event data with payload containing prediction results
    """
    try:
        payload = event_data.get("payload", {})
        gridsquare_id = payload.get("gridsquare_id")
        quality_score = payload.get("prediction_results", {}).get("quality_score", 0.0)

        logger.info(f"External gridsquare prediction: {gridsquare_id} with quality {quality_score}")

        # Decision logic based on quality score
        if quality_score >= 0.8:
            # High quality - instruct to reorder this gridsquare to priority
            instruction_type = "microscope.control.reorder_gridsquares"
            instruction_payload = {
                "gridsquare_ids": [gridsquare_id],
                "priority": "high",
                "reason": f"High quality prediction: {quality_score:.3f}",
            }
        elif quality_score <= 0.3:
            # Low quality - instruct to skip this gridsquare
            instruction_type = "microscope.control.skip_gridsquares"
            instruction_payload = {
                "gridsquare_ids": [gridsquare_id],
                "reason": f"Low quality prediction: {quality_score:.3f}",
            }
        else:
            # Medium quality - no specific action needed
            logger.info(f"Medium quality gridsquare {gridsquare_id} ({quality_score:.3f}) - no action needed")
            return

        # Generate instruction for all active agent sessions
        active_sessions = get_active_agent_sessions()
        for session in active_sessions:
            instruction_id = str(uuid.uuid4())

            success = publish_agent_instruction_created(
                instruction_id=instruction_id,
                session_id=session.session_id,
                agent_id=session.agent_id,
                instruction_type=instruction_type,
                payload=instruction_payload,
                priority="normal",
            )

            if success:
                logger.info(f"Generated instruction {instruction_id} for agent {session.agent_id}")
            else:
                logger.error(f"Failed to generate instruction for agent {session.agent_id}")

    except Exception as e:
        logger.error(f"Error processing external gridsquare model prediction: {e}")


def handle_external_foilhole_model_prediction(event_data: dict[str, Any]) -> None:
    """
    Handle external foilhole model prediction event by generating agent instructions

    Args:
        event_data: External event data with payload containing prediction results
    """
    try:
        payload = event_data.get("payload", {})
        gridsquare_id = payload.get("gridsquare_id")
        foilholes = payload.get("foilhole_predictions", [])

        # Count high quality foilholes
        high_quality_foilholes = [fh for fh in foilholes if fh.get("quality_score", 0) >= 0.8]

        if len(high_quality_foilholes) > 0:
            # Instruct to reorder high quality foilholes
            instruction_type = "microscope.control.reorder_foilholes"
            instruction_payload = {
                "gridsquare_id": gridsquare_id,
                "foilhole_ids": [fh["foilhole_id"] for fh in high_quality_foilholes],
                "priority": "high",
                "reason": f"Found {len(high_quality_foilholes)} high quality foilholes",
            }

            # Generate instruction for all active agent sessions
            active_sessions = get_active_agent_sessions()
            for session in active_sessions:
                instruction_id = str(uuid.uuid4())

                success = publish_agent_instruction_created(
                    instruction_id=instruction_id,
                    session_id=session.session_id,
                    agent_id=session.agent_id,
                    instruction_type=instruction_type,
                    payload=instruction_payload,
                    priority="normal",
                )

                if success:
                    logger.info(f"Generated foilhole reorder instruction {instruction_id} for agent {session.agent_id}")
                else:
                    logger.error(f"Failed to generate foilhole instruction for agent {session.agent_id}")
        else:
            logger.info(f"No high quality foilholes found for gridsquare {gridsquare_id}")

    except Exception as e:
        logger.error(f"Error processing external foilhole model prediction: {e}")


def get_active_agent_sessions():
    """Get all currently active agent sessions"""
    with Session(db_engine) as session:
        # Find sessions that are active (have recent connections)
        return session.query(AgentSession).filter(AgentSession.status == "active").all()


def handle_gridsquare_model_prediction_router(event_data: dict[str, Any]) -> None:
    """Route gridsquare model prediction events based on source"""
    source = event_data.get("source", "")
    if source == "external_simulator":
        handle_external_gridsquare_model_prediction(event_data)
    else:
        handle_gridsquare_model_prediction(event_data)


def handle_foilhole_model_prediction_router(event_data: dict[str, Any]) -> None:
    """Route foilhole model prediction events based on source"""
    source = event_data.get("source", "")
    if source == "external_simulator":
        handle_external_foilhole_model_prediction(event_data)
    else:
        handle_foilhole_model_prediction(event_data)


# ============ Agent Communication Events ============


def handle_agent_instruction_created(event_data: dict[str, Any]) -> None:
    """
    Handle agent instruction created event by persisting the instruction to the database

    Args:
        event_data: Event data for agent instruction created
    """
    try:
        event = AgentInstructionCreatedEvent(**event_data)
        logger.info(f"Agent instruction created event: {event.model_dump()}")

        # Persist instruction to database
        with Session(db_engine) as session:
            # Verify the session exists
            session_obj = session.query(AgentSession).filter(AgentSession.session_id == event.session_id).first()
            if not session_obj:
                logger.warning(f"Session {event.session_id} not found for instruction {event.instruction_id}")
                return

            instruction = AgentInstruction(
                instruction_id=event.instruction_id,
                session_id=event.session_id,
                agent_id=event.agent_id,
                instruction_type=event.instruction_type,
                payload=event.payload,
                sequence_number=event.sequence_number,
                priority=event.priority,
                status="pending",
                created_at=datetime.now(),
                expires_at=event.expires_at,
                instruction_metadata=event.instruction_metadata or {},
            )
            session.add(instruction)
            session.commit()

        logger.info(f"Successfully persisted instruction {event.instruction_id} to database")

    except ValidationError as e:
        logger.error(f"Validation error processing agent instruction created event: {e}")
    except Exception as e:
        logger.error(f"Error processing agent instruction created event: {e}")


def handle_agent_instruction_updated(event_data: dict[str, Any]) -> None:
    """
    Handle agent instruction updated event by updating the instruction status

    Args:
        event_data: Event data for agent instruction updated
    """
    try:
        event = AgentInstructionUpdatedEvent(**event_data)
        logger.info(f"Agent instruction updated event: {event.model_dump()}")

        # Update instruction status in database
        with Session(db_engine) as session:
            instruction = (
                session.query(AgentInstruction).filter(AgentInstruction.instruction_id == event.instruction_id).first()
            )
            if instruction:
                instruction.status = event.status
                if event.acknowledged_at:
                    instruction.acknowledged_at = event.acknowledged_at
                session.commit()
                logger.info(f"Updated instruction {event.instruction_id} status to {event.status}")
            else:
                logger.warning(f"Instruction {event.instruction_id} not found for status update")

    except ValidationError as e:
        logger.error(f"Validation error processing agent instruction updated event: {e}")
    except Exception as e:
        logger.error(f"Error processing agent instruction updated event: {e}")


def handle_agent_instruction_expired(event_data: dict[str, Any]) -> None:
    """
    Handle agent instruction expired event by updating retry logic and status

    Args:
        event_data: Event data for agent instruction expired
    """
    try:
        event = AgentInstructionExpiredEvent(**event_data)
        logger.info(f"Agent instruction expired event: {event.model_dump()}")

        # Update instruction status in database
        with Session(db_engine) as session:
            instruction = (
                session.query(AgentInstruction).filter(AgentInstruction.instruction_id == event.instruction_id).first()
            )
            if instruction:
                if event.retry_count >= instruction.max_retries:
                    # Mark as failed after max retries
                    instruction.status = "expired"
                    logger.info(
                        f"Instruction {event.instruction_id} marked as expired after {event.retry_count} retries"
                    )
                else:
                    # Reset to pending for retry
                    instruction.status = "pending"
                    instruction.retry_count = event.retry_count
                    logger.info(f"Instruction {event.instruction_id} reset for retry ({event.retry_count})")

                session.commit()
            else:
                logger.warning(f"Instruction {event.instruction_id} not found for expiry handling")

    except ValidationError as e:
        logger.error(f"Validation error processing agent instruction expired event: {e}")
    except Exception as e:
        logger.error(f"Error processing agent instruction expired event: {e}")


# Create a mapping from event types to their handler functions
def get_event_handlers() -> dict[str, Callable]:
    """
    Get a mapping of event types to their handler functions

    Returns:
        Dict[str, Callable]: Mapping of event type strings to handler functions
    """
    return {
        MessageQueueEventType.ACQUISITION_CREATED.value: handle_acquisition_created,
        MessageQueueEventType.ACQUISITION_UPDATED.value: handle_acquisition_updated,
        MessageQueueEventType.ACQUISITION_DELETED.value: handle_acquisition_deleted,
        MessageQueueEventType.ATLAS_CREATED.value: handle_atlas_created,
        MessageQueueEventType.ATLAS_UPDATED.value: handle_atlas_updated,
        MessageQueueEventType.ATLAS_DELETED.value: handle_atlas_deleted,
        MessageQueueEventType.GRID_CREATED.value: handle_grid_created,
        MessageQueueEventType.GRID_UPDATED.value: handle_grid_updated,
        MessageQueueEventType.GRID_DELETED.value: handle_grid_deleted,
        MessageQueueEventType.GRIDSQUARE_CREATED.value: handle_gridsquare_created,
        MessageQueueEventType.GRIDSQUARE_UPDATED.value: handle_gridsquare_updated,
        MessageQueueEventType.GRIDSQUARE_DELETED.value: handle_gridsquare_deleted,
        MessageQueueEventType.GRIDSQUARE_LOWMAG_CREATED.value: handle_gridsquare_lowmag_created,
        MessageQueueEventType.GRIDSQUARE_LOWMAG_UPDATED.value: handle_gridsquare_lowmag_updated,
        MessageQueueEventType.GRIDSQUARE_LOWMAG_DELETED.value: handle_gridsquare_lowmag_deleted,
        MessageQueueEventType.FOILHOLE_CREATED.value: handle_foilhole_created,
        MessageQueueEventType.FOILHOLE_UPDATED.value: handle_foilhole_updated,
        MessageQueueEventType.FOILHOLE_DELETED.value: handle_foilhole_deleted,
        MessageQueueEventType.MICROGRAPH_CREATED.value: handle_micrograph_created,
        MessageQueueEventType.MICROGRAPH_UPDATED.value: handle_micrograph_updated,
        MessageQueueEventType.MICROGRAPH_DELETED.value: handle_micrograph_deleted,
        MessageQueueEventType.AGENT_INSTRUCTION_CREATED.value: handle_agent_instruction_created,
        MessageQueueEventType.AGENT_INSTRUCTION_UPDATED.value: handle_agent_instruction_updated,
        MessageQueueEventType.AGENT_INSTRUCTION_EXPIRED.value: handle_agent_instruction_expired,
        MessageQueueEventType.MOTION_CORRECTION_COMPLETE.value: handle_motion_correction_complete,
        MessageQueueEventType.CTF_COMPLETE.value: handle_ctf_estimation_complete,
        MessageQueueEventType.GRIDSQUARE_MODEL_PREDICTION.value: handle_gridsquare_model_prediction,
        MessageQueueEventType.FOILHOLE_MODEL_PREDICTION.value: handle_foilhole_model_prediction,
        MessageQueueEventType.MULTI_FOILHOLE_MODEL_PREDICTION.value: handle_multi_foilhole_model_prediction,
        MessageQueueEventType.MODEL_PARAMETER_UPDATE.value: handle_model_parameter_update,
        MessageQueueEventType.REFRESH_PREDICTIONS.value: handle_refresh_predictions,
        # TODO: Add handlers for all other event types as needed
    }


def on_message(ch, method, properties, body):
    """
    Callback function for processing RabbitMQ messages

    Args:
        ch: Channel object
        method: Method object
        properties: Properties object
        body: Message body
    """
    # Get retry count from message headers only once
    retry_count = 0
    if properties.headers and "x-retry-count" in properties.headers:
        retry_count = properties.headers["x-retry-count"]

    # Default event_type
    event_type = "unknown"

    try:
        message = json.loads(body.decode())
        logger.info(f"Received message: {message}")

        if "event_type" not in message:
            logger.warning(f"Message missing 'event_type' field: {message}")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
            return

        event_type = message["event_type"]

        event_handlers = get_event_handlers()
        if event_type not in event_handlers:
            logger.warning(f"No handler registered for event type: {event_type}")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
            return

        handler = event_handlers[event_type]

        # For handlers that support the new signature (channel and delivery_tag)
        if event_type in [
            MessageQueueEventType.GRID_CREATED.value,
            MessageQueueEventType.FOILHOLE_CREATED.value,
            MessageQueueEventType.GRIDSQUARE_CREATED.value,
            MessageQueueEventType.GRIDSQUARE_LOWMAG_CREATED.value,
            MessageQueueEventType.MICROGRAPH_CREATED.value,
        ]:
            success = handler(message, ch, method.delivery_tag)
            if success:
                ch.basic_ack(delivery_tag=method.delivery_tag)
            # Handler will have already NACKed if it failed
        else:
            # Simple handlers - just call them and ACK
            handler(message)
            ch.basic_ack(delivery_tag=method.delivery_tag)
        logger.debug(f"Successfully processed {event_type} event")

    except json.JSONDecodeError:
        logger.error(f"Failed to decode JSON message: {body.decode()}")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

    except Exception as e:
        logger.error(f"Error processing message: {e}")

        if retry_count >= 3:
            logger.warning(f"Message failed after {retry_count} retries, dropping message")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        else:
            # Republish with incremented retry count
            headers = properties.headers or {}
            headers["x-retry-count"] = retry_count + 1

            logger.debug(f"Republishing message with retry count {retry_count + 1}, event_type: {event_type}")

            try:
                ch.basic_publish(
                    exchange="",
                    routing_key=method.routing_key,
                    body=body,
                    properties=pika.BasicProperties(headers=headers),
                )
                ch.basic_ack(delivery_tag=method.delivery_tag)
            except Exception as republish_error:
                logger.error(f"Failed to republish message: {republish_error}")
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)


def signal_handler(signum, frame):
    """Handle shutdown signals"""
    logger.info("Received shutdown signal, stopping consumer...")
    rmq_consumer.stop_consuming()
    rmq_consumer.close()
    sys.exit(0)


def main():
    """Main function to run the consumer"""
    parser = argparse.ArgumentParser(description="SmartEM Decisions MQ Consumer")
    parser.add_argument(
        "-v", "--verbose", action="count", default=0, help="Increase verbosity (-v for INFO, -vv for DEBUG)"
    )
    args = parser.parse_args()

    # Configure logging based on verbosity level
    if args.verbose >= 2:  # Debug level -vv
        log_level = logging.DEBUG
    elif args.verbose == 1:  # Info level -v
        log_level = logging.INFO
    else:  # Default - only errors
        log_level = logging.ERROR

    # Reconfigure logger with the specified verbosity level
    global logger
    logger = setup_logger(level=log_level, conf=conf)

    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    while True:
        try:
            logger.info("Starting RabbitMQ consumer...")
            rmq_consumer.consume(on_message, prefetch_count=1)
        except KeyboardInterrupt:
            logger.info("Consumer stopped by user")
            break
        except Exception as e:
            logger.error(f"Error in consumer: {e}")
            logger.info("Retrying in 10 seconds...")
            time.sleep(10)

    rmq_consumer.close()


if __name__ == "__main__":
    main()
