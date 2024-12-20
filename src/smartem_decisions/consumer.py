#!/usr/bin/env python

import json
import os
from inspect import currentframe, getframeinfo
from logging import LogRecord

import pika
from dotenv import load_dotenv
from sqlmodel import create_engine, Session as SQLModelSession
from smartem_decisions.plugin_logging import GraylogUDPHandler
from pydantic import ValidationError
from smartem_decisions.utils import load_conf
from smartem_decisions.model.mq_event import (
    MessageQueueEventType,
    SessionStartBody,
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
    SessionEndBody,
)
from smartem_decisions.workflow import (
    session_start,
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
    session_end,
)

load_dotenv()
conf = load_conf()

graylog_handler = GraylogUDPHandler(
    host=os.environ["GRAYLOG_HOST"],
    # For testing without graylog, run `nc -klu 12209` to see what's been sent:
    # port=12209
    port=int(os.environ["GRAYLOG_UDP_PORT"]),
)


def _log_info(message):
    frame = currentframe()
    assert frame is not None, "Could not get the current frame"
    frame_info = getframeinfo(frame)
    # Ref: https://docs.python.org/3/library/logging.html#logging.LogRecord
    graylog_handler.handle(
        LogRecord(
            name=conf["app"]["name"],
            level=20,  # INFO
            pathname=frame_info.filename,  # TODO get pathname not filename
            lineno=frame_info.lineno,
            args={},
            exc_info=None,
            msg=json.dumps(message),
        )
    )


def _log_issue(message):
    frame = currentframe()
    assert frame is not None, "Could not get the current frame"
    frame_info = getframeinfo(frame)
    # Ref: https://docs.python.org/3/library/logging.html#logging.LogRecord
    graylog_handler.handle(
        LogRecord(
            name=conf["app"]["name"],
            level=40,  # ERROR
            pathname=frame_info.filename,  # TODO get pathname not filename
            lineno=frame_info.lineno,
            args={},
            exc_info=None,
            msg=json.dumps(message),
        )
    )


assert os.getenv("RABBITMQ_HOST") is not None, "Could not get env var RABBITMQ_HOST"
assert os.getenv("RABBITMQ_PORT") is not None, "Could not get env var RABBITMQ_PORT"
assert os.getenv("RABBITMQ_USER") is not None, "Could not get env var RABBITMQ_USER"
assert os.getenv("RABBITMQ_PASSWORD") is not None, "Could not get env var RABBITMQ_PASSWORD"
connection = pika.BlockingConnection(
    pika.ConnectionParameters(
        host=os.getenv("RABBITMQ_HOST"),  # type: ignore
        port=int(os.getenv("RABBITMQ_PORT")),  # type: ignore
        credentials=pika.PlainCredentials(
            os.getenv("RABBITMQ_USER"),  # type: ignore
            os.getenv("RABBITMQ_PASSWORD"),  # type: ignore
        ),
    )
)

channel = connection.channel()

channel.queue_declare(queue=conf["rabbitmq"]["queue_name"], durable=True)
print(" [*] Waiting for messages. To exit press CTRL+C")

assert os.getenv("POSTGRES_USER") is not None, "Could not get env var POSTGRES_USER"
assert os.getenv("POSTGRES_PASSWORD") is not None, "Could not get env var POSTGRES_PASSWORD"
assert os.getenv("POSTGRES_PORT") is not None, "Could not get env var POSTGRES_PORT"
assert os.getenv("POSTGRES_DB") is not None, "Could not get env var POSTGRES_DB"
engine = create_engine(
    f"postgresql+psycopg2://{os.getenv("POSTGRES_USER")}:{os.getenv("POSTGRES_PASSWORD")}@localhost:{os.getenv("POSTGRES_PORT")}/{os.getenv("POSTGRES_DB")}",
    echo=True,
)


