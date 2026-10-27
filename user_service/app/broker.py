import json
import logging

import aio_pika
from aio_pika import DeliveryMode, ExchangeType

from app.config import settings

log = logging.getLogger(__name__)

_connection: aio_pika.RobustConnection | None = None
_exchange: aio_pika.abc.AbstractExchange | None = None


class BrokerUnavailable(Exception):
    """Брокер не подключён или publish не удался. Роут превратит это в 503."""


async def connect_broker() -> None:
    global _connection, _exchange
    _connection = await aio_pika.connect_robust(settings.rabbitmq_url)
    channel = await _connection.channel()
    _exchange = await channel.declare_exchange(
        "users",
        ExchangeType.TOPIC,
        durable=True,
    )
    log.info("broker connected, exchange users declared")


async def close_broker() -> None:
    global _connection, _exchange
    if _connection is not None:
        await _connection.close()
    _connection = None
    _exchange = None


async def publish_user_registered(*, user_id: int, username: str) -> None:
    if _exchange is None:
        raise BrokerUnavailable("broker is not connected")
    body = json.dumps(
        {
            "event": "user.registered",
            "user_id": user_id,
            "username": username,
        }
    ).encode()
    try:
        await _exchange.publish(
            aio_pika.Message(
                body=body,
                delivery_mode=DeliveryMode.PERSISTENT,
                content_type="application/json",
            ),
            routing_key="user.registered",
        )
    except Exception as exc:
        raise BrokerUnavailable("failed to publish user.registered") from exc
