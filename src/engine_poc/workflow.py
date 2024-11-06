import os
import yaml
import logging
from dotenv import load_dotenv
from domain_entities import MessageQueueEventType
from worker import AsyncWorker as RabbitMQAsyncWorker

load_dotenv()
conf = yaml.safe_load(open(os.path.join(os.path.dirname(__file__), 'config.yaml')))
LOGGER = logging.getLogger(__name__)

"""
Current way:
1. User manually starts the process on the microscope side.
    User manually starts the filesystem watcher. The fact of starting new scanning session with
      the microscope is communicated, passing unique session and microscope info (ids and metadata) 
    TBC: So session start event will be communicated to the system externally?
2. User manually works through the workflow until they get to the micrograph (highest res) stage
3. A fs watcher then picks up newly generated data on the file system,
   determines what these files are, rsyncs to our fs (GPFS in out on-site datacenter) and then
   sends a notification to Murfey API (https://github.com/DiamondLightSource/python-murfey).
4. Failure handling: everything gets logged to our graylog instance, and payloads of failed requests
   get dumped to RabbitMQ so making it possible to recover later.

Note: We make use of the Zocalo
processing framework to organize parts of the workflow concerning
managing data transfer from microscope
and detector systems to a facility filesystem for processing. 
"""


class Workflow(RabbitMQAsyncWorker):
    def __init__(self, amqp_url):
        super().__init__(amqp_url)

    def start_publishing(self):
        """This method will enable delivery confirmations and send
        initial "workflow entrypoint" message to RabbitMQ.
        """
        LOGGER.info('Issuing consumer related RPC commands')
        self.enable_delivery_confirmations()

    def on_session_start(self):
        """
        Initialise a record of newly started session with the central storage database,
            recording session metadata (and possibly indexes to relevant fs resources and artifacts).
        """
        pass

    def on_session_pause(self):
        """
        Out of scope initially, TBC if we want to explicitly support suspending and resuming sessions
        """
        pass

    def on_session_resume(self):
        """
        Out of scope initially, TBC if we want to explicitly support suspending and resuming sessions
        """
        ...

    def on_session_end(self):
        """
        Finalise the session (automate deposition at this point?)
        """
        ...

    def on_grid_scan_start(self):
        """
        fs watcher will tell us when this starts - we don't invoke grid scans via Athena API,
        not can we be notified about it from Athena API.
        """

    def on_grid_scan_complete(self):
        """
        Scan atlas and get grid squares. TBC: from CryoEM client API or from filesystem?
          see `doc/metadata_spa_acquisition`

        :param Atlas and Grid Squares (metadata and 25 * ~4k images)
        """
        ...

    def on_grid_squares_decision_start(self):
        """
        Fire off a call to ML, passing a list of grid squares (Atlas?).
        ML routine performs following:
        - filter_grid_squares (Grid Square Decision to filter out junk)
        - prioritise_grid_squares (assign score)
        """
        ...

    def on_grid_squares_decision_complete(self):
        """
        Receives an ordered list of grid squares, ranked;
          Possibly a dismissal threshold OR choose a percentage to reject, or a combo of the two

        Communicate with Athena API with our new grid square scan priorities, after which
          the user needs to manually restart the flow on the microscope side. The user could intervene at this point
          and queue up the squares in the order that's been suggested, or dismiss the suggestion
          and proceed with default routine.
        """
        ...

    # TODO naming - foil holes are not actually detected but are derived from user-provided input
    def on_foil_holes_detected(self):
        """
        User clicks on two adjacent Foil Holes on the Grid Square to generate a grid of Foil Holes
          across the grid square and detect the rest of the foil hole positions.
        """
        ...

    def on_foil_holes_decision_start(self):
        """
        Fire off a call to ML, passing a list of foil holes.
        ML routine performs following:
        - filter_foil_holes (Foil Hole Decision to filter out junk)
        - prioritise_foil_holes (Foil Hole Decision to prioritise order of capture)
          - ...and feed back to further grid scanning and foil hole detection routines (TODO)
        """
        ...

    def on_foil_holes_decision_complete(self):
        """
        Decision on how many shots per foil hole the user wants when dictating acquisition areas,
        this is specified by the user and is out of scope for automation because "it depends" and is subjective.
        Once done they will resume our flow.

        Acquisition areas picked for one foil hole are then applied to all foil holes
        (so acquisition areas are basically Foil Hole coverage).
        """
        ...

    def on_motion_correct_and_ctf_start(self):
        """
        Motion and CTF (Contrast Transfer Function). Already happens on our side (via Murfey API -> Data Processing),
        takes about 15-20 sec. Accepts a multi-frame (movie)
        """
        pass

    def on_motion_correct_and_ctf_complete(self):
        """
        Receives a Micrograph from the multi-frame, along with annotations describing various quality metrics
        for the micrograph. These can influence acquisition order on the foil hole level immediately,
        and accumulate towards changing acquisition order at the grid square level.
        """
        pass

    def on_particle_acquisition_start(self):
        """
        Particle acquisition. An example: https://cryolo.readthedocs.io/en/stable/
        There are a number of these floating around for automating particle picking.
        * This step can take up to 10-15 minutes.
        """
        pass

    def on_particle_acquisition_complete(self):
        """
        At this point we know if our data is useful, meaning we can feed decisions back up the chain
        (e.g. avoiding similar foil holes). Quality metrics can fuel decisions that can be fed back to
        both grid square decisions and foil hole decisions.
        """
        pass

    # TODO confirm that particle picking and particle acquisition are separate steps
    #   There's also particle filtering:
    #   https://github.com/DiamondLightSource/cryoem-services/blob/main/src/cryoemservices/services/select_particles.py
    #   which probably means particle acquisition consists of 2 consecutive steps: filtering then picking. If so - is
    #   there any benefit in discriminating these two steps at the level of MQ semantics or would it be better to
    #   encapsulate both behind a single `acquisition` step?
    def on_particle_picking_start(self):
        """
        Particle Picking Service is part of the data processing pipeline.
        Receives a JSON blob via RabitMQ, is given a path to an image,
            picks on that and produces a list of coordinates of particles on that image.
        That info can then be passed to decision service.
        https://github.com/DiamondLightSource/cryoem-services/blob/main/src/cryoemservices/services/cryolo.py
        """
        ...

    def on_particle_picking_complete(self):
        """
        Particle picking.
        - self.filter_particles()
        - self.prioritise_particles()
        """
        ...

    def on_particle_selection_start(self):
        """Particle selection started.
        """

    def on_particle_selection_complete(self):
        """Particle selection completed.
            Subset selection on what was picked, based on some measure of quality.
        """

    def on_message(self, _unused_channel, basic_deliver, properties, body):
        """
        :param pika.channel.Channel _unused_channel: The channel object
        :param pika.Spec.Basic.Deliver basic_deliver: method
        :param pika.Spec.BasicProperties properties:
        :param bytes body: The message body:
        """
        LOGGER.info('Received message # %s from %s: %s',
                    basic_deliver.delivery_tag, properties, body)

        # TODO Validate `properties.headers` against a Pydantic schema
        #   ref: https://docs.pydantic.dev/latest/concepts/validators/#annotated-validators

        match properties.headers['event_type']:
            # This stuff is triggered bya  fs watcher on the EPU side:
            case MessageQueueEventType.session_start:
                self.on_session_start()
            case MessageQueueEventType.session_pause:
                self.on_session_pause()
            case MessageQueueEventType.session_resume:
                self.on_session_resume()
            case MessageQueueEventType.session_end:
                self.on_session_end()
            case MessageQueueEventType.grid_scan_start:
                self.on_grid_scan_start()
            case MessageQueueEventType.grid_scan_complete:
                self.on_grid_scan_complete()
            case MessageQueueEventType.grid_squares_decision_start:
                self.on_grid_squares_decision_start()
            case MessageQueueEventType.grid_squares_decision_complete:
                self.on_grid_squares_decision_complete()
            case MessageQueueEventType.foil_holes_detected:
                self.on_foil_holes_detected()
            case MessageQueueEventType.foil_holes_decision_start:
                self.on_foil_holes_decision_start()
            case MessageQueueEventType.foil_holes_decision_complete:
                self.on_foil_holes_decision_complete()

            # this stuff gets triggered by RabbitMQ:
            case MessageQueueEventType.motion_correct_and_ctf_start:
                self.on_motion_correct_and_ctf_start()
            case MessageQueueEventType.motion_correct_and_ctf_complete:
                self.on_motion_correct_and_ctf_complete()
            case MessageQueueEventType.particle_picking_start:
                self.on_particle_picking_start()
            case MessageQueueEventType.particle_picking_complete:
                self.on_particle_picking_complete() # only this step will feed back decisions
            case MessageQueueEventType.particle_selection_start:
                self.on_particle_selection_start()
            case MessageQueueEventType.particle_selection_complete:
                self.on_particle_selection_complete()

        # TODO: we should only acknowledge messages which are recognised and valid?
        self.acknowledge_message(basic_deliver.delivery_tag)



class ReconnectingWorker(object):
    """
    This is an example consumer/publisher that will reconnect if the nested
    Consumer/Publisher indicates that a reconnect is necessary.
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
        if self._reconnect_delay > int(conf['rabbitmq']['reconnect_delay_seconds']):
            self._reconnect_delay = int(conf['rabbitmq']['reconnect_delay_seconds'])
        return self._reconnect_delay


def main():
    logging.basicConfig(level=logging.INFO, format=conf['log']['format'])
    amqp_url = (f"amqp://{os.environ['RABBITMQ_USER']}:{os.environ['RABBITMQ_PASSWORD']}@"
                f"{os.environ['RABBITMQ_HOST']}:{os.environ['RABBITMQ_PORT']}/")
    worker = ReconnectingWorker(amqp_url)
    worker.run()


if __name__ == '__main__':
    main()