def handle_event(event_type: MessageQueueEventType, message: dict, ch, method, sess):
    # Map event types to their corresponding handlers and body types
    event_handlers = {
        MessageQueueEventType.SESSION_START: (session_start, SessionStartBody),
        MessageQueueEventType.GRID_SCAN_START: (grid_scan_start, GridScanStartBody),
        MessageQueueEventType.GRID_SCAN_COMPLETE: (grid_scan_complete, GridScanCompleteBody),
        MessageQueueEventType.GRID_SQUARES_DECISION_START: (grid_squares_decision_start, GridSquaresDecisionStartBody),
        MessageQueueEventType.GRID_SQUARES_DECISION_COMPLETE: (
        grid_squares_decision_complete, GridSquaresDecisionCompleteBody),
        MessageQueueEventType.FOIL_HOLES_DETECTED: (foil_holes_detected, FoilHolesDetectedBody),
        MessageQueueEventType.FOIL_HOLES_DECISION_START: (foil_holes_decision_start, FoilHolesDecisionStartBody),
        MessageQueueEventType.FOIL_HOLES_DECISION_COMPLETE: (
        foil_holes_decision_complete, FoilHolesDecisionCompleteBody),
        MessageQueueEventType.MICROGRAPHS_DETECTED: (micrographs_detected, MicrographsDetectedBody),
        MessageQueueEventType.MOTION_CORRECTION_START: (motion_correction_start, MotionCorrectionStartBody),
        MessageQueueEventType.MOTION_CORRECTION_COMPLETE: (motion_correction_complete, MotionCorrectionCompleteBody),
        MessageQueueEventType.CTF_START: (ctf_start, CtfStartBody),
        MessageQueueEventType.CTF_COMPLETE: (ctf_complete, CtfCompleteBody),
        MessageQueueEventType.PARTICLE_PICKING_START: (particle_picking_start, ParticlePickingStartBody),
        MessageQueueEventType.PARTICLE_PICKING_COMPLETE: (particle_picking_complete, ParticlePickingCompleteBody),
        MessageQueueEventType.PARTICLE_SELECTION_START: (particle_selection_start, ParticleSelectionStartBody),
        MessageQueueEventType.PARTICLE_SELECTION_COMPLETE: (particle_selection_complete, ParticleSelectionCompleteBody),
        MessageQueueEventType.SESSION_END: (session_end, SessionEndBody),
    }

    if event_type not in event_handlers:
        print(f" [!] Unhandled event type: {event_type}")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        return

    handler, body_class = event_handlers[event_type]

    try:
        body = body_class(**message)
        print(f" [+] {event_type.value} {body}")
        _log_info(
            dict(
                message,
                **{"info": f"{event_type.value} {body}"},
            )
        )
        ch.basic_ack(delivery_tag=method.delivery_tag)
        handler(body, sess)
    except ValidationError as pve:
        print(f" [!] Failed to parse {event_type.value} body: {pve}")
        _log_issue(
            dict(
                message,
                **{"issue": f"Failed to parse {event_type.value} body: {pve}"},
            )
        )
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)


def on_message(ch, method, properties, body):
    print(f" [I] Received message with props={properties} and body: {body.decode()}")
    message = json.loads(body.decode()) # TODO assumption of valid JSON here, handle mal-formed

    if "event_type" not in message:
        print(f" [!] Message missing 'event_type' field: {message}")
        _log_issue(dict(message, **{"issue": "Message missing event_type field"}))
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        print("\n")
        return

    try:
        event_type = MessageQueueEventType(message["event_type"])
    except ValueError:
        print(f" [!] Message 'event_type' value not recognised: {message}")
        _log_issue(dict(message, **{"issue": "Message event_type value not recognised"}))
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        print("\n")
        return

    with SQLModelSession(engine) as sess:
        handle_event(event_type, message, ch, method, sess)

    print("\n")


channel.basic_qos(prefetch_count=1)
channel.basic_consume(queue=conf["rabbitmq"]["queue_name"], on_message_callback=on_message)

channel.start_consuming()
