import json
import os
import pika
import typer
from typing import Optional
from dotenv import load_dotenv
from pika.exchange_type import ExchangeType

from domain_entities import MessageQueueEventType, MessageQueueEventHeaders

load_dotenv()
# TODO load app config

class RabbitMQBlockingTestPublisher:
    EXCHANGE = 'smartem_decisions'
    EXCHANGE_TYPE = ExchangeType.topic
    QUEUE_NAME = 'default_queue'
    ROUTING_KEY = 'example.text'
    APP_ID = 'example-workflow'  # Assuming we would never use it. ref: https://stackoverflow.com/a/53518634

    def __init__(self):
        self.connection = None
        self.channel = None
        self._connect()

    def _connect(self):
        parameters = pika.ConnectionParameters(
            host=os.getenv('RABBITMQ_HOST', 'localhost'),
            port=int(os.getenv('RABBITMQ_PORT', 5672)),
            credentials=pika.PlainCredentials(
                os.getenv('RABBITMQ_USER', 'user'),
                os.getenv('RABBITMQ_PASSWORD', 'password')
            )
        )
        self.connection = pika.BlockingConnection(parameters)
        self.channel = self.connection.channel()
        self.channel.queue_declare(queue=self.QUEUE_NAME)

    def _close(self):
        if self.connection and not self.connection.is_closed:
            self.connection.close()

    def _publish(self, headers, body):
        if not self.channel:
            raise Exception("Connection is not established.")
        self.channel.basic_publish(
            exchange=self.EXCHANGE,
            routing_key=self.QUEUE_NAME,
            body=json.dumps(body, ensure_ascii=True),
            properties=pika.BasicProperties(
                app_id=self.APP_ID,
                content_type='application/json',
                headers=headers,
                delivery_mode=2,  # make message persistent
            )
        )

    def publish_test_message(self, headers, body):
        try:
            self._publish(headers, body)
            print(f"Sent message to queue {self.QUEUE_NAME}; headers: {headers}; body: {body}")
        except Exception as e:
            print(f"Failed to publish test message: {e}")
        finally:
            self._close()


cli_app = typer.Typer()

"""
Because the session is started manually by the user, and external to the system (on the EPU side)
we simulate that event here for dev/testing purposes.
"""
@cli_app.command()
def simulate_external_session_start(self):
    self.publish_test_message(
        headers = MessageQueueEventHeaders(
            event_type = MessageQueueEventType.session_start
        ),
        body = {
            'session_id': 'xx-xx-xx'
        }
    )

"""
Simulate a grid scan complete event (external to the system)
"""
@cli_app.command()
def simulate_external_grid_scan_complete(self):
    self.publish_test_message(
        headers=MessageQueueEventHeaders(
            event_type=MessageQueueEventType.grid_scan_complete
        ),
        body={
            'session_id': 'xx-xx-xx'
        }
    )

"""
Simulate an ill-formed message with no valid recipient
"""
@cli_app.command()
def invalidly_routed_message():
    test_publisher.publish_test_message(
        headers=MessageQueueEventHeaders(
            event_type=MessageQueueEventType.grid_scan_complete
        ),
        body={
            'session_id': 'xx-xx-xx'
        }
    )

"""
Simulate a motion capture and CTF message to test workflow response.
"""
@cli_app.command()
def motion_correct_and_ctf(valid: Optional[bool] = True):
    valid_body = {
        'session_id': 'xx-xx-xx'
    }
    invalid_body = {
        'malformed_prop': 'or malformed value'
    }
    test_publisher.publish_test_message(
        headers = MessageQueueEventHeaders(
            event_type = MessageQueueEventType.motion_correct_and_ctf_start
        ),
        body = valid_body if valid else invalid_body
    )


if __name__ == "__main__":
    test_publisher = RabbitMQBlockingTestPublisher()
    cli_app()

