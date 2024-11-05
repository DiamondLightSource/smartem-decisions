import json
import pika
import typer
from dotenv import load_dotenv

from domain_entities import MessageQueueEventType, MessageQueueEventHeaders


load_dotenv()
# TODO load app config

def publish_message(headers: MessageQueueEventHeaders, body):
    if self._channel is None or not self._channel.is_open:
        return
    properties = pika.BasicProperties(app_id=self.APP_ID,
                                      content_type='application/json',
                                      headers=headers)

    self._channel.basic_publish(self.EXCHANGE, self.ROUTING_KEY,
                                json.dumps(body, ensure_ascii=False),
                                properties)

"""
Because the session is started manually by the user, and external to the system (on the EPU side)
    we simulate that event here for dev/testing purposes.
TODO define message_headers and message_body in scope of:
    https://github.com/vredchenko/cryoem-decision-engine-poc/issues/3
"""
def simulate_external_session_start(self):
    publish_message(
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
def simulate_external_grid_scan_complete(self):
    pass

"""
Simulate an ill-formed message with no valid recipient
"""
def publish_invalidly_routed_message(): pass

"""
Simulate a well-formed motion capture and CTF message to test workflow response
"""
def publish_motion_correct_and_ctf_valid_message():
    headers = {}
    message = {}

"""
Simulate an ill-formed motion capture and CTF message to test workflow response
"""
def publish_motion_correct_and_ctf_invalid_message():
    headers = {}
    message = {}



def main(name: str, valid: bool = True):
    print(f"Hello {name}, {bool}")


if __name__ == "__main__":
    # TODO inspect env - if we are in production mode - raise exception and return early
    typer.run(main)
