#!/usr/bin/env python

import argparse
import asyncio
import json
import logging
import os
import signal
import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Any

import numpy as np
import scipy.stats
from aio_pika.abc import AbstractIncomingMessage
from dotenv import load_dotenv
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from sqlmodel import select

from smartem_backend import mq_publisher as mq_publisher_module
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
    CurrentQualityGroupPrediction,
    CurrentQualityPrediction,
    FoilHole,
    FoilHoleGroup,
    FoilHoleGroupMembership,
    GridSquare,
    Micrograph,
    QualityGroupPrediction,
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
    CreateFoilHoleGroupEvent,
    CtfCompleteBody,
    FoilHoleCreatedEvent,
    FoilHoleDeletedEvent,
    FoilHoleGroupModelPredictionEvent,
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
    ParticlePickingCompleteBody,
    RefreshPredictionsEvent,
)
from smartem_backend.mq_publisher import (
    publish_agent_instruction_created,
    publish_ctf_estimation_registered,
    publish_motion_correction_registered,
    publish_particle_picking_registered,
)
from smartem_backend.predictions.acquisition import ordered_holes
from smartem_backend.predictions.update import overall_predictions_update, prior_update
from smartem_backend.rmq import AioPikaConsumer, AioPikaPublisher, decode_event_body
from smartem_backend.rmq.config import load_rmq_connection_url, load_rmq_topology
from smartem_backend.utils import load_conf, setup_logger, setup_postgres_async_connection

load_dotenv(override=False)  # Don't override existing env vars as these might be coming from k8s
conf = load_conf()

# Initialize logger with default ERROR level (will be reconfigured in main())
log_manager = LogManager.get_instance("smartem_backend")
logger = log_manager.configure(LogConfig(level=logging.ERROR, console=True))

async_db_engine: AsyncEngine
SessionLocal: async_sessionmaker[AsyncSession]
if os.getenv("SKIP_DB_INIT", "false").lower() != "true":
    async_db_engine = setup_postgres_async_connection()
    SessionLocal = async_sessionmaker(
        bind=async_db_engine, class_=AsyncSession, autocommit=False, autoflush=False, expire_on_commit=False
    )
else:
    async_db_engine = None  # type: ignore[assignment]
    SessionLocal = None  # type: ignore[assignment]

EventHandler = Callable[[dict[str, Any]], Awaitable[None]]


async def handle_acquisition_created(event_data: dict[str, Any]) -> None:
    try:
        event = AcquisitionCreatedEvent(**event_data)
        logger.info(f"Acquisition created event: {event.model_dump()}")
    except ValidationError as e:
        logger.error(f"Validation error processing acquisition created event: {e}")
    except Exception as e:
        logger.error(f"Error processing acquisition created event: {e}")


async def handle_acquisition_updated(event_data: dict[str, Any]) -> None:
    try:
        event = AcquisitionUpdatedEvent(**event_data)
        logger.info(f"Acquisition updated event: {event.model_dump()}")
    except ValidationError as e:
        logger.error(f"Validation error processing acquisition updated event: {e}")
    except Exception as e:
        logger.error(f"Error processing acquisition updated event: {e}")


async def handle_acquisition_deleted(event_data: dict[str, Any]) -> None:
    try:
        event = AcquisitionDeletedEvent(**event_data)
        logger.info(f"Acquisition deleted event: {event.model_dump()}")
    except ValidationError as e:
        logger.error(f"Validation error processing acquisition deleted event: {e}")
    except Exception as e:
        logger.error(f"Error processing acquisition deleted event: {e}")


async def handle_atlas_created(event_data: dict[str, Any]) -> None:
    try:
        event = AtlasCreatedEvent(**event_data)
        logger.info(f"Atlas created event: {event.model_dump()}")
    except ValidationError as e:
        logger.error(f"Validation error processing atlas created event: {e}")
    except Exception as e:
        logger.error(f"Error processing atlas created event: {e}")


async def handle_atlas_updated(event_data: dict[str, Any]) -> None:
    try:
        event = AtlasUpdatedEvent(**event_data)
        logger.info(f"Atlas updated event: {event.model_dump()}")
    except ValidationError as e:
        logger.error(f"Validation error processing atlas updated event: {e}")
    except Exception as e:
        logger.error(f"Error processing atlas updated event: {e}")


async def handle_atlas_deleted(event_data: dict[str, Any]) -> None:
    try:
        event = AtlasDeletedEvent(**event_data)
        logger.info(f"Atlas deleted event: {event.model_dump()}")
    except ValidationError as e:
        logger.error(f"Validation error processing atlas deleted event: {e}")
    except Exception as e:
        logger.error(f"Error processing atlas deleted event: {e}")


