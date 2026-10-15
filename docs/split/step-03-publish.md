# Шаг 3 — Событие `user.registered`

**Предыдущий:** [step-02-user-service.md](step-02-user-service.md) · **Следующий:** [step-04-chat-service.md](step-04-chat-service.md)

## Задача

После успешного commit регистрации опубликовать JSON в exchange `users`. Если брокер недоступен, `POST /auth/register` отвечает 503.

## Теория

Регистрация — факт, который случился. Чату не нужно, чтобы user-сервис знал про комнаты. User-сервис кладёт в шину короткое сообщение и забывает, кто его прочитает.

Публикуем **после** commit. До commit события быть не должно: чат создал бы профиль пользователя, которого в базе нет. Если commit прошёл, а publish нет, клиент видит 503. Строка пользователя при этом уже есть, повторная регистрация того же ника вернёт 409. Для урока этого достаточно. Надёжная связка «строка и событие либо вместе, либо никак» называется outbox и сюда не входит — она названа в финальном шаге.

Клиент — `aio-pika`, не блокирующий `pika`. Иначе publish остановит event loop uvicorn.

Контракт, который chat будет читать на шаге 5:

```json
{"event": "user.registered", "user_id": 1, "username": "alice"}
```

Exchange `users`, тип topic, durable. Routing key `user.registered`. Очередь объявляет получатель, не отправитель. Пока чат не запущен, у exchange нет очереди, и сообщение пропадёт. Поэтому в финальной проверке chat стартует раньше регистрации.

## Код

В `user_service/requirements.txt` добавьте строку:

```text
aio-pika>=9.4
```

`user_service/app/broker.py`:

```python
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
```

В `app/routes/auth.py` регистрация после `users.add` публикует событие. Остальные ручки не меняются.

```python
from app.broker import BrokerUnavailable, publish_user_registered
```

```python
    user = await users.add(
        username=body.username,
        password_hash=hash_password(body.password),
    )
    try:
        await publish_user_registered(user_id=user.id, username=user.username)
    except BrokerUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Broker unavailable",
        ) from exc
    return UserRead.model_validate(user)
```

В `app/main.py` подключение брокера — в lifespan, до `yield`. Пока RabbitMQ не ответил, API не начнёт принимать запросы.

```python
from app.broker import close_broker, connect_broker
```

```python
    app.state.session_factory = make_session_factory(engine)
    await connect_broker()
    yield
    await close_broker()
    await engine.dispose()
```

Пересоберите образ: в нём ещё нет `aio-pika`.

```bash
docker compose -f user_service/docker-compose.yml up --build -d
```

## Разбор кода

`connect_robust` сам переподключает канал, если брокер моргнул. `declare_exchange` идемпотентен: второй процесс с тем же именем и типом не создаёт второй exchange.

`delivery_mode=PERSISTENT` просит брокер записать сообщение на диск. Это не замена очереди: если очереди нет, персистентность некому хранить.

`UserRepository.add` уже делает commit. Publish стоит сразу после него, в роуте, а не внутри репозитория: репозиторий по-прежнему не знает про RabbitMQ.

## ✅ Проверка

Брокер с шага 1 запущен.

```bash
curl -s -o /dev/null -w "%{http_code}\n" -X POST http://127.0.0.1:8081/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"username":"bob","password":"secret"}'
# 201
```

В UI http://127.0.0.1:15672 появился exchange `users` типа topic. Очереди `chat.users` ещё нет — её объявит чат. Сообщение про bob при этом потеряно. Это ожидаемо, на шаге 5 регистрация пойдёт уже при живой очереди.

Остановите брокер и повторите регистрацию с новым именем:

```bash
docker stop rabbit-rabbitmq-1
curl -s -w "\n%{http_code}\n" -X POST http://127.0.0.1:8081/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"username":"carol","password":"secret"}'
# {"detail":"Broker unavailable"}
# 503

docker start rabbit-rabbitmq-1
```

Имя контейнера возьмите из `docker compose -f rabbit/docker-compose.yml ps`, если оно другое.

**Готово →** [step-04-chat-service.md](step-04-chat-service.md)
