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
    MotionCorrectionStartBody,
    MotionCorrectionCompleteBody,
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

def on_message(ch, method, properties, body):
    print(f" [I] Received message with props={properties} and body: {body.decode()}")
    message = json.loads(body.decode())  # TODO assumption of valid JSON here, handle mal-formed

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
        match event_type:
            # Note: events below are triggered by a fs watcher on the EPU side:

            case MessageQueueEventType.session_start:
                try:
                    body = SessionStartBody(**message)
                    print(f" [+] Session Start {body}")
                    _log_info(
                        dict(
                            message,
                            **{"info": f"Session Start {body}"},
                        )
                    )
                    ch.basic_ack(delivery_tag=method.delivery_tag)
                    session_start(body, sess)
                except ValidationError as pve:
                    print(f" [!] Failed to parse Session Start body: {pve}")
                    _log_issue(
                        dict(
                            message,
                            **{"issue": f"Failed to parse Session Start body: {pve}"},
                        )
                    )
                    ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

            case MessageQueueEventType.session_pause: pass # out of scope

            case MessageQueueEventType.session_resume: pass # out of scope

            case MessageQueueEventType.grid_scan_start:
                try:
                    body = GridScanStartBody(**message)
                    print(f" [+] Grid Scan Start {body}")
                    _log_info(
                        dict(
                            message,
                            **{"info": f"Grid Scan Start {body}"},
                        )
                    )
                    ch.basic_ack(delivery_tag=method.delivery_tag)
                    grid_scan_start(body, sess)
                except ValidationError as pve:
                    print(f" [!] Failed to parse Grid Scan Start body: {pve}")
                    _log_issue(
                        dict(
                            message,
                            **{"issue": f"Failed to parse Grid Scan Start body: {pve}"},
                        )
                    )
                    ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

            case MessageQueueEventType.grid_scan_complete:
                try:
                    body = GridScanCompleteBody(**message)
                    print(f" [+] Grid Scan Complete {body}")
                    _log_info(
                        dict(
                            message,
                            **{"info": f"Grid Scan Complete {body}"},
                        )
                    )
                    ch.basic_ack(delivery_tag=method.delivery_tag)
                    grid_scan_complete(body, sess)
                except ValidationError as pve:
                    print(f" [!] Failed to parse Grid Scan Complete body: {pve}")
                    _log_issue(
                        dict(
                            message,
                            **{"issue": f"Failed to parse Grid Scan Complete body: {pve}"},
                        )
                    )
                    ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

            case MessageQueueEventType.grid_squares_decision_start:
                try:
                    body = GridSquaresDecisionStartBody(**message)
                    print(f" [+] Grid Squares Decision Start {body}")
                    _log_info(
                        dict(
                            message,
                            **{"info": f"Grid Squares Decision Start Complete {body}"},
                        )
                    )
                    ch.basic_ack(delivery_tag=method.delivery_tag)
                    grid_squares_decision_start(body, sess)
                except ValidationError as pve:
                    print(f" [!] Failed to parse Grid Squares Decision Start body: {pve}")
                    _log_issue(
                        dict(
                            message,
                            **{"issue": f"Failed to parse Grid Squares Decision Start body: {pve}"},
                        )
                    )
                    ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

            case MessageQueueEventType.grid_squares_decision_complete:
                try:
                    body = GridSquaresDecisionCompleteBody(**message)
                    print(f" [+] Grid Squares Decision Complete {body}")
                    _log_info(
                        dict(
                            message,
                            **{"info": f"Grid Squares Decision Complete {body}"},
                        )
                    )
                    ch.basic_ack(delivery_tag=method.delivery_tag)
                    grid_squares_decision_complete(body, sess)
                except ValidationError as pve:
                    print(f" [!] Failed to parse Grid Squares Decision Complete body: {pve}")
                    _log_issue(
                        dict(
                            message,
                            **{"issue": f"Failed to parse Grid Squares Decision Complete body: {pve}"},
                        )
                    )
                    ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

            case MessageQueueEventType.foil_holes_detected:
                try:
                    body = FoilHolesDetectedBody(**message)
                    print(f" [+] Motion Correction Complete {body}")
                    _log_info(
                        dict(
                            message,
                            **{"info": f"Motion Correction Complete {body}"},
                        )
                    )
                    ch.basic_ack(delivery_tag=method.delivery_tag)
                    foil_holes_detected(body, sess)
                except ValidationError as pve:
                    print(f" [!] Failed to parse Motion Correction Complete body: {pve}")
                    _log_issue(
                        dict(
                            message,
                            **{"issue": f"Failed to parse Motion Correction Complete body: {pve}"},
                        )
                    )
                    ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

            case MessageQueueEventType.foil_holes_decision_start:
                try:
                    body = FoilHolesDecisionStartBody(**message)
                    print(f" [+] Foil Holes Decision Start {body}")
                    _log_info(
                        dict(
                            message,
                            **{"info": f"Foil Holes Decision Start {body}"},
                        )
                    )
                    ch.basic_ack(delivery_tag=method.delivery_tag)
                    foil_holes_decision_start(body, sess)
                except ValidationError as pve:
                    print(f" [!] Foil Holes Decision Start body: {pve}")
                    _log_issue(
                        dict(
                            message,
                            **{"issue": f"Failed to parse Foil Holes Decision Start body: {pve}"},
                        )
                    )
                    ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

            case MessageQueueEventType.foil_holes_decision_complete:
                try:
                    body = FoilHolesDecisionCompleteBody(**message)
                    print(f" [+] Foil Holes Decision Complete {body}")
                    _log_info(
                        dict(
                            message,
                            **{"info": f"Foil Holes Decision Complete {body}"},
                        )
                    )
                    ch.basic_ack(delivery_tag=method.delivery_tag)
                    foil_holes_decision_complete(body, sess)
                except ValidationError as pve:
                    print(f" [!] Failed to parse Foil Holes Decision Complete body: {pve}")
                    _log_issue(
                        dict(
                            message,
                            **{"issue": f"Failed to parse Foil Holes Decision Complete body: {pve}"},
                        )
                    )
                    ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

            # Events below get triggered by RabbitMQ:
            case MessageQueueEventType.motion_correction_start:
                try:
                    body = MotionCorrectionStartBody(**message)
                    print(f" [+] Motion Correction Start {body}")
                    _log_info(
                        dict(
                            message,
                            **{"info": f"Motion Correction Start {body}"},
                        )
                    )
                    ch.basic_ack(delivery_tag=method.delivery_tag)
                    motion_correction_start(body, sess)
                except ValidationError as pve:
                    print(f" [!] Failed to parse Motion Correction Start body: {pve}")
                    _log_issue(
                        dict(
                            message,
                            **{"issue": f"Failed to parse Motion Correction Start body: {pve}"},
                        )
                    )
                    ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

            case MessageQueueEventType.motion_correction_complete:
                try:
                    body = MotionCorrectionCompleteBody(**message)
                    print(f" [+] Motion Correction Complete {body}")
                    _log_info(
                        dict(
                            message,
                            **{"info": f"Motion Correction Complete {body}"},
                        )
                    )
                    ch.basic_ack(delivery_tag=method.delivery_tag)
                    motion_correction_complete(body, sess)
                except ValidationError as pve:
                    print(f" [!] Failed to parse Motion Correction Complete body: {pve}")
                    _log_issue(
                        dict(
                            message,
                            **{"issue": f"Failed to parse Motion Correction Complete body: {pve}"},
                        )
                    )
                    ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

            case MessageQueueEventType.ctf_start:
                try:
                    body = CtfStartBody(**message)
                    print(f" [+] CTF Start {body}")
                    _log_info(
                        dict(
                            message,
                            **{"info": f"CTF Start {body}"},
                        )
                    )
                    ch.basic_ack(delivery_tag=method.delivery_tag)
                    ctf_start(body, sess)
                except ValidationError as pve:
                    print(f" [!] Failed to parse CTF Start body: {pve}")
                    _log_issue(
                        dict(
                            message,
                            **{"issue": f"Failed to parse CTF Start body: {pve}"},
                        )
                    )
                    ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

            case MessageQueueEventType.ctf_complete:
                try:
                    body = CtfCompleteBody(**message)
                    print(f" [+] CTF Complete {body}")
                    _log_info(
                        dict(
                            message,
                            **{"info": f"CTF Complete {body}"},
                        )
                    )
                    ch.basic_ack(delivery_tag=method.delivery_tag)
                    ctf_complete(body, sess)
                except ValidationError as pve:
                    print(f" [!] Failed to parse CTF Complete body: {pve}")
                    _log_issue(
                        dict(
                            message,
                            **{"issue": f"Failed to parse CTF Complete body: {pve}"},
                        )
                    )
                    ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

            case MessageQueueEventType.particle_picking_start:
                try:
                    body = ParticlePickingStartBody(**message)
                    print(f" [+] Particle Picking Start {body}")
                    _log_info(
                        dict(
                            message,
                            **{"info": f"Particle Picking Start {body}"},
                        )
                    )
                    ch.basic_ack(delivery_tag=method.delivery_tag)
                    particle_picking_start(body, sess)
                except ValidationError as pve:
                    print(f" [!] Failed to parse Particle Picking Start body: {pve}")
                    _log_issue(
                        dict(
                            message,
                            **{"issue": f"Failed to parse Particle Picking Start body: {pve}"},
                        )
                    )
                    ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

            case MessageQueueEventType.particle_picking_complete:
                # Note: only this step will feed back decisions
                try:
                    particle_picking_complete_body = ParticlePickingCompleteBody(**message)
                    print(f" [+] Particle Picking Complete {particle_picking_complete_body}")
                    _log_info(
                        dict(
                            message,
                            **{"info": f"Particle Picking Complete {particle_picking_complete_body}"},
                        )
                    )
                    ch.basic_ack(delivery_tag=method.delivery_tag)
                    particle_picking_complete(body, sess)
                except ValidationError as pve:
                    print(f" [!] Failed to parse Particle Picking Complete body: {pve}")
                    _log_issue(
                        dict(
                            message,
                            **{"issue": f"Failed to parse Particle Picking Complete body: {pve}"},
                        )
                    )
                    ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

            case MessageQueueEventType.particle_selection_start:
                try:
                    body = ParticleSelectionStartBody(**message)
                    print(f" [+] Particle Selection Start {body}")
                    _log_info(
                        dict(
                            message,
                            **{"info": f"Particle Selection Start {body}"},
                        )
                    )
                    ch.basic_ack(delivery_tag=method.delivery_tag)
                    particle_selection_start(body, sess)
                except ValidationError as pve:
                    print(f" [!] Failed to parse Particle Selection Start body: {pve}")
                    _log_issue(
                        dict(
                            message,
                            **{"issue": f"Failed to parse Particle Selection Start body: {pve}"},
                        )
                    )
                    ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

            case MessageQueueEventType.particle_selection_complete:
                try:
                    body = ParticleSelectionCompleteBody(**message)
                    print(f" [+] Particle Selection Complete {body}")
                    _log_info(
                        dict(
                            message,
                            **{"info": f"Particle Selection Complete {body}"},
                        )
                    )
                    ch.basic_ack(delivery_tag=method.delivery_tag)
                    particle_selection_complete(body, sess)
                except ValidationError as pve:
                    print(f" [!] Failed to parse Particle Selection Complete body: {pve}")
                    _log_issue(
                        dict(
                            message,
                            **{"issue": f"Failed to parse Particle Selection Complete body: {pve}"},
                        )
                    )
                    ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

            case MessageQueueEventType.session_end:
                try:
                    body = SessionEndBody(**message)
                    print(f" [+] Session End {body}")
                    _log_info(
                        dict(
                            message,
                            **{"info": f"Session End {body}"},
                        )
                    )
                    ch.basic_ack(delivery_tag=method.delivery_tag)
                    session_end(body, sess)
                except ValidationError as pve:
                    print(f" [!] Failed to parse Session End body: {pve}")
                    _log_issue(
                        dict(
                            message,
                            **{"issue": f"Failed to parse Session End body: {pve}"},
                        )
                    )
                    ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

    sess.close()
    print("\n")


channel.basic_qos(prefetch_count=1)
channel.basic_consume(queue=conf["rabbitmq"]["queue_name"], on_message_callback=on_message)

channel.start_consuming()
