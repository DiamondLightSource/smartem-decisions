import json
import logging
from collections.abc import Awaitable, Callable

import aio_pika
from aio_pika import DeliveryMode, Message
from aio_pika.abc import AbstractChannel, AbstractIncomingMessage, AbstractQueue, AbstractRobustConnection

logger = logging.getLogger(__name__)

MessageHandler = Callable[[AbstractIncomingMessage], Awaitable[None]]


class AioPikaConsumer:
    """Async RabbitMQ consumer built on aio-pika.

    Mirrors AioPikaPublisher: connect_robust owns reconnection and heartbeats
    on the event loop. A single event loop owns the connection, so handler
    coroutines can share it safely without the thread-safety concerns that
    pika.BlockingConnection had inside FastAPI's threadpool.
    """

    def __init__(
        self,
        url: str,
        queue_name: str,
        exchange_name: str = "",
        prefetch_count: int = 1,
        heartbeat: int = 60,
    ) -> None:
        self._url = url
        self._queue_name = queue_name
        self._exchange_name = exchange_name
        self._prefetch_count = prefetch_count
        self._heartbeat = heartbeat
        self._connection: AbstractRobustConnection | None = None
        self._channel: AbstractChannel | None = None
        self._queue: AbstractQueue | None = None
        self._consume_task = None

    async def connect(self) -> None:
        if self._connection is not None and not self._connection.is_closed:
            return
        self._connection = await aio_pika.connect_robust(self._url, heartbeat=self._heartbeat)
        channel = await self._connection.channel()
        await channel.set_qos(prefetch_count=self._prefetch_count)
        self._channel = channel
        self._queue = await channel.declare_queue(self._queue_name, durable=True)
        if self._exchange_name:
            exchange = await channel.declare_exchange(self._exchange_name, durable=True)
            await self._queue.bind(exchange, routing_key=self._queue_name)
        logger.info("Connected aio-pika consumer, queue='%s'", self._queue_name)

    @property
    def is_connected(self) -> bool:
        return self._connection is not None and not self._connection.is_closed

    async def consume(self, handler: MessageHandler) -> None:
        """Consume messages from the queue, dispatching each to handler.

        The handler is expected to manage its own ack/nack via
        `async with message.process(...)`. This method runs until cancelled.
        """
        if self._queue is None:
            raise RuntimeError("consume() called before connect()")
        async with self._queue.iterator() as iterator:
            async for message in iterator:
                await handler(message)

    async def requeue_with_retry(self, message: AbstractIncomingMessage, retry_count: int) -> None:
        """Re-publish the message body with an incremented x-retry-count header.

        Matches the retry semantics of the old pika consumer: the original
        message is acked by its `process()` context; a new copy goes back on
        the same queue with the updated header. Caller is responsible for
        deciding whether retry_count still has budget.
        """
        if self._channel is None:
            raise RuntimeError("requeue_with_retry() called before connect()")
        headers = dict(message.headers or {})
        headers["x-retry-count"] = retry_count
        reissue = Message(
            body=message.body,
            headers=headers,
            delivery_mode=DeliveryMode.PERSISTENT,
            content_type=message.content_type or "application/json",
        )
        await self._channel.default_exchange.publish(reissue, routing_key=self._queue_name)

    async def close(self) -> None:
        if self._channel is not None and not self._channel.is_closed:
            await self._channel.close()
        if self._connection is not None and not self._connection.is_closed:
            await self._connection.close()
        self._channel = None
        self._connection = None
        self._queue = None
        logger.info("Closed aio-pika consumer")


def decode_event_body(message: AbstractIncomingMessage) -> dict:
    return json.loads(message.body.decode())
