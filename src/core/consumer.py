#!/usr/bin/env python

import os
import pika
import json
import yaml
from dotenv import load_dotenv

load_dotenv()

from pydantic import ValidationError
from schemas.mq_event import (
    MessageQueueEventType,
    MotionCorrectionCompleteBody,
    ParticlePickingCompleteBody,
    ParticleSelectionCompleteBody,
)
from logging import LogRecord
from inspect import currentframe, getframeinfo
from plugin_logging import GraylogUDPHandler

conf = yaml.safe_load(open(os.path.join(os.path.dirname(__file__), "config.yaml")))

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
assert (
    os.getenv("RABBITMQ_PASSWORD") is not None
), "Could not get env var RABBITMQ_PASSWORD"
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


def on_message(ch, method, properties, body):
    print(f" [I] Received message with props={properties} and body: {body.decode()}")
    message = json.loads(
        body.decode()
    )  # TODO assumption of valid JSON here, handle mal-formed

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
        _log_issue(
            dict(message, **{"issue": "Message event_type value not recognised"})
        )
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        print("\n")
        return

    match event_type:
        # Events below are triggered by a fs watcher on the EPU side:
        case MessageQueueEventType.session_start:
            pass
        case MessageQueueEventType.session_pause:
            pass
        case MessageQueueEventType.session_resume:
            pass
        case MessageQueueEventType.session_end:
            pass
        case MessageQueueEventType.grid_scan_start:
            pass
        case MessageQueueEventType.grid_scan_complete:
            pass
        case MessageQueueEventType.grid_squares_decision_start:
            pass
        case MessageQueueEventType.grid_squares_decision_complete:
            pass
        case MessageQueueEventType.foil_holes_detected:
            pass
        case MessageQueueEventType.foil_holes_decision_start:
            pass
        case MessageQueueEventType.foil_holes_decision_complete:
            pass
        # Events below get triggered by RabbitMQ:
        case MessageQueueEventType.motion_correction_start:
            pass
        case MessageQueueEventType.motion_correction_complete:
            try:
                motion_correction_complete_body = MotionCorrectionCompleteBody(
                    **message
                )
                print(
                    f" [+] Motion Correction Complete {motion_correction_complete_body}"
                )
                _log_info(
                    dict(
                        message,
                        **{
                            "info": f"Motion Correction Complete {motion_correction_complete_body}"
                        },
                    )
                )
                ch.basic_ack(delivery_tag=method.delivery_tag)
            except ValidationError as pve:
                print(f" [!] Failed to parse Motion Correction Complete body: {pve}")
                _log_issue(
                    dict(
                        message,
                        **{
                            "issue": f"Failed to parse Motion Correction Complete body: {pve}"
                        },
                    )
                )
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        case MessageQueueEventType.ctf_start:
            pass
        case MessageQueueEventType.ctf_complete:
            pass
        case MessageQueueEventType.particle_picking_start:
            pass
        case MessageQueueEventType.particle_picking_complete:
            # Note: only this step will feed back decisions
            try:
                particle_picking_complete_body = ParticlePickingCompleteBody(**message)
                print(
                    f" [+] Particle Picking Complete {particle_picking_complete_body}"
                )
                _log_info(
                    dict(
                        message,
                        **{
                            "info": f"Particle Picking Complete {particle_picking_complete_body}"
                        },
                    )
                )
                ch.basic_ack(delivery_tag=method.delivery_tag)
            except ValidationError as pve:
                print(f" [!] Failed to parse Particle Picking Complete body: {pve}")
                _log_issue(
                    dict(
                        message,
                        **{
                            "issue": f"Failed to parse Particle Picking Complete body: {pve}"
                        },
                    )
                )
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        case MessageQueueEventType.particle_selection_start:
            pass
        case MessageQueueEventType.particle_selection_complete:
            try:
                particle_selection_complete_body = ParticleSelectionCompleteBody(
                    **message
                )
                print(
                    f" [+] Particle Selection Complete {particle_selection_complete_body}"
                )
                _log_info(
                    dict(
                        message,
                        **{
                            "info": f"Particle Selection Complete {particle_selection_complete_body}"
                        },
                    )
                )
                ch.basic_ack(delivery_tag=method.delivery_tag)
            except ValidationError as pve:
                print(f" [!] Failed to parse Particle Selection Complete body: {pve}")
                _log_issue(
                    dict(
                        message,
                        **{
                            "issue": f"Failed to parse Particle Selection Complete body: {pve}"
                        },
                    )
                )
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

    print("\n")


channel.basic_qos(prefetch_count=1)
channel.basic_consume(
    queue=conf["rabbitmq"]["queue_name"], on_message_callback=on_message
)

channel.start_consuming()
