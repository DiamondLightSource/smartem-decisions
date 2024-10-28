import functools
import logging
import json
import pika
from pika.exchange_type import ExchangeType

LOG_FORMAT = ('%(levelname) -10s %(asctime)s %(name) -30s %(funcName) '
              '-35s %(lineno) -5d: %(message)s')
LOGGER = logging.getLogger(__name__)


class AsyncWorker(object):
  """This is a combined consumer-publisher worker that will handle unexpected
  interactions with RabbitMQ such as channel and connection closures.
  refs:
  - https://github.com/pika/pika/blob/main/examples/asynchronous_consumer_example.py
  - https://github.com/pika/pika/blob/main/examples/asynchronous_publisher_example.py

  If RabbitMQ closes the connection, this class will stop and indicate
  that reconnection is necessary. You should look at the output, as
  there are limited reasons why the connection may be closed, which
  usually are tied to permission related issues or socket timeouts.

  If the channel is closed, it will indicate a problem with one of the
  commands that were issued and that should surface in the output as well.

  It uses delivery confirmations and illustrates one way to keep track of
  messages that have been sent and if they've been confirmed by RabbitMQ.

  """
  EXCHANGE = 'cryoem_decision_engine'
  EXCHANGE_TYPE = ExchangeType.topic
  PUBLISH_INTERVAL = 3
  QUEUE = 'default_queue'
  ROUTING_KEY = 'example.text'

  def __init__(self, amqp_url):
    self.should_reconnect = False
    self.was_consuming = False

    self._connection = None
    self._channel = None
    self._closing = False
    self._consumer_tag = None
    self._url = amqp_url
    self._consuming = False

    self._deliveries = None
    self._acked = None
    self._nacked = None
    self._message_number = None

    self._stopping = False # TODO confirm this is different to `self._closing`

    # In production, experiment with higher prefetch values
    # for higher consumer throughput
    self._prefetch_count = 1

  def connect(self):
    """This method connects to RabbitMQ, returning the connection handle.
    When the connection is established, the on_connection_open method
    will be invoked by pika.

    :rtype: pika.SelectConnection

    """
    LOGGER.info('Connecting to %s', self._url)
    return pika.SelectConnection(
      pika.URLParameters(self._url),
      on_open_callback=self.on_connection_open,
      on_open_error_callback=self.on_connection_open_error,
      on_close_callback=self.on_connection_closed)

  def close_connection(self):
    self._consuming = False
    if self._connection.is_closing or self._connection.is_closed:
      LOGGER.info('Connection is closing or already closed')
    else:
      LOGGER.info('Closing connection')
      self._connection.close()

  def reconnect(self): # TODO found in consumer but not in publisher
    """Will be invoked if the connection can't be opened or is
    closed. Indicates that a reconnect is necessary then stops the
    ioloop.

    """
    self.should_reconnect = True
    self.stop()

  def on_connection_open(self, _unused_connection):
    """This method is called by pika once the connection to RabbitMQ has
    been established. It passes the handle to the connection object in
    case we need it, but in this case, we'll just mark it unused.

    :param pika.SelectConnection _unused_connection: The connection

    """
    LOGGER.info('Connection opened')
    self.open_channel()

  def on_connection_open_error(self, _unused_connection, err):
    """This method is called by pika if the connection to RabbitMQ
    can't be established.

    :param pika.SelectConnection _unused_connection: The connection
    :param Exception err: The error

    """
    LOGGER.error('Connection open failed, reopening in 5 seconds: %s', err)
    self._connection.ioloop.call_later(5, self._connection.ioloop.stop) # in producer example,
    # TODO but self.reconnect() in consumer example

  def on_connection_closed(self, _unused_connection, reason):
    """This method is invoked by pika when the connection to RabbitMQ is
    closed unexpectedly. Since it is unexpected, we will reconnect to
    RabbitMQ if it disconnects.

    :param pika.connection.Connection connection: The closed connection obj
    :param Exception reason: exception representing reason for loss of
        connection.

    """
    self._channel = None
    if self._stopping:
      self._connection.ioloop.stop()
    else:
      LOGGER.warning('Connection closed, reopening in 5 seconds: %s',
                     reason)
      self._connection.ioloop.call_later(5, self._connection.ioloop.stop) # in producer example,
    # TODO but self.reconnect() in consumer example

  def open_channel(self):
    """Open a new channel with RabbitMQ by issuing the Channel.Open RPC
    command. When RabbitMQ responds that the channel is open, the
    on_channel_open callback will be invoked by pika.

    """
    LOGGER.info('Creating a new channel')
    self._connection.channel(on_open_callback=self.on_channel_open)

  def on_channel_open(self, channel):
    """This method is invoked by pika when the channel has been opened.
    The channel object is passed in so we can make use of it.

    Since the channel is now open, we'll declare the exchange to use.

    :param pika.channel.Channel channel: The channel object

    """
    LOGGER.info('Channel opened')
    self._channel = channel
    self.add_on_channel_close_callback()
    self.setup_exchange(self.EXCHANGE)

  def add_on_channel_close_callback(self):
    """This method tells pika to call the on_channel_closed method if
    RabbitMQ unexpectedly closes the channel.

    """
    LOGGER.info('Adding channel close callback')
    self._channel.add_on_close_callback(self.on_channel_closed)

  def on_channel_closed(self, channel, reason):
    """Invoked by pika when RabbitMQ unexpectedly closes the channel.
    Channels are usually closed if you attempt to do something that
    violates the protocol, such as re-declare an exchange or queue with
    different parameters. In this case, we'll close the connection
    to shutdown the object.

    :param pika.channel.Channel channel: The closed channel
    :param Exception reason: why the channel was closed

    """
    LOGGER.warning('Channel %i was closed: %s', channel, reason)
    # TODO instead in consumer: `self.close_connection()`
    self._channel = None
    if not self._stopping:
      self._connection.close()

  def setup_exchange(self, exchange_name):
    """Setup the exchange on RabbitMQ by invoking the Exchange.Declare RPC
    command. When it is complete, the on_exchange_declareok method will
    be invoked by pika.

    :param str|unicode exchange_name: The name of the exchange to declare

    """
    LOGGER.info('Declaring exchange: %s', exchange_name)
    # Note: using functools.partial is not required, it is demonstrating
    # how arbitrary data can be passed to the callback when it is called
    cb = functools.partial(
      self.on_exchange_declareok, userdata=exchange_name)
    self._channel.exchange_declare(
      exchange=exchange_name,
      exchange_type=self.EXCHANGE_TYPE,
      callback=cb)

  def on_exchange_declareok(self, _unused_frame, userdata):
    """Invoked by pika when RabbitMQ has finished the Exchange.Declare RPC
    command.

    :param pika.Frame.Method _unused_frame: Exchange.DeclareOk response frame
    :param str|unicode userdata: Extra user data (exchange name)

    """
    LOGGER.info('Exchange declared: %s', userdata)
    self.setup_queue(self.QUEUE)

  def setup_queue(self, queue_name):
    """Setup the queue on RabbitMQ by invoking the Queue.Declare RPC
    command. When it is complete, the on_queue_declareok method will
    be invoked by pika.

    :param str|unicode queue_name: The name of the queue to declare.

    """
    LOGGER.info('Declaring queue %s', queue_name)
    cb = functools.partial(self.on_queue_declareok, userdata=queue_name)
    self._channel.queue_declare(queue=queue_name, callback=cb)

  def on_queue_declareok(self, _unused_frame, userdata):
    """Method invoked by pika when the Queue.Declare RPC call made in
    setup_queue has completed. In this method we will bind the queue
    and exchange together with the routing key by issuing the Queue.Bind
    RPC command. When this command is complete, the on_bindok method will
    be invoked by pika.

    :param pika.frame.Method _unused_frame: The Queue.DeclareOk frame
    :param str|unicode userdata: Extra user data (queue name)

    """
    queue_name = userdata
    LOGGER.info('Binding %s to %s with %s', self.EXCHANGE, queue_name,
                self.ROUTING_KEY)
    cb = functools.partial(self.on_bindok, userdata=queue_name)
    self._channel.queue_bind(
      queue_name,
      self.EXCHANGE,
      routing_key=self.ROUTING_KEY,
      callback=cb)

  def on_bindok(self, _unused_frame, userdata):
    """Invoked by pika when the Queue.Bind method has completed. At this
    point we will set the prefetch count for the channel.

    :param pika.frame.Method _unused_frame: The Queue.BindOk response frame
    :param str|unicode userdata: Extra user data (queue name)

    """
    LOGGER.info('Queue bound: %s', userdata)
    self.set_qos()
    # TODO self.start_publishing() in publisher
    self.start_publishing()

  def set_qos(self):
    """This method sets up the consumer prefetch to only be delivered
    one message at a time. The consumer must acknowledge this message
    before RabbitMQ will deliver another one. You should experiment
    with different prefetch values to achieve desired performance.

    """
    self._channel.basic_qos(
      prefetch_count=self._prefetch_count, callback=self.on_basic_qos_ok)

  def on_basic_qos_ok(self, _unused_frame):
    """Invoked by pika when the Basic.QoS method has completed. At this
    point we will start consuming messages by calling start_consuming
    which will invoke the needed RPC commands to start the process.

    :param pika.frame.Method _unused_frame: The Basic.QosOk response frame

    """
    LOGGER.info('QOS set to: %d', self._prefetch_count)
    self.start_consuming()

  def start_consuming(self):
    """This method sets up the consumer by first calling
    add_on_cancel_callback so that the object is notified if RabbitMQ
    cancels the consumer. It then issues the Basic.Consume RPC command
    which returns the consumer tag that is used to uniquely identify the
    consumer with RabbitMQ. We keep the value to use it when we want to
    cancel consuming. The on_message method is passed in as a callback pika
    will invoke when a message is fully received.

    """
    LOGGER.info('Issuing consumer related RPC commands')
    self.add_on_cancel_callback()
    self._consumer_tag = self._channel.basic_consume(
      self.QUEUE, self.on_message)
    self.was_consuming = True
    self._consuming = True

  def start_publishing(self):
    """This method will enable delivery confirmations and schedule the
    first message to be sent to RabbitMQ

    """
    LOGGER.info('Issuing consumer related RPC commands')
    self.enable_delivery_confirmations()
    self.schedule_next_message()

  def enable_delivery_confirmations(self):
    """Send the Confirm.Select RPC method to RabbitMQ to enable delivery
    confirmations on the channel. The only way to turn this off is to close
    the channel and create a new one.

    When the message is confirmed from RabbitMQ, the
    on_delivery_confirmation method will be invoked passing in a Basic.Ack
    or Basic.Nack method from RabbitMQ that will indicate which messages it
    is confirming or rejecting.

    """
    LOGGER.info('Issuing Confirm.Select RPC command')
    self._channel.confirm_delivery(self.on_delivery_confirmation)

  def on_delivery_confirmation(self, method_frame):
    """Invoked by pika when RabbitMQ responds to a Basic.Publish RPC
    command, passing in either a Basic.Ack or Basic.Nack frame with
    the delivery tag of the message that was published. The delivery tag
    is an integer counter indicating the message number that was sent
    on the channel via Basic.Publish. Here we're just doing housekeeping
    to keep track of stats and remove message numbers that we expect
    a delivery confirmation of from the list used to keep track of messages
    that are pending confirmation.

    :param pika.frame.Method method_frame: Basic.Ack or Basic.Nack frame

    """
    confirmation_type = method_frame.method.NAME.split('.')[1].lower()
    ack_multiple = method_frame.method.multiple
    delivery_tag = method_frame.method.delivery_tag

    LOGGER.info('Received %s for delivery tag: %i (multiple: %s)',
                confirmation_type, delivery_tag, ack_multiple)

    if confirmation_type == 'ack':
      self._acked += 1
    elif confirmation_type == 'nack':
      self._nacked += 1

    del self._deliveries[delivery_tag]

    if ack_multiple:
      for tmp_tag in list(self._deliveries.keys()):
        if tmp_tag <= delivery_tag:
          self._acked += 1
          del self._deliveries[tmp_tag]
    """
    NOTE: at some point you would check self._deliveries for stale
    entries and decide to attempt re-delivery
    """

    LOGGER.info(
      'Published %i messages, %i have yet to be confirmed, '
      '%i were acked and %i were nacked', self._message_number,
      len(self._deliveries), self._acked, self._nacked)

  def schedule_next_message(self):
    """If we are not closing our connection to RabbitMQ, schedule another
    message to be delivered in PUBLISH_INTERVAL seconds.

    """
    LOGGER.info('Scheduling next message for %0.1f seconds',
                self.PUBLISH_INTERVAL)
    self._connection.ioloop.call_later(self.PUBLISH_INTERVAL,
                                       self.publish_message)

  def publish_message(self):
    """If the class is not stopping, publish a message to RabbitMQ,
    appending a list of deliveries with the message number that was sent.
    This list will be used to check for delivery confirmations in the
    on_delivery_confirmations method.

    Once the message has been sent, schedule another message to be sent.
    The main reason I put scheduling in was just so you can get a good idea
    of how the process is flowing by slowing down and speeding up the
    delivery intervals by changing the PUBLISH_INTERVAL constant in the
    class.

    """
    if self._channel is None or not self._channel.is_open:
      return

    hdrs = {'bread': 'loaf', 'cheese': 'cheddar'}
    properties = pika.BasicProperties(app_id='example-publisher',
                                      content_type='application/json',
                                      headers=hdrs)

    message = 'example message body'
    self._channel.basic_publish(self.EXCHANGE, self.ROUTING_KEY,
                                json.dumps(message, ensure_ascii=False),
                                properties)
    self._message_number += 1
    self._deliveries[self._message_number] = True
    LOGGER.info('Published message # %i', self._message_number)
    self.schedule_next_message()

  def add_on_cancel_callback(self):
    """Add a callback that will be invoked if RabbitMQ cancels the consumer
    for some reason. If RabbitMQ does cancel the consumer,
    on_consumer_cancelled will be invoked by pika.

    """
    LOGGER.info('Adding consumer cancellation callback')
    self._channel.add_on_cancel_callback(self.on_consumer_cancelled)

  def on_consumer_cancelled(self, method_frame):
    """Invoked by pika when RabbitMQ sends a Basic.Cancel for a consumer
    receiving messages.

    :param pika.frame.Method method_frame: The Basic.Cancel frame

    """
    LOGGER.info('Consumer was cancelled remotely, shutting down: %r',
                method_frame)
    self._channel.close()

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

  def acknowledge_message(self, delivery_tag):
    """Acknowledge the message delivery from RabbitMQ by sending a
    Basic.Ack RPC method for the delivery tag.

    :param int delivery_tag: The delivery tag from the Basic.Deliver frame

    """
    LOGGER.info('Acknowledging message %s', delivery_tag)
    self._channel.basic_ack(delivery_tag)

  def stop_consuming(self):
    """Tell RabbitMQ that you would like to stop consuming by sending the
    Basic.Cancel RPC command.

    """
    if self._channel:
      LOGGER.info('Sending a Basic.Cancel RPC command to RabbitMQ')
      cb = functools.partial(
        self.on_cancelok, userdata=self._consumer_tag)
      self._channel.basic_cancel(self._consumer_tag, cb)

  def on_cancelok(self, _unused_frame, userdata):
    """This method is invoked by pika when RabbitMQ acknowledges the
    cancellation of a consumer. At this point we will close the channel.
    This will invoke the on_channel_closed method once the channel has been
    closed, which will in-turn close the connection.

    :param pika.frame.Method _unused_frame: The Basic.CancelOk frame
    :param str|unicode userdata: Extra user data (consumer tag)

    """
    self._consuming = False
    LOGGER.info(
      'RabbitMQ acknowledged the cancellation of the consumer: %s',
      userdata)
    self.close_channel()

  def close_channel(self):
    """Call to close the channel with RabbitMQ cleanly by issuing the
    Channel.Close RPC command.

    """
    LOGGER.info('Closing the channel')
    self._channel.close()

  def run(self):
    """Run the example code by connecting and then starting the IOLoop.

    """
    while not self._stopping:
      self._connection = None
      self._deliveries = {}
      self._acked = 0
      self._nacked = 0
      self._message_number = 0

      try:
        self._connection = self.connect()
        self._connection.ioloop.start()
      except KeyboardInterrupt:
        self.stop()
        if (self._connection is not None and
           not self._connection.is_closed):
          self._connection.ioloop.start()

    LOGGER.info('Stopped')

  def stop(self):
    """Cleanly shutdown the connection to RabbitMQ by stopping the consumer
    with RabbitMQ. When RabbitMQ confirms the cancellation, on_cancelok
    will be invoked by pika, which will then closing the channel and
    connection. The IOLoop is started again because this method is invoked
    when CTRL-C is pressed raising a KeyboardInterrupt exception. This
    exception stops the IOLoop which needs to be running for pika to
    communicate with RabbitMQ. All of the commands issued prior to starting
    the IOLoop will be buffered but not processed.

    """
    if not self._closing:
      self._closing = True
      LOGGER.info('Stopping')
      if self._consuming:
        self.stop_consuming()
        self._connection.ioloop.start()
      else:
        self._connection.ioloop.stop()
      LOGGER.info('Stopped')