async def handle_grid_created(event_data: dict[str, Any]) -> None:
    try:
        event = GridCreatedEvent(**event_data)
        logger.info(f"Grid created event: {event.model_dump()}")
        try:
            await initialise_all_models_for_grid(event.uuid)
            logger.info(f"Successfully initialised prediction model weights for grid {event.uuid}")
        except Exception as weight_init_error:
            logger.error(f"Failed to initialise prediction model weights for grid {event.uuid}: {weight_init_error}")
    except ValidationError as e:
        logger.error(f"Validation error processing grid created event: {e}")
    except Exception as e:
        logger.error(f"Error processing grid created event: {e}")


async def handle_grid_updated(event_data: dict[str, Any]) -> None:
    try:
        event = GridUpdatedEvent(**event_data)
        logger.info(f"Grid updated event: {event.model_dump()}")
    except ValidationError as e:
        logger.error(f"Validation error processing grid updated event: {e}")
    except Exception as e:
        logger.error(f"Error processing grid updated event: {e}")


async def handle_grid_deleted(event_data: dict[str, Any]) -> None:
    try:
        event = GridDeletedEvent(**event_data)
        logger.info(f"Grid deleted event: {event.model_dump()}")
    except ValidationError as e:
        logger.error(f"Validation error processing grid deleted event: {e}")
    except Exception as e:
        logger.error(f"Error processing grid deleted event: {e}")


async def handle_grid_registered(event_data: dict[str, Any]) -> None:
    try:
        event = GridRegisteredEvent(**event_data)
        logger.info(f"Grid registered event: {event.model_dump()}")
    except ValidationError as e:
        logger.error(f"Validation error processing grid registered event: {e}")
    except Exception as e:
        logger.error(f"Error processing grid registered event: {e}")


async def handle_gridsquare_lowmag_created(event_data: dict[str, Any]) -> None:
    try:
        event = GridSquareCreatedEvent(**event_data)
        logger.info(f"GridSquare low mag created event: {event.model_dump()}")
    except ValidationError as e:
        logger.error(f"Validation error processing gridsquare created event: {e}")
    except Exception as e:
        logger.error(f"Error processing gridsquare created event: {e}")


async def handle_gridsquare_created(event_data: dict[str, Any]) -> None:
    try:
        event = GridSquareCreatedEvent(**event_data)
        logger.info(f"GridSquare created event: {event.model_dump()}")
        try:
            await generate_predictions_for_gridsquare(event.uuid, event.grid_uuid)
            logger.info(f"Successfully generated predictions for gridsquare {event.uuid}")
        except Exception as prediction_error:
            logger.error(f"Failed to generate predictions for gridsquare {event.uuid}: {prediction_error}")
    except ValidationError as e:
        logger.error(f"Validation error processing gridsquare created event: {e}")
    except Exception as e:
        logger.error(f"Error processing gridsquare created event: {e}")


async def handle_gridsquare_lowmag_updated(event_data: dict[str, Any]) -> None:
    try:
        event = GridSquareUpdatedEvent(**event_data)
        logger.info(f"GridSquare low mag updated event: {event.model_dump()}")
    except ValidationError as e:
        logger.error(f"Validation error processing gridsquare low mag updated event: {e}")
    except Exception as e:
        logger.error(f"Error processing gridsquare low mag updated event: {e}")


async def handle_gridsquare_updated(event_data: dict[str, Any]) -> None:
    try:
        event = GridSquareUpdatedEvent(**event_data)
        logger.info(f"GridSquare updated event: {event.model_dump()}")
    except ValidationError as e:
        logger.error(f"Validation error processing gridsquare updated event: {e}")
    except Exception as e:
        logger.error(f"Error processing gridsquare updated event: {e}")


async def handle_gridsquare_lowmag_deleted(event_data: dict[str, Any]) -> None:
    try:
        event = GridSquareDeletedEvent(**event_data)
        logger.info(f"GridSquare low mag deleted event: {event.model_dump()}")
    except ValidationError as e:
        logger.error(f"Validation error processing low mag gridsquare deleted event: {e}")
    except Exception as e:
        logger.error(f"Error processing low mag gridsquare deleted event: {e}")


async def handle_gridsquare_deleted(event_data: dict[str, Any]) -> None:
    try:
        event = GridSquareDeletedEvent(**event_data)
        logger.info(f"GridSquare deleted event: {event.model_dump()}")
    except ValidationError as e:
        logger.error(f"Validation error processing gridsquare deleted event: {e}")
    except Exception as e:
        logger.error(f"Error processing gridsquare deleted event: {e}")


