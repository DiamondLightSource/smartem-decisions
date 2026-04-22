import json
import logging
from datetime import datetime
from typing import Any

import aio_pika
from aio_pika import DeliveryMode, Message
from aio_pika.abc import AbstractChannel, AbstractExchange, AbstractRobustConnection
from aio_pika.exceptions import DeliveryError
from pydantic import BaseModel

from smartem_backend.model.mq_event import MessageQueueEventType

logger = logging.getLogger(__name__)


class _DateTimeEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, datetime):
            return o.isoformat()
        return super().default(o)


class AioPikaPublisher:
    """Async RabbitMQ publisher built on aio-pika.

    Uses connect_robust so the library owns reconnection. Publisher confirms
    (publisher_confirms=True) give an ack-from-broker guarantee; mandatory=True
    surfaces misrouted messages as DeliveryError rather than silent drops.
    Thread-safe because a single event loop owns the connection.
    """

    def __init__(self, url: str, exchange_name: str, routing_key: str, heartbeat: int = 60) -> None:
        self._url = url
        self._exchange_name = exchange_name
        self._routing_key = routing_key
        self._heartbeat = heartbeat
        self._connection: AbstractRobustConnection | None = None
        self._channel: AbstractChannel | None = None
        self._exchange: AbstractExchange | None = None

    async def connect(self) -> None:
        if self._connection is not None and not self._connection.is_closed:
            return
        self._connection = await aio_pika.connect_robust(self._url, heartbeat=self._heartbeat)
        channel = await self._connection.channel(publisher_confirms=True)
        self._channel = channel
        await channel.declare_queue(self._routing_key, durable=True)
        if self._exchange_name:
            self._exchange = await channel.declare_exchange(self._exchange_name, durable=True)
        else:
            self._exchange = channel.default_exchange
        logger.info("Connected aio-pika publisher, routing_key='%s'", self._routing_key)

    @property
    def is_connected(self) -> bool:
        return self._connection is not None and not self._connection.is_closed

    async def close(self) -> None:
        if self._channel is not None and not self._channel.is_closed:
            await self._channel.close()
        if self._connection is not None and not self._connection.is_closed:
            await self._connection.close()
        self._channel = None
        self._connection = None
        self._exchange = None
        logger.info("Closed aio-pika publisher")

    def _encode(self, event_type: MessageQueueEventType, payload: BaseModel | dict[str, Any]) -> bytes:
        if isinstance(payload, BaseModel):
            payload_dict = json.loads(payload.json())
        else:
            payload_dict = payload
        body = {"event_type": event_type.value, **payload_dict}
        return json.dumps(body, cls=_DateTimeEncoder).encode("utf-8")

    def _message(self, body: bytes) -> Message:
        return Message(body=body, delivery_mode=DeliveryMode.PERSISTENT, content_type="application/json")

    async def publish_event(self, event_type: MessageQueueEventType, payload: BaseModel | dict[str, Any]) -> bool:
        if self._exchange is None:
            logger.error("Publisher not connected when publishing %s", event_type.value)
            return False
        try:
            body = self._encode(event_type, payload)
            await self._exchange.publish(self._message(body), routing_key=self._routing_key, mandatory=True)
            return True
        except DeliveryError as exc:
            logger.error("Unroutable message for event %s: %s", event_type.value, exc)
            return False
        except Exception as exc:
            logger.error("Failed to publish %s: %s", event_type.value, exc)
            return False

    async def publish_events(self, items: list[tuple[MessageQueueEventType, BaseModel | dict[str, Any]]]) -> bool:
        if not items:
            return True
        if self._exchange is None:
            logger.error("Publisher not connected when publishing batch of %d", len(items))
            return False
        try:
            for event_type, payload in items:
                body = self._encode(event_type, payload)
                await self._exchange.publish(self._message(body), routing_key=self._routing_key, mandatory=True)
            return True
        except DeliveryError as exc:
            logger.error("Unroutable message during batch publish: %s", exc)
            return False
        except Exception as exc:
            logger.error("Failed to publish batch of %d events: %s", len(items), exc)
            return False
