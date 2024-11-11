#!/usr/bin/env python
import os
import pika
import typer
import yaml
from dotenv import load_dotenv
load_dotenv()
from schemas import mq_event


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

@simulate_msg_cli.command()
def rouge_message(legit: bool = True):
    """Simulate an ill-formed message with no valid recipient, i.e. headers
    fail to specify a valid `event_type` making it impossible to route the
    message to the correct consumer.
    """
    print('Not implemented')
    pass


@simulate_msg_cli.command()
def external_session_start(legit: bool = True):
    """Because the session is started manually by the user of EPU software,
    it's origin is external to the system.
    """
    print('Not implemented')
    pass

@simulate_msg_cli.command()
def external_grid_scan_start(legit: bool = True):
    """Simulate a grid scan start event (external to the system)
    """
    print('Not implemented')
    pass

@simulate_msg_cli.command()
def external_grid_scan_complete(legit: bool = True):
    """Simulate a grid scan complete event (external to the system)
    """
    print('Not implemented')
    pass

@simulate_msg_cli.command()
def motion_correct_and_ctf_start(legit: bool = True):
    """Simulate a motion capture and CTF start message to test workflow response
    """
    print('Not implemented')
    pass

@simulate_msg_cli.command()
def motion_correct_and_ctf_complete(legit: bool = True):
    """Simulate a Motion capture and CTF complete message to test workflow response
    """
    channel = connection.channel()
    channel.queue_declare(queue=conf['rabbitmq']['queue_name'], durable=True)
    headers = mq_event.MessageQueueEventHeaders(
        event_type=mq_event.MessageQueueEventType.session_start
    )
    message = {}
    channel.basic_publish(
        exchange='',
        routing_key=conf['rabbitmq']['routing_key'],
        body=str(message),
        properties=pika.BasicProperties(
            delivery_mode=pika.DeliveryMode.Persistent
        ))
    print(f" [x] Sent {message}")
    connection.close()
    pass

if __name__ == "__main__":
    simulate_msg_cli()