async def handle_gridsquare_registered(event_data: dict[str, Any]) -> None:
    try:
        event = GridSquareRegisteredEvent(**event_data)
        logger.info(f"Grid square registered event: {event.model_dump()}")
    except ValidationError as e:
        logger.error(f"Validation error processing grid square registered event: {e}")
    except Exception as e:
        logger.error(f"Error processing grid square registered event: {e}")


async def handle_foilhole_created(event_data: dict[str, Any]) -> None:
    try:
        event = FoilHoleCreatedEvent(**event_data)
        logger.info(f"FoilHole created event: {event.model_dump()}")
        try:
            await generate_predictions_for_foilhole(event.uuid, event.gridsquare_uuid)
            logger.info(f"Successfully generated predictions for foilhole {event.uuid}")
        except Exception as prediction_error:
            logger.error(f"Failed to generate predictions for foilhole {event.uuid}: {prediction_error}")
    except ValidationError as e:
        logger.error(f"Validation error processing foilhole created event: {e}")
    except Exception as e:
        logger.error(f"Error processing foilhole created event: {e}")


async def handle_foilhole_updated(event_data: dict[str, Any]) -> None:
    try:
        event = FoilHoleUpdatedEvent(**event_data)
        logger.info(f"FoilHole updated event: {event.model_dump()}")
    except ValidationError as e:
        logger.error(f"Validation error processing foilhole updated event: {e}")
    except Exception as e:
        logger.error(f"Error processing foilhole updated event: {e}")


async def handle_foilhole_deleted(event_data: dict[str, Any]) -> None:
    try:
        event = FoilHoleDeletedEvent(**event_data)
        logger.info(f"FoilHole deleted event: {event.model_dump()}")
    except ValidationError as e:
        logger.error(f"Validation error processing foilhole deleted event: {e}")
    except Exception as e:
        logger.error(f"Error processing foilhole deleted event: {e}")


async def handle_micrograph_created(event_data: dict[str, Any]) -> None:
    try:
        event = MicrographCreatedEvent(**event_data)
        logger.info(f"Micrograph created event: {event.model_dump()}")
        try:
            await simulate_processing_pipeline_async(event.uuid)
            logger.info(f"Started processing pipeline simulation for micrograph {event.uuid}")
        except Exception as simulation_error:
            logger.error(f"Failed to start processing simulation for micrograph {event.uuid}: {simulation_error}")
    except ValidationError as e:
        logger.error(f"Validation error processing micrograph created event: {e}")
    except Exception as e:
        logger.error(f"Error processing micrograph created event: {e}")


async def handle_micrograph_updated(event_data: dict[str, Any]) -> None:
    try:
        event = MicrographUpdatedEvent(**event_data)
        logger.info(f"Micrograph updated event: {event.model_dump()}")
    except ValidationError as e:
        logger.error(f"Validation error processing micrograph updated event: {e}")
    except Exception as e:
        logger.error(f"Error processing micrograph updated event: {e}")


async def handle_micrograph_deleted(event_data: dict[str, Any]) -> None:
    try:
        event = MicrographDeletedEvent(**event_data)
        logger.info(f"Micrograph deleted event: {event.model_dump()}")
    except ValidationError as e:
        logger.error(f"Validation error processing micrograph deleted event: {e}")
    except Exception as e:
        logger.error(f"Error processing micrograph deleted event: {e}")


async def _check_against_statistics(
    metric_name: str,
    micrograph_uuid: str,
    comparison_value: float,
    larger_better: bool = False,
) -> float:
    async with SessionLocal() as session:
        grid_row = (
            await session.execute(
                select(GridSquare, FoilHole, Micrograph)
                .where(GridSquare.uuid == FoilHole.gridsquare_uuid)
                .where(FoilHole.uuid == Micrograph.foilhole_uuid)
                .where(Micrograph.uuid == micrograph_uuid)
            )
        ).one()
        grid_uuid = grid_row[0].grid_uuid
        metric_stats = (
            (
                await session.execute(
                    select(QualityMetricStatistics)
                    .where(QualityMetricStatistics.grid_uuid == grid_uuid)
                    .where(QualityMetricStatistics.name == metric_name)
                )
            )
            .scalars()
            .all()
        )
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


