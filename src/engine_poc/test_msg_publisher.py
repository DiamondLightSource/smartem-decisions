import json
import yaml
import os
import pika
import typer
from dotenv import load_dotenv
from pika.exchange_type import ExchangeType

from domain_entities import MessageQueueEventType, MessageQueueEventHeaders

load_dotenv()
conf = yaml.safe_load(open(os.path.join(os.path.dirname(__file__), 'config.yaml')))

class RabbitMQBlockingTestPublisher:
    APP_ID = conf['rabbitmq']['app_id'] or 'example-workflow-1'
    EXCHANGE = conf['rabbitmq']['exchange'] or 'smartem_decisions'
    EXCHANGE_TYPE = ExchangeType.topic
    QUEUE_NAME = conf['rabbitmq']['queue_name'] or 'default_queue'
    ROUTING_KEY = conf['rabbitmq']['routing_key'] or 'example.text'

    def __init__(self):
        self.connection = None
        self.channel = None
        self._connect()

    def _connect(self):
        parameters = pika.ConnectionParameters(
            host=os.getenv('RABBITMQ_HOST'),
            port=int(os.getenv('RABBITMQ_PORT')),
            credentials=pika.PlainCredentials(
                os.getenv('RABBITMQ_USER'),
                os.getenv('RABBITMQ_PASSWORD')
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
def simulate_external_session_start():
    test_publisher.publish_test_message(
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
def simulate_external_grid_scan_complete():
    test_publisher.publish_test_message(
        headers=MessageQueueEventHeaders(
            event_type=MessageQueueEventType.grid_scan_complete
        ),
        body={
            'session_id': 'xx-xx-xx'
        }
    )

"""
Simulate an ill-formed message with no valid recipient, i.e. headers
fail to specify a valid `event_type` making it impossible to route the
message to the correct consumer.
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
Simulate a "motion capture and CTF" message to test workflow response.
"""
@cli_app.command()
def motion_correct_and_ctf(valid: bool = True):
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

