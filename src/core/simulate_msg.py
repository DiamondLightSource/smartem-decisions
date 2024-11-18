#!/usr/bin/env python

import os
import pika
import typer
import yaml
import json
from dotenv import load_dotenv

from schemas.mq_event import MessageQueueEventType

load_dotenv()
from uuid import uuid4

simulate_msg_cli = typer.Typer()
conf = yaml.safe_load(open(os.path.join(os.path.dirname(__file__), 'config.yaml')))

connection = pika.BlockingConnection(
    pika.ConnectionParameters(
        host=os.getenv('RABBITMQ_HOST'),
        port=int(os.getenv('RABBITMQ_PORT')),
        credentials=pika.PlainCredentials(
            os.getenv('RABBITMQ_USER'),
            os.getenv('RABBITMQ_PASSWORD')
        )
    ))

def _send_msg(msg):
    channel = connection.channel()
    channel.queue_declare(queue=conf['rabbitmq']['queue_name'], durable=True)
    channel.basic_publish(
        exchange='',
        routing_key=conf['rabbitmq']['routing_key'],
        body=json.dumps(msg),
        properties=pika.BasicProperties(
            delivery_mode=pika.DeliveryMode.Persistent
        ))
    print(f" [x] Sent {msg}")
    connection.close()


@simulate_msg_cli.command()
def rogue_message(event_type_missing: bool = False):
    """Simulate an ill-formed message with no valid recipient,
    either `event_type` parameter taking on an unrecognised value or missing entirely -
    making it impossible to route the message to the correct consumer.
    """
    message = {
        'event_type': 'foo bar',
    } if event_type_missing else {
        'micrograph_id': str(uuid4()),
        'total_motion': 0.123,
        'average_motion': 0.006,
        'ctf_max_resolution_estimate': 0.123123,
    }
    _send_msg(message)

@simulate_msg_cli.command()
def external_session_start(legit: bool = True):
    print('Not implemented')

@simulate_msg_cli.command()
def external_grid_scan_start(legit: bool = True):
    print('Not implemented')

@simulate_msg_cli.command()
def external_grid_scan_complete(legit: bool = True):
    print('Not implemented')

@simulate_msg_cli.command()
def motion_correction_start(legit: bool = True):
    print('Not implemented')

@simulate_msg_cli.command()
def motion_correction_complete(legit: bool = True):
    message = {
        'event_type': str(MessageQueueEventType.motion_correction_complete.value),
        'micrograph_id': str(uuid4()),
        'total_motion': 0.123,
        'average_motion': 0.006,
        'ctf_max_resolution_estimate': 0.123123,
    } if legit else {
        'event_type': str(MessageQueueEventType.motion_correction_complete.value),
        'micrograf_id': 'xx',
        'total_lotion': None,
        'averag_emotion': -0.006,
        'ctf_max_revolution_estimate': '0.123123',
    }
    _send_msg(message)

@simulate_msg_cli.command()
def particle_picking_start(legit: bool = True):
    print('Not implemented')

@simulate_msg_cli.command()
def particle_picking_complete(legit: bool = True):
    message = {
        'event_type': str(MessageQueueEventType.particle_picking_complete.value),
        'micrograph_id': str(uuid4()),
        'number_of_particles_picked': 10,
        'pick_distribution': {} # TODO
    } if legit else {
        'event_type': str(MessageQueueEventType.particle_picking_complete.value),
        'micrograf_id': 'xx',
        'number_of_particles_picked': -10,
        'pick_distribution': None,
    }
    _send_msg(message)

@simulate_msg_cli.command()
def particle_selection_start(legit: bool = True):
    print('Not implemented')

@simulate_msg_cli.command()
def particle_selection_complete(legit: bool = True):
    message = {
        'event_type': str(MessageQueueEventType.particle_selection_complete.value),
        'micrograph_id': str(uuid4()),
        'number_of_particles_selected': 0,
        'selection_distribution': {}  # TODO
    } if legit else {
        'event_type': str(MessageQueueEventType.particle_selection_complete.value),
        'micrograf_id': 'xx',
        'number_of_particles_selected': -10,
        'selection_distribution': None,
    }
    _send_msg(message)

@simulate_msg_cli.command()
def ctf_start(legit: bool = True):
    print('Not implemented')

@simulate_msg_cli.command()
def ctf_complete(legit: bool = True):
    print('Not implemented')

if __name__ == "__main__":
    simulate_msg_cli()