async def handle_motion_correction_complete(event_data: dict[str, Any]) -> None:
    try:
        event = MotionCorrectionCompleteBody(**event_data)
        quality = await _check_against_statistics("motioncorrection", event.micrograph_uuid, event.total_motion)
        async with SessionLocal() as session:
            grid_row = (
                await session.execute(
                    select(GridSquare, FoilHole, Micrograph)
                    .where(GridSquare.uuid == FoilHole.gridsquare_uuid)
                    .where(FoilHole.uuid == Micrograph.foilhole_uuid)
                    .where(Micrograph.uuid == event.micrograph_uuid)
                )
            ).one()
            grid_uuid = grid_row[0].grid_uuid
            metric_stats = (
                (
                    await session.execute(
                        select(QualityMetricStatistics)
                        .where(QualityMetricStatistics.grid_uuid == grid_uuid)
                        .where(QualityMetricStatistics.name == "motioncorrection")
                    )
                )
                .scalars()
                .all()
            )
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
            await session.commit()
            await prior_update(quality, event.micrograph_uuid, "motioncorrection", session)
        await publish_motion_correction_registered(
            event.micrograph_uuid, quality >= 0.5, metric_name="motioncorrection"
        )
    except ValidationError as e:
        logger.error(f"Validation error processing motion correction event: {e}")
    except Exception as e:
        logger.error(f"Error processing motion correction event: {e}")


async def handle_ctf_estimation_complete(event_data: dict[str, Any]) -> None:
    try:
        event = CtfCompleteBody(**event_data)
        quality = await _check_against_statistics(
            "ctfmaxresolution", event.micrograph_uuid, event.ctf_max_resolution_estimate
        )
        async with SessionLocal() as session:
            grid_row = (
                await session.execute(
                    select(GridSquare, FoilHole, Micrograph)
                    .where(GridSquare.uuid == FoilHole.gridsquare_uuid)
                    .where(FoilHole.uuid == Micrograph.foilhole_uuid)
                    .where(Micrograph.uuid == event.micrograph_uuid)
                )
            ).one()
            grid_uuid = grid_row[0].grid_uuid
            metric_stats = (
                (
                    await session.execute(
                        select(QualityMetricStatistics)
                        .where(QualityMetricStatistics.grid_uuid == grid_uuid)
                        .where(QualityMetricStatistics.name == "ctfmaxresolution")
                    )
                )
                .scalars()
                .all()
            )
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
            await session.commit()
            await prior_update(quality, event.micrograph_uuid, "ctfmaxresolution", session)
        await publish_ctf_estimation_registered(event.micrograph_uuid, quality >= 0.5, metric_name="ctfmaxresolution")
    except ValidationError as e:
        logger.error(f"Validation error processing ctf event: {e}")
    except Exception as e:
        logger.error(f"Error processing ctf event: {e}")


async def handle_particle_picking_complete(event_data: dict[str, Any]) -> None:
    try:
        event = ParticlePickingCompleteBody(**event_data)
        quality = await _check_against_statistics(
            "numparticles", event.micrograph_uuid, event.number_of_particles_picked, larger_better=True
        )
        async with SessionLocal() as session:
            grid_row = (
                await session.execute(
                    select(GridSquare, FoilHole, Micrograph)
                    .where(GridSquare.uuid == FoilHole.gridsquare_uuid)
                    .where(FoilHole.uuid == Micrograph.foilhole_uuid)
                    .where(Micrograph.uuid == event.micrograph_uuid)
                )
            ).one()
            grid_uuid = grid_row[0].grid_uuid
            metric_stats = (
                (
                    await session.execute(
                        select(QualityMetricStatistics)
                        .where(QualityMetricStatistics.grid_uuid == grid_uuid)
                        .where(QualityMetricStatistics.name == "numparticles")
                    )
                )
                .scalars()
                .all()
            )
            if not metric_stats:
                updated_metric_stats = QualityMetricStatistics(
                    grid_uuid=grid_uuid,
                    name="numparticles",
                    count=1,
                    value_sum=event.number_of_particles_picked,
                    squared_value_sum=0,
                )
            else:
                updated_metric_stats = metric_stats[0]
                old_diff = event.number_of_particles_picked - (
                    updated_metric_stats.value_sum / updated_metric_stats.count
                )
                updated_metric_stats.count += 1
                updated_metric_stats.value_sum += event.number_of_particles_picked
                updated_metric_stats.squared_value_sum += old_diff * (
                    event.number_of_particles_picked - (updated_metric_stats.value_sum / updated_metric_stats.count)
                )
            session.add(updated_metric_stats)
            await session.commit()
            await prior_update(quality, event.micrograph_uuid, "numparticles", session)
        await publish_particle_picking_registered(event.micrograph_uuid, quality >= 0.5, metric_name="numparticles")
    except ValidationError as e:
        logger.error(f"Validation error processing particle picking event: {e}")
    except Exception as e:
        logger.error(f"Error processing particle picking event: {e}")


