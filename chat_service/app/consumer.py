import json
import logging

import aio_pika
from aio_pika import ExchangeType

from app.config import settings
from app.repositories.profiles import UserProfileRepository

log = logging.getLogger(__name__)


async def start_consumer(session_factory) -> aio_pika.abc.AbstractRobustConnection:
    connection = await aio_pika.connect_robust(settings.rabbitmq_url)
    channel = await connection.channel()
    await channel.set_qos(prefetch_count=10)
    exchange = await channel.declare_exchange(
        "users",
        ExchangeType.TOPIC,
        durable=True,
    )
    queue = await channel.declare_queue("chat.users", durable=True)
    await queue.bind(exchange, routing_key="user.registered")

    async def on_message(message: aio_pika.abc.AbstractIncomingMessage) -> None:
        async with message.process(requeue=True):
            data = json.loads(message.body)
            if data.get("event") != "user.registered":
                return
            async with session_factory() as session:
                profiles = UserProfileRepository(session)
                await profiles.upsert(
                    user_id=int(data["user_id"]),
                    username=str(data["username"]),
                )
            log.info(
                "profile upserted id=%s username=%s",
                data["user_id"],
                data["username"],
            )

    await queue.consume(on_message)
    log.info("consuming queue chat.users")
    return connection
