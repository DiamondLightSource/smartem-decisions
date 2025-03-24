#!/usr/bin/env python

import json
import os
from uuid import uuid4
import time

import pika
import typer
import yaml
from dotenv import load_dotenv

from smartem_decisions.utils import load_conf
from smartem_decisions.model.mq_event import MessageQueueEventType

load_dotenv()
conf = load_conf()

simulate_msg_cli = typer.Typer()

# Load the config file
try:
    with open(os.path.join(os.path.dirname(__file__), "config.yaml")) as f:
        conf = yaml.safe_load(f)
except Exception as e:
    print(f"Error loading config file: {e}")
    conf = {"rabbitmq": {"queue_name": "smartem_events", "routing_key": "smartem_events"}}

# Check for required environment variables
assert os.getenv("RABBITMQ_HOST") is not None, "Could not get env var RABBITMQ_HOST"
assert os.getenv("RABBITMQ_PORT") is not None, "Could not get env var RABBITMQ_PORT"
assert os.getenv("RABBITMQ_USER") is not None, "Could not get env var RABBITMQ_USER"
assert os.getenv("RABBITMQ_PASSWORD") is not None, "Could not get env var RABBITMQ_PASSWORD"


def get_connection(max_retries=3, retry_delay=2):
    """
    Create and return a connection to RabbitMQ with retry logic.
    
    Args:
        max_retries: Maximum number of connection attempts
        retry_delay: Delay between retries in seconds
        
    Returns:
        A pika.BlockingConnection object
        
    Raises:
        pika.exceptions.AMQPConnectionError: If connection cannot be established after retries
    """
    connection_params = pika.ConnectionParameters(
        host=os.getenv("RABBITMQ_HOST"),  # type: ignore
        port=int(os.getenv("RABBITMQ_PORT")),  # type: ignore
        credentials=pika.PlainCredentials(
            os.getenv("RABBITMQ_USER"),  # type: ignore
            os.getenv("RABBITMQ_PASSWORD"),  # type: ignore
        ),
    )
    
    for attempt in range(max_retries):
        try:
            print(f"Attempting to connect to RabbitMQ (attempt {attempt + 1}/{max_retries})...")
            connection = pika.BlockingConnection(connection_params)
            print("Successfully connected to RabbitMQ")
            return connection
        except pika.exceptions.AMQPConnectionError as e:
            if attempt < max_retries - 1:
                print(f"Connection failed: {e}. Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
            else:
                print(f"Failed to connect to RabbitMQ after {max_retries} attempts")
                raise
        except Exception as e:
            print(f"Unexpected error while connecting to RabbitMQ: {e}")
            raise


def _send_msg(msg):
    """
    Send a message to RabbitMQ
    
    Args:
        msg: The message to send
        
    Raises:
        Exception: If the message cannot be sent
    """
    connection = None
    try:
        # Get a connection with retry logic
        connection = get_connection()
        
        # Create a channel and declare the queue
        channel = connection.channel()
        channel.queue_declare(queue=conf["rabbitmq"]["queue_name"], durable=True)
        
        # Publish the message
        channel.basic_publish(
            exchange="",
            routing_key=conf["rabbitmq"]["routing_key"],
            body=json.dumps(msg),
            properties=pika.BasicProperties(delivery_mode=pika.DeliveryMode.Persistent),
        )
        print(f" [x] Sent {msg}")
    except pika.exceptions.AMQPConnectionError as e:
        print(f"AMQP Connection Error: {e}")
        raise
    except pika.exceptions.AMQPChannelError as e:
        print(f"AMQP Channel Error: {e}")
        raise
    except Exception as e:
        print(f"Error sending message: {e}")
        raise
    finally:
        # Ensure connection is closed even if an exception occurs
        if connection is not None and connection.is_open:
            try:
                connection.close()
                print("Connection closed")
            except Exception as e:
                print(f"Error closing connection: {e}")


@simulate_msg_cli.command()
def rogue_message(event_type_missing: bool = False):
    """Simulates an ill-formed message with no valid recipient,
    either `event_type` parameter taking on an unrecognised value or missing entirely -
    making it impossible to route the message to the correct consumer.
    """
    message = (
        {
            "event_type": "foo bar",
        }
        if event_type_missing
        else {
            "some": "nonsense",
            "data": False,
            "meaning of life the world and everything": 6 * 7,
        }
    )
    _send_msg(message)


@simulate_msg_cli.command()
def acquisition_start(legit: bool = True):
    """Simulates initiation of a new microscopy session"""
    message = (
        {
            "event_type": str(MessageQueueEventType.ACQUISITION_START.value),
            "name": "Untitled Session 02",
            "epu_id": str(uuid4()),
        }
        if legit
        else {
            "event_type": str(MessageQueueEventType.ACQUISITION_START.value),
            "title": "Untitled 01",
        }
    )
    _send_msg(message)


@simulate_msg_cli.command()
def grid_scan_start(legit: bool = True):
    """Simulates start of a grid scan"""
    message = (
        {
            "event_type": str(MessageQueueEventType.GRID_SCAN_START.value),
            "grid_id": 1,
        }
        if legit
        else {
            "event_type": str(MessageQueueEventType.GRID_SCAN_START.value),
            "grit_id": "just plain wrong",
        }
    )
    _send_msg(message)


@simulate_msg_cli.command()
def grid_scan_complete(legit: bool = True):
    """Simulates end of a grid scan
    TODO: mock grid squares information
    """
    message = (
        {
            "event_type": str(MessageQueueEventType.GRID_SCAN_COMPLETE.value),
            "grid_id": 1,
        }
        if legit
        else {
            "event_type": str(MessageQueueEventType.GRID_SCAN_COMPLETE.value),
            "grit_id": "just plain wrong",
        }
    )
    _send_msg(message)


@simulate_msg_cli.command()
def grid_squares_decision_start(legit: bool = True):
    """Simulates start of grid squares decision"""
    message = (
        {
            "event_type": str(MessageQueueEventType.GRID_SQUARES_DECISION_START.value),
            "grid_id": 1,
        }
        if legit
        else {
            "event_type": str(MessageQueueEventType.GRID_SQUARES_DECISION_START.value),
            "grit_id": "just plain wrong",
        }
    )
    _send_msg(message)


@simulate_msg_cli.command()
def grid_squares_decision_complete(legit: bool = True):
    """Simulates end of grid squares decision
    TODO: mock grid squares decision information
    """
    message = (
        {
            "event_type": str(MessageQueueEventType.GRID_SQUARES_DECISION_COMPLETE.value),
            "grid_id": 1,
        }
        if legit
        else {
            "event_type": str(MessageQueueEventType.GRID_SQUARES_DECISION_COMPLETE.value),
            "grit_id": "just plain wrong",
        }
    )
    _send_msg(message)


@simulate_msg_cli.command()
def foil_holes_detected(legit: bool = True):
    """Simulates foil hole detection
    TODO supply actual foilhole mock data
    """
    message = (
        {
            "event_type": str(MessageQueueEventType.FOIL_HOLES_DETECTED.value),
            "grid_id": 1,
        }
        if legit
        else {
            "event_type": str(MessageQueueEventType.FOIL_HOLES_DETECTED.value),
            "grit_id": "just plain wrong",
        }
    )
    _send_msg(message)


@simulate_msg_cli.command()
def foil_holes_decision_start(legit: bool = True):
    """Simulates foil hole decision start"""
    message = (
        {
            "event_type": str(MessageQueueEventType.FOIL_HOLES_DECISION_START.value),
            "gridsquare_id": 1,
        }
        if legit
        else {
            "event_type": str(MessageQueueEventType.FOIL_HOLES_DECISION_START.value),
            "gritcircle_id": "just plain wrong",
        }
    )
    _send_msg(message)


@simulate_msg_cli.command()
def foil_holes_decision_complete(legit: bool = True):
    # TODO supply actual foilhole decision mock data
    """Simulates foil hole decision start"""
    message = (
        {
            "event_type": str(MessageQueueEventType.FOIL_HOLES_DECISION_COMPLETE.value),
            "gridsquare_id": 1,
        }
        if legit
        else {
            "event_type": str(MessageQueueEventType.FOIL_HOLES_DECISION_COMPLETE.value),
            "gritcircle_id": "just plain wrong",
        }
    )
    _send_msg(message)


@simulate_msg_cli.command()
def micrographs_detected(legit: bool = True):
    """Simulates micrograph detection
    TODO supply actual micrograph mock data
    """
    message = (
        {
            "event_type": str(MessageQueueEventType.MICROGRAPHS_DETECTED.value),
            "foilhole_id": 1,
        }
        if legit
        else {
            "event_type": str(MessageQueueEventType.MICROGRAPHS_DETECTED.value),
            "pothole_id": "just plain wrong",
        }
    )
    _send_msg(message)


@simulate_msg_cli.command()
def motion_correction_start(legit: bool = True):
    """Simulates micrograph motion correction start"""
    message = (
        {
            "event_type": str(MessageQueueEventType.MOTION_CORRECTION_START.value),
            "micrograph_id": 1,
        }
        if legit
        else {
            "event_type": str(MessageQueueEventType.MOTION_CORRECTION_START.value),
            "micrograf_id": "just plain wrong",
        }
    )
    _send_msg(message)


@simulate_msg_cli.command()
def motion_correction_complete(legit: bool = True):
    """Simulates micrograph motion correction completion"""
    message = (
        {
            "event_type": str(MessageQueueEventType.MOTION_CORRECTION_COMPLETE.value),
            "micrograph_id": 1,
            "total_motion": 0.123,
            "average_motion": 0.006,
            "ctf_max_resolution_estimate": 0.123123,  # TODO should this be ctf?
        }
        if legit
        else {
            "event_type": str(MessageQueueEventType.MOTION_CORRECTION_COMPLETE.value),
            "micrograf_id": str(uuid4()),
            "total_lotion": None,
            "averag_emotion": -0.006,
            "ctf_max_revolution_estimate": "0.123123",
        }
    )
    _send_msg(message)


@simulate_msg_cli.command()
def ctf_start(legit: bool = True):
    """Simulates micrograph CTF start"""
    message = (
        {
            "event_type": str(MessageQueueEventType.CTF_START.value),
            "micrograph_id": 1,
        }
        if legit
        else {
            "event_type": str(MessageQueueEventType.CTF_START.value),
            "micrograf_id": "just plain wrong",
        }
    )
    _send_msg(message)


@simulate_msg_cli.command()
def ctf_complete(legit: bool = True):
    """Simulates micrograph ctf completion"""
    message = (
        {
            "event_type": str(MessageQueueEventType.CTF_COMPLETE.value),
            "micrograph_id": 1,
            "total_motion": 0.123,
            "average_motion": 0.321,
            "ctf_max_resolution_estimate": 0.897,
        }
        if legit
        else {
            "event_type": str(MessageQueueEventType.CTF_COMPLETE.value),
            "micrograf_id": "just plain wrong",
        }
    )
    _send_msg(message)


@simulate_msg_cli.command()
def particle_picking_start(legit: bool = True):
    """Simulates the start of particle picking process"""
    message = (
        {
            "event_type": str(MessageQueueEventType.PARTICLE_PICKING_START.value),
            "micrograph_id": 1,
        }
        if legit
        else {
            "event_type": str(MessageQueueEventType.PARTICLE_PICKING_START.value),
            "micrograf_id": "just plain wrong",
        }
    )
    _send_msg(message)


@simulate_msg_cli.command()
def particle_picking_complete(legit: bool = True):
    """Simulates completion of particle picking process"""
    message = (
        {
            "event_type": str(MessageQueueEventType.PARTICLE_PICKING_COMPLETE.value),
            "micrograph_id": 1,
            "number_of_particles_picked": 10,
            "pick_distribution": {},  # TODO
        }
        if legit
        else {
            "event_type": str(MessageQueueEventType.PARTICLE_PICKING_COMPLETE.value),
            "micrograf_id": str(uuid4()),
            "number_of_particles_picked": -10,
            "pick_distribution": None,
        }
    )
    _send_msg(message)


@simulate_msg_cli.command()
def particle_selection_start(legit: bool = True):
    """Simulates the start of particle selection process"""
    message = (
        {
            "event_type": str(MessageQueueEventType.PARTICLE_SELECTION_START.value),
            "micrograph_id": 1,
        }
        if legit
        else {
            "event_type": str(MessageQueueEventType.PARTICLE_SELECTION_START.value),
            "micrograf_id": "just plain wrong",
        }
    )
    _send_msg(message)


@simulate_msg_cli.command()
def particle_selection_complete(legit: bool = True):
    """Simulates completion of particle selection process"""
    message = (
        {
            "event_type": str(MessageQueueEventType.PARTICLE_SELECTION_COMPLETE.value),
            "micrograph_id": 1,
            "number_of_particles_selected": 0,
            "number_of_particles_rejected": 10,
            "selection_distribution": {},  # TODO
        }
        if legit
        else {
            "event_type": str(MessageQueueEventType.PARTICLE_SELECTION_COMPLETE.value),
            "micrograf_id": str(uuid4()),
            "number_of_particles_selected": -10,
            "number_of_particles_rejected": 10,
            "selection_distribution": None,
        }
    )
    _send_msg(message)


@simulate_msg_cli.command()
def acquisition_end(legit: bool = True):
    """Simulates acquisition finalisation"""
    message = (
        {
            "event_type": str(MessageQueueEventType.ACQUISITION_END.value),
            "session_id": 1,
        }
        if legit
        else {
            "event_type": str(MessageQueueEventType.ACQUISITION_END.value),
            "sess_id": str(uuid4()),
        }
    )
    _send_msg(message)


if __name__ == "__main__":
    simulate_msg_cli()