async def handle_gridsquare_model_prediction(event_data: dict[str, Any]) -> None:
    try:
        event = GridSquareModelPredictionEvent(**event_data)
        quality_prediction = QualityPrediction(
            gridsquare_uuid=event.gridsquare_uuid,
            prediction_model_name=event.prediction_model_name,
            value=event.prediction_value,
            metric_name=event.metric,
        )
        async with SessionLocal() as session:
            session.add(quality_prediction)
            current_quality_prediction = (
                (
                    await session.execute(
                        select(CurrentQualityPrediction)
                        .where(CurrentQualityPrediction.gridsquare_uuid == event.gridsquare_uuid)
                        .where(CurrentQualityPrediction.prediction_model_name == event.prediction_model_name)
                        .where(CurrentQualityPrediction.metric_name == event.metric)
                    )
                )
                .scalars()
                .first()
            )
            if current_quality_prediction is None:
                grid_uuid = (
                    (await session.execute(select(GridSquare).where(GridSquare.uuid == event.gridsquare_uuid)))
                    .scalars()
                    .one()
                    .grid_uuid
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
            await session.commit()
    except ValidationError as e:
        logger.error(f"Validation error processing grid square model prediction event: {e}")
    except Exception as e:
        logger.error(f"Error processing grid square model prediction event: {e}")


async def handle_foilhole_model_prediction(event_data: dict[str, Any]) -> None:
    try:
        event = FoilHoleModelPredictionEvent(**event_data)
        quality_prediction = QualityPrediction(
            foilhole_uuid=event.foilhole_uuid,
            prediction_model_name=event.prediction_model_name,
            value=event.prediction_value,
            metric_name=event.metric,
        )
        async with SessionLocal() as session:
            session.add(quality_prediction)
            current_quality_prediction = (
                (
                    await session.execute(
                        select(CurrentQualityPrediction)
                        .where(CurrentQualityPrediction.foilhole_uuid == event.foilhole_uuid)
                        .where(CurrentQualityPrediction.prediction_model_name == event.prediction_model_name)
                        .where(CurrentQualityPrediction.metric_name == event.metric)
                    )
                )
                .scalars()
                .first()
            )
            if current_quality_prediction is None:
                square_row = (
                    await session.execute(
                        select(GridSquare, FoilHole)
                        .where(GridSquare.uuid == FoilHole.gridsquare_uuid)
                        .where(FoilHole.uuid == event.foilhole_uuid)
                    )
                ).one()
                square = square_row[0]
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
            await session.commit()
    except ValidationError as e:
        logger.error(f"Validation error processing foil hole model prediction event: {e}")
    except Exception as e:
        logger.error(f"Error processing foil hole model prediction event: {e}")


async def handle_multi_foilhole_model_prediction(event_data: dict[str, Any]) -> None:
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
        async with SessionLocal() as session:
            session.add_all(quality_predictions)
            current_quality_predictions = list(
                (
                    await session.execute(
                        select(CurrentQualityPrediction)
                        .where(CurrentQualityPrediction.foilhole_uuid.in_(event.foilhole_uuids))
                        .where(CurrentQualityPrediction.prediction_model_name == event.prediction_model_name)
                        .where(CurrentQualityPrediction.metric_name == event.metric)
                    )
                )
                .scalars()
                .all()
            )
            if not current_quality_predictions:
                squares = (
                    await session.execute(
                        select(GridSquare, FoilHole)
                        .where(GridSquare.uuid == FoilHole.gridsquare_uuid)
                        .where(FoilHole.uuid.in_(event.foilhole_uuids))
                    )
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
            await session.commit()
    except ValidationError as e:
        logger.error(f"Validation error processing multiple foil hole model prediction event: {e}")
    except Exception as e:
        logger.error(f"Error processing multiple foil hole model prediction event: {e}")


async def handle_create_foilhole_group(event_data: dict[str, Any]) -> None:
    try:
        event = CreateFoilHoleGroupEvent(**event_data)
        async with SessionLocal() as session:
            group = (
                (await session.execute(select(FoilHoleGroup).where(FoilHoleGroup.uuid == event.group_uuid)))
                .scalars()
                .first()
            )
            if group is None:
                group = FoilHoleGroup(
                    uuid=event.group_uuid,
                    grid_uuid=event.grid_uuid,
                    name=event.name,
                )
                session.add(group)
                memberships = [
                    FoilHoleGroupMembership(group_uuid=event.group_uuid, foilhole_uuid=fhuuid)
                    for fhuuid in event.foilhole_uuids
                ]
                session.add_all(memberships)
            else:
                group.name = event.name
                existing_memberships = (
                    (
                        await session.execute(
                            select(FoilHoleGroupMembership).where(
                                FoilHoleGroupMembership.group_uuid == event.group_uuid
                            )
                        )
                    )
                    .scalars()
                    .all()
                )
                existing_uuids = {m.foilhole_uuid for m in existing_memberships}
                new_memberships = [
                    FoilHoleGroupMembership(group_uuid=event.group_uuid, foilhole_uuid=fhuuid)
                    for fhuuid in event.foilhole_uuids
                    if fhuuid not in existing_uuids
                ]
                session.add_all(new_memberships)
            await session.commit()
    except ValidationError as e:
        logger.error(f"Validation error processing create foil hole group event: {e}")
    except Exception as e:
        logger.error(f"Error processing create foil hole group event: {e}")


async def handle_foilhole_group_model_prediction(event_data: dict[str, Any]) -> None:
    try:
        event = FoilHoleGroupModelPredictionEvent(**event_data)
        async with SessionLocal() as session:
            group = (
                (await session.execute(select(FoilHoleGroup).where(FoilHoleGroup.uuid == event.group_uuid)))
                .scalars()
                .one()
            )
            session.add(
                QualityGroupPrediction(
                    group_uuid=event.group_uuid,
                    grid_uuid=group.grid_uuid,
                    value=event.prediction_value,
                    prediction_model_name=event.prediction_model_name,
                    metric_name=event.metric,
                )
            )
            existing = (
                (
                    await session.execute(
                        select(CurrentQualityGroupPrediction)
                        .where(CurrentQualityGroupPrediction.group_uuid == event.group_uuid)
                        .where(CurrentQualityGroupPrediction.prediction_model_name == event.prediction_model_name)
                        .where(CurrentQualityGroupPrediction.metric_name == event.metric)
                    )
                )
                .scalars()
                .first()
            )
            if existing is None:
                session.add(
                    CurrentQualityGroupPrediction(
                        group_uuid=event.group_uuid,
                        grid_uuid=group.grid_uuid,
                        value=event.prediction_value,
                        prediction_model_name=event.prediction_model_name,
                        metric_name=event.metric,
                    )
                )
            else:
                existing.value = event.prediction_value
            await session.commit()
    except ValidationError as e:
        logger.error(f"Validation error processing foil hole group model prediction event: {e}")
    except Exception as e:
        logger.error(f"Error processing foil hole group model prediction event: {e}")


async def handle_refresh_predictions(event_data: dict[str, Any]) -> None:
    try:
        event = RefreshPredictionsEvent(**event_data)
        async with SessionLocal() as session:
            await overall_predictions_update(event.grid_uuid, session)
            await ordered_holes(event.grid_uuid, session)
    except ValidationError as e:
        logger.error(f"Validation error processing refresh predictions event: {e}")
    except Exception as e:
        logger.error(f"Error processing refresh predictions event: {e}")


async def handle_model_parameter_update(event_data: dict[str, Any]) -> None:
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
        async with SessionLocal() as session:
            session.add(model_parameter)
            await session.commit()
    except ValidationError as e:
        logger.error(f"Validation error processing model parameter update event: {e}")
    except Exception as e:
        logger.error(f"Error processing model parameter update event: {e}")


# ============ External Message Processing Events ============


async def _get_active_agent_sessions() -> list[AgentSession]:
    async with SessionLocal() as session:
        result = await session.execute(select(AgentSession).where(AgentSession.status == "active"))
        return list(result.scalars().all())


async def handle_external_gridsquare_model_prediction(event_data: dict[str, Any]) -> None:
    try:
        payload = event_data.get("payload", {})
        gridsquare_id = payload.get("gridsquare_id")
        quality_score = payload.get("prediction_results", {}).get("quality_score", 0.0)

        logger.info(f"External gridsquare prediction: {gridsquare_id} with quality {quality_score}")

        if quality_score >= 0.8:
            instruction_type = "microscope.control.reorder_gridsquares"
            instruction_payload = {
                "gridsquare_ids": [gridsquare_id],
                "priority": "high",
                "reason": f"High quality prediction: {quality_score:.3f}",
            }
        elif quality_score <= 0.3:
            instruction_type = "microscope.control.skip_gridsquares"
            instruction_payload = {
                "gridsquare_ids": [gridsquare_id],
                "reason": f"Low quality prediction: {quality_score:.3f}",
            }
        else:
            logger.info(f"Medium quality gridsquare {gridsquare_id} ({quality_score:.3f}) - no action needed")
            return

        active_sessions = await _get_active_agent_sessions()
        for session in active_sessions:
            instruction_id = str(uuid.uuid4())
            success = await publish_agent_instruction_created(
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


async def handle_external_foilhole_model_prediction(event_data: dict[str, Any]) -> None:
    try:
        payload = event_data.get("payload", {})
        gridsquare_id = payload.get("gridsquare_id")
        foilholes = payload.get("foilhole_predictions", [])

        high_quality_foilholes = [fh for fh in foilholes if fh.get("quality_score", 0) >= 0.8]

        if len(high_quality_foilholes) > 0:
            instruction_type = "microscope.control.reorder_foilholes"
            instruction_payload = {
                "gridsquare_id": gridsquare_id,
                "foilhole_ids": [fh["foilhole_id"] for fh in high_quality_foilholes],
                "priority": "high",
                "reason": f"Found {len(high_quality_foilholes)} high quality foilholes",
            }

            active_sessions = await _get_active_agent_sessions()
            for session in active_sessions:
                instruction_id = str(uuid.uuid4())
                success = await publish_agent_instruction_created(
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


async def handle_gridsquare_model_prediction_router(event_data: dict[str, Any]) -> None:
    source = event_data.get("source", "")
    if source == "external_simulator":
        await handle_external_gridsquare_model_prediction(event_data)
    else:
        await handle_gridsquare_model_prediction(event_data)


async def handle_foilhole_model_prediction_router(event_data: dict[str, Any]) -> None:
    source = event_data.get("source", "")
    if source == "external_simulator":
        await handle_external_foilhole_model_prediction(event_data)
    else:
        await handle_foilhole_model_prediction(event_data)


# ============ Agent Communication Events ============


async def handle_agent_instruction_created(event_data: dict[str, Any]) -> None:
    try:
        event = AgentInstructionCreatedEvent(**event_data)
        logger.info(f"Agent instruction created event: {event.model_dump()}")

        async with SessionLocal() as session:
            session_obj = (
                (await session.execute(select(AgentSession).where(AgentSession.session_id == event.session_id)))
                .scalars()
                .first()
            )
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
            await session.commit()
        logger.info(f"Successfully persisted instruction {event.instruction_id} to database")
    except ValidationError as e:
        logger.error(f"Validation error processing agent instruction created event: {e}")
    except Exception as e:
        logger.error(f"Error processing agent instruction created event: {e}")


async def handle_agent_instruction_updated(event_data: dict[str, Any]) -> None:
    try:
        event = AgentInstructionUpdatedEvent(**event_data)
        logger.info(f"Agent instruction updated event: {event.model_dump()}")

        async with SessionLocal() as session:
            instruction = (
                (
                    await session.execute(
                        select(AgentInstruction).where(AgentInstruction.instruction_id == event.instruction_id)
                    )
                )
                .scalars()
                .first()
            )
            if instruction is None:
                logger.warning(f"Instruction {event.instruction_id} not found for status update")
                return
            instruction.status = event.status
            if event.acknowledged_at:
                instruction.acknowledged_at = event.acknowledged_at
            await session.commit()
        logger.info(f"Updated instruction {event.instruction_id} status to {event.status}")
    except ValidationError as e:
        logger.error(f"Validation error processing agent instruction updated event: {e}")
    except Exception as e:
        logger.error(f"Error processing agent instruction updated event: {e}")


async def handle_agent_instruction_expired(event_data: dict[str, Any]) -> None:
    try:
        event = AgentInstructionExpiredEvent(**event_data)
        logger.info(f"Agent instruction expired event: {event.model_dump()}")

        async with SessionLocal() as session:
            instruction = (
                (
                    await session.execute(
                        select(AgentInstruction).where(AgentInstruction.instruction_id == event.instruction_id)
                    )
                )
                .scalars()
                .first()
            )
            if instruction is None:
                logger.warning(f"Instruction {event.instruction_id} not found for expiry handling")
                return
            if event.retry_count >= instruction.max_retries:
                instruction.status = "expired"
                resolution = "expired"
            else:
                instruction.status = "pending"
                instruction.retry_count = event.retry_count
                resolution = "retry"
            await session.commit()
        if resolution == "expired":
            logger.info(f"Instruction {event.instruction_id} marked as expired after {event.retry_count} retries")
        else:
            logger.info(f"Instruction {event.instruction_id} reset for retry ({event.retry_count})")
    except ValidationError as e:
        logger.error(f"Validation error processing agent instruction expired event: {e}")
    except Exception as e:
        logger.error(f"Error processing agent instruction expired event: {e}")


def get_event_handlers() -> dict[str, EventHandler]:
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
        MessageQueueEventType.PARTICLE_PICKING_COMPLETE.value: handle_particle_picking_complete,
        MessageQueueEventType.GRIDSQUARE_MODEL_PREDICTION.value: handle_gridsquare_model_prediction,
        MessageQueueEventType.FOILHOLE_MODEL_PREDICTION.value: handle_foilhole_model_prediction,
        MessageQueueEventType.MULTI_FOILHOLE_MODEL_PREDICTION.value: handle_multi_foilhole_model_prediction,
        MessageQueueEventType.CREATE_FOILHOLE_GROUP.value: handle_create_foilhole_group,
        MessageQueueEventType.FOILHOLE_GROUP_MODEL_PREDICTION.value: handle_foilhole_group_model_prediction,
        MessageQueueEventType.MODEL_PARAMETER_UPDATE.value: handle_model_parameter_update,
        MessageQueueEventType.REFRESH_PREDICTIONS.value: handle_refresh_predictions,
    }


async def _on_message(consumer: AioPikaConsumer, message: AbstractIncomingMessage) -> None:
    """Dispatch an incoming message to its handler and manage ack/retry."""
    retry_count = 0
    if message.headers and "x-retry-count" in message.headers:
        retry_count = int(message.headers["x-retry-count"])
    event_type = "unknown"

    try:
        event_data = decode_event_body(message)
        logger.info(f"Received message: {event_data}")

        if "event_type" not in event_data:
            logger.warning(f"Message missing 'event_type' field: {event_data}")
            await message.reject(requeue=False)
            return

        event_type = event_data["event_type"]
        handlers = get_event_handlers()
        handler = handlers.get(event_type)
        if handler is None:
            logger.warning(f"No handler registered for event type: {event_type}")
            await message.reject(requeue=False)
            return

        await handler(event_data)
        await message.ack()
        logger.debug(f"Successfully processed {event_type} event")
    except json.JSONDecodeError:
        logger.error(f"Failed to decode JSON message: {message.body!r}")
        await message.reject(requeue=False)
    except Exception as e:
        logger.error(f"Error processing message: {e}")
        if retry_count >= 3:
            logger.warning(f"Message failed after {retry_count} retries, dropping message")
            await message.reject(requeue=False)
            return
        try:
            await consumer.requeue_with_retry(message, retry_count + 1)
            await message.ack()
            logger.debug(f"Republished message with retry count {retry_count + 1}, event_type: {event_type}")
        except Exception as republish_error:
            logger.error(f"Failed to republish message: {republish_error}")
            await message.reject(requeue=True)


async def _run(consumer: AioPikaConsumer, stop_event: asyncio.Event) -> None:
    """Consume until stop_event is set, reconnecting on transport errors."""

    async def handler(message: AbstractIncomingMessage) -> None:
        await _on_message(consumer, message)

    while not stop_event.is_set():
        try:
            logger.info("Starting RabbitMQ consumer...")
            consume_task = asyncio.create_task(consumer.consume(handler))
            stop_task = asyncio.create_task(stop_event.wait())
            done, pending = await asyncio.wait({consume_task, stop_task}, return_when=asyncio.FIRST_COMPLETED)
            for task in pending:
                task.cancel()
            for task in done:
                exc = task.exception()
                if exc is not None and not isinstance(exc, asyncio.CancelledError):
                    raise exc
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Error in consumer: {e}")
            if stop_event.is_set():
                break
            logger.info("Retrying in 10 seconds...")
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=10)
            except TimeoutError:
                pass


async def amain(verbosity: int) -> None:
    if verbosity >= 2:
        log_level = logging.DEBUG
    elif verbosity == 1:
        log_level = logging.INFO
    else:
        log_level = logging.ERROR

    global logger
    logger = setup_logger(level=log_level, conf=conf)

    url = load_rmq_connection_url()
    exchange_name, queue_name = load_rmq_topology()

    # The consumer process invokes publish_* from mq_publisher too (reply events).
    # Those functions require a bound publisher on the same event loop.
    publisher = AioPikaPublisher(url=url, exchange_name=exchange_name, routing_key=queue_name)
    await publisher.connect()
    mq_publisher_module.set_publisher(publisher)

    consumer = AioPikaConsumer(url=url, queue_name=queue_name, exchange_name=exchange_name, prefetch_count=1)
    await consumer.connect()

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()

    def _request_stop() -> None:
        logger.info("Received shutdown signal, stopping consumer...")
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _request_stop)
        except NotImplementedError:
            # Windows doesn't support add_signal_handler; fall back to default handler.
            signal.signal(sig, lambda *_: _request_stop())

    try:
        await _run(consumer, stop_event)
    finally:
        try:
            await consumer.close()
        except Exception as e:
            logger.error(f"Error closing consumer: {e}")
        try:
            await publisher.close()
        except Exception as e:
            logger.error(f"Error closing publisher: {e}")
        mq_publisher_module.set_publisher(None)


def main() -> None:
    parser = argparse.ArgumentParser(description="SmartEM Decisions MQ Consumer")
    parser.add_argument(
        "-v", "--verbose", action="count", default=0, help="Increase verbosity (-v for INFO, -vv for DEBUG)"
    )
    args = parser.parse_args()
    asyncio.run(amain(args.verbose))


if __name__ == "__main__":
    main()
