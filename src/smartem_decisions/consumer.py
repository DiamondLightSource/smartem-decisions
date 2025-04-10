#!/usr/bin/env python

import json

from dotenv import load_dotenv
from sqlmodel import Session as SQLModelSession
from pydantic import ValidationError

from src.smartem_decisions.utils import (
    load_conf,
    logger,
    setup_rabbitmq_connection,
    setup_postgres_connection,
)
from src.smartem_decisions.model.mq_event import (
    MessageQueueEventType,
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
from src.smartem_decisions.workflow import (
    acquisition_start,
    grid_scan_start,
    grid_scan_complete,
    grid_squares_decision_start,
    grid_squares_decision_complete,
    foil_holes_detected,
    foil_holes_decision_start,
    foil_holes_decision_complete,
    micrographs_detected,
    motion_correction_start,
    motion_correction_complete,
    ctf_start,
    ctf_complete,
    particle_picking_start,
    particle_picking_complete,
    particle_selection_start,
    particle_selection_complete,
    acquisition_end,
)

load_dotenv()
conf = load_conf()
db_engine = setup_postgres_connection()


def handle_event(event_type: MessageQueueEventType, message: dict, ch, method, sess):
    # Map event types to their corresponding handlers and body types
    event_handlers = {
        MessageQueueEventType.ACQUISITION_START: (acquisition_start, AcquisitionStartBody),
        MessageQueueEventType.GRID_SCAN_START: (grid_scan_start, GridScanStartBody),
        MessageQueueEventType.GRID_SCAN_COMPLETE: (grid_scan_complete, GridScanCompleteBody),
        MessageQueueEventType.GRID_SQUARES_DECISION_START: (grid_squares_decision_start, GridSquaresDecisionStartBody),
        MessageQueueEventType.GRID_SQUARES_DECISION_COMPLETE: (
            grid_squares_decision_complete,
            GridSquaresDecisionCompleteBody,
        ),
        MessageQueueEventType.FOIL_HOLES_DETECTED: (foil_holes_detected, FoilHolesDetectedBody),
        MessageQueueEventType.FOIL_HOLES_DECISION_START: (foil_holes_decision_start, FoilHolesDecisionStartBody),
        MessageQueueEventType.FOIL_HOLES_DECISION_COMPLETE: (
            foil_holes_decision_complete,
            FoilHolesDecisionCompleteBody,
        ),
        MessageQueueEventType.MICROGRAPHS_DETECTED: (micrographs_detected, MicrographsDetectedBody),
        MessageQueueEventType.MOTION_CORRECTION_START: (motion_correction_start, MotionCorrectionStartBody),
        MessageQueueEventType.MOTION_CORRECTION_COMPLETE: (motion_correction_complete, MotionCorrectionCompleteBody),
        MessageQueueEventType.CTF_START: (ctf_start, CtfStartBody),
        MessageQueueEventType.CTF_COMPLETE: (ctf_complete, CtfCompleteBody),
        MessageQueueEventType.PARTICLE_PICKING_START: (particle_picking_start, ParticlePickingStartBody),
        MessageQueueEventType.PARTICLE_PICKING_COMPLETE: (particle_picking_complete, ParticlePickingCompleteBody),
        MessageQueueEventType.PARTICLE_SELECTION_START: (particle_selection_start, ParticleSelectionStartBody),
        MessageQueueEventType.PARTICLE_SELECTION_COMPLETE: (particle_selection_complete, ParticleSelectionCompleteBody),
        MessageQueueEventType.ACQUISITION_END: (acquisition_end, AcquisitionEndBody),
    }

    if event_type not in event_handlers:
        print(f" [!] Unhandled event type: {event_type}")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        return

    handler, body_class = event_handlers[event_type]

    try:
        body = body_class(**message)
        print(f" [+] {event_type.value} {body}")
        logger.info(
            dict(
                message,
                **{"info": f"{event_type.value} {body}"},
            )
        )
        ch.basic_ack(delivery_tag=method.delivery_tag)
        handler(body, sess)
    except ValidationError as pve:
        print(f" [!] Failed to parse {event_type.value} body: {pve}")
        logger.warning(
            dict(
                message,
                **{"issue": f"Failed to parse {event_type.value} body: {pve}"},
            )
        )
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)


def on_message(ch, method, properties, body):
    print(f" [I] Received message with props={properties} and body: {body.decode()}")
    message = json.loads(body.decode())  # TODO assumption of valid JSON here, handle mal-formed

    if "event_type" not in message:
        print(f" [!] Message missing 'event_type' field: {message}")
        logger.warning(dict(message, **{"issue": "Message missing event_type field"}))
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        print("\n")
        return

    try:
        event_type = MessageQueueEventType(message["event_type"])
    except ValueError:
        print(f" [!] Message 'event_type' value not recognised: {message}")
        logger.warning(dict(message, **{"issue": "Message event_type value not recognised"}))
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        print("\n")
        return

    with SQLModelSession(db_engine) as sess:
        handle_event(event_type, message, ch, method, sess)

    print("\n")


def main():
    rmq_connection = setup_rabbitmq_connection()
    channel = rmq_connection.channel()

    channel.queue_declare(queue=conf["rabbitmq"]["queue_name"], durable=True)
    logger.info(" [*] Waiting for messages. To exit press CTRL+C")

    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(queue=conf["rabbitmq"]["queue_name"], on_message_callback=on_message)
    channel.start_consuming()


if __name__ == "__main__":
    main()
