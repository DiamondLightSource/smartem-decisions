import functools
import logging

LOG_FORMAT = ('%(levelname) -10s %(asctime)s %(name) -30s %(funcName) '
              '-35s %(lineno) -5d: %(message)s')
LOGGER = logging.getLogger(__name__)

from worker import AsyncWorker as RabbitMQAsyncWorker

"""
Current way:
1. User manually starts the process on the microscope side
   User manually starts the filesystem watcher
2. User manually works through the workflow until they get to the micrograph (highest res) stage
3. A fs watcher then picks up newly generated data on the file system,
   determines what these files are, rsyncs to our fs (GPFS in out on-site datacenter) and then
   sends a notification to Murfey API (https://github.com/DiamondLightSource/python-murfey).
4. Failure handling: everything gets logged to our graylog instance, and payloads of failed requests get dumped to RabbitMQ
   so that it can be recovered later.

Note: We make use of the Zocalo
processing framework to organize parts of the workflow concerning
managing data transfer from microscope
and detector systems to a facility filesystem for processing.
"""


class Workflow(RabbitMQAsyncWorker):
    def __init__(self, amqp_url):
        super().__init__(amqp_url)

    """
    Example of running the complete workflow

    publishers:
    - start_session
    - start_grid_scan
    - grid_scan_complete
    - grid_square_decision

    consumers:
    - on_session_start
    - on_start_grid_scan
    - on_grid_scan_complete
    - on_grid_square_decision

    actions:
    - init_session
    - decide_grid_squares
    - athena_api.send_grid_squares_scan_priorities

    """

    """
    User manually starts the process on the microscope side.
    User manually starts the filesystem watcher. The fact of starting new scanning session with
      the microscope is communicated, passing unique session and microscope info (ids and metadata) 
    """

    def start_session(self): ...
        # message = "new session {session_info} started on microscope {device_info}"
        # channel.basic_publish(exchange='',
        #                       routing_key='foo',
        #                       body=message)
        # print(f" [x] Sent {message}")

    """
    Initialise a record of newly started session with the central storage database, recording session metadata
    (and indexes to relevant fs resources and artifacts).
    """

    def init_session(self): ...

    """
    message consumer
    """

    def on_session_start(self):
        self.init_session()

    """
    Scan atlas and get grid squares
    TBC: from CryoEM client API or from filesystem? See `doc/metadata_spa_acquisition`

    @param Atlas and Grid Squares (metadata and 25 * ~4k images) 
    """

    def atlas_scanned_notification_recipient(self):
        # TODO call to init scanning here?
        self.filter_grid_squares()
        self.prioritise_grid_squares()

    """
    Grid Square Decision - filter out junk

    @param list of grid squares
    @return ordered list of grid squares, ranked; possibly a dismissal threshold OR choose a percentage to reject,
      or a combo of the two
    """

    def filter_and_rank_grid_squares(self): pass

    """
    Athena API instruction - provide Athena API with our new grid square scan priorities, after which
      the user needs to manually restart the flow on the microscope side. The user could intervene at this point
      and queue up the squares in the order that's been suggested, or dismiss the suggestion
      and proceed with default routine.

    @param output of `filter_and_rank_grid_squares`
    @return None?
    """

    def prioritise_grid_squares(self):  # TODO rename method
        # invoke Athena API
        pass

    """
    At this point currently user clicks on two adjacent Foil Holes on the Grid Square to generate a grid of Foil Holes
      across the grid square and detect the rest of the foil hole positions.
    """

    def detect_foil_holes(self):
        # Foil Hole detection step?
        # self.filter_foil_holes()
        # self.prioritise_foil_holes()
        pass

    """
    Foil Hole Decision - filter out junk
    """

    def filter_and_rank_foil_holes(self): pass

    """
    Foil Hole Decision - prioritise order of capture - and feed back `scan_atlas` and `detect_foil_holes`?
    """

    def prioritise_foil_holes(self): pass

    """
    Decision on how many shots per Foil Hole they want when dictating acquisition areas, this is specified by the user
    and is out of scope for automation because "it depends" and is subjective. Once do they will resume our flow.

    Acquisition areas picked for one Foil Hole are then applied to all Foil Holes
    (so acquisition areas are basically Foil Hole coverage).
    """

    """
    Motion and CTF (Contrast Transfer Function). Already happens on our side (via Murfey API -> Data Processing),
    takes about 15-20 sec.

    @param Multi-frame movie 
    @return Always a Micrograph from the multi-frame is returned, along with annotations describing:
      - various quality metrics for the micrograph (these can influence acquisition order on the FoilHole level immediately,
        and accumulate towards changing acquisition order at the Grid Square level).
    """

    def correct_motion_and_ctf(self): pass

    """
    Particle picking.
    At this point we know if our data is useful and we can feed back up the chain decisions such as:
        - avoiding similar foil holes
    Quality metrics can fuel decisions that can be fed back to both grid square decisions and foil hole decisions

    Note: check out https://cryolo.readthedocs.io/en/stable/ but there are a number of these floating around for
    automating particle picking.
    """

    def pick_particles(self):
        # An additional step here - particle acquisition? This step can take up to 10-15 mins?
        self.filter_particles()
        self.prioritise_particles()

    """
    Particle picking decision - filter out junk
    """

    def filter_particles(self): pass

    """
    Particle picking decision - prioritise order of capture
    """

    def prioritise_particles(self): pass

    def on_message(self, _unused_channel, basic_deliver, properties, body):
        """Invoked by pika when a message is delivered from RabbitMQ. The
        channel is passed for your convenience. The basic_deliver object that
        is passed in carries the exchange, routing key, delivery tag and
        a redelivered flag for the message. The properties passed in is an
        instance of BasicProperties with the message properties and the body
        is the message that was sent.

        :param pika.channel.Channel _unused_channel: The channel object
        :param pika.Spec.Basic.Deliver: basic_deliver method
        :param pika.Spec.BasicProperties: properties
        :param bytes body: The message body

        """
        LOGGER.info('Received message # %s from %s: %s',
                    basic_deliver.delivery_tag, properties.app_id, body)
        self.acknowledge_message(basic_deliver.delivery_tag)


class ReconnectingWorker(object):
  """This is an example consumer that will reconnect if the nested
  ExampleConsumer indicates that a reconnect is necessary.

  """

  def __init__(self, amqp_url):
    self._reconnect_delay = 0
    self._amqp_url = amqp_url
    self._consumer = Workflow(self._amqp_url)

  def run(self):
    while True:
      try:
        self._consumer.run()
      except KeyboardInterrupt:
        self._consumer.stop()
        break
      self._maybe_reconnect()

  def _maybe_reconnect(self):
    if self._consumer.should_reconnect:
      self._consumer.stop()
      reconnect_delay = self._get_reconnect_delay()
      LOGGER.info('Reconnecting after %d seconds', reconnect_delay)
      time.sleep(reconnect_delay)
      self._consumer = Workflow(self._amqp_url)

  def _get_reconnect_delay(self):
    if self._consumer.was_consuming:
      self._reconnect_delay = 0
    else:
      self._reconnect_delay += 1
    if self._reconnect_delay > 30:
      self._reconnect_delay = 30
    return self._reconnect_delay



def main():
  logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
  amqp_url = 'amqp://user:password@localhost:5672/%2F'
  worker = ReconnectingWorker(amqp_url)
  worker.run()


if __name__ == '__main__':
  main()
