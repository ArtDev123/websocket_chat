# Шаг 5 — Консьюмер и проекция

**Предыдущий:** [step-04-chat-service.md](step-04-chat-service.md) · **Следующий:** [step-06-frontend.md](step-06-frontend.md)

## Задача

Слушать очередь `chat.users` и писать `user_profiles`. Добавить `GET /profiles`, чтобы глазами увидеть, что событие дошло. Повторная доставка того же `user_id` не создаёт вторую строку.

## Теория

Очередь объявляет тот, кто читает. Chat при старте создаёт durable-очередь `chat.users` и привязывает её к exchange `users` по ключу `user.registered`. User-сервис про имя очереди не знает.

`ack` ставим после успешного upsert. `message.process(requeue=True)` делает это само: вышли из блока без исключения — сообщение снято, исключение — сообщение вернётся в очередь.

Повтор безопасен: `INSERT ... ON CONFLICT (id) DO UPDATE` обновляет username и не падает на уже существующем id.

Порядок, если поднимаете всё заново: брокер, chat, user, регистрация. Иначе событие попадёт в exchange без очереди и пропадёт. Уже потерянные на шаге 3 события сами не восстановятся.

## Код

Замените `chat_service/app/repositories/profiles.py` на версию с upsert:

```python
from sqlalchemy.dialects.postgresql import insert

from app.models import UserProfile
from app.repositories.base import BaseRepository


class UserProfileRepository(BaseRepository[UserProfile]):
    model = UserProfile

    async def upsert(self, *, user_id: int, username: str) -> None:
        stmt = insert(UserProfile).values(id=user_id, username=username)
        stmt = stmt.on_conflict_do_update(
            index_elements=[UserProfile.id],
            set_={"username": stmt.excluded.username},
        )
        await self._session.execute(stmt)
        await self._session.commit()
```

`chat_service/app/consumer.py`:

```python
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
```

В `app/schemas.py` добавьте модель ответа:

```python
class ProfileRead(BaseModel):
    id: int
    username: str
    created_at: datetime

    model_config = {"from_attributes": True}
```

`app/routes/profiles.py`:

```python
from fastapi import APIRouter

from app.auth import CurrentUser
from app.deps import ProfileRepoDep
from app.schemas import ProfileRead

router = APIRouter(tags=["profiles"])


@router.get("/profiles", response_model=list[ProfileRead])
async def list_profiles(
    profiles: ProfileRepoDep,
    _: CurrentUser,
) -> list[ProfileRead]:
    rows = await profiles.get_all()
    return [ProfileRead.model_validate(row) for row in rows]
```

В `app/routes/__init__.py` подключите роутер рядом с остальными: `from app.routes import messages, profiles, rooms, ws` и `app.include_router(profiles.router)`.

В lifespan `app/main.py` консьюмер стартует после фабрики сессий и закрывается до `engine.dispose()`:

```python
from app.consumer import start_consumer
```

```python
    app.state.session_factory = make_session_factory(engine)
    app.state.broker = await start_consumer(app.state.session_factory)
    yield
    await app.state.broker.close()
    await engine.dispose()
```

Пересоберите чат: `docker compose -f chat_service/docker-compose.yml up --build -d`. Пока идёт lifespan, `/health` не ответит — процесс ждёт брокера.

## Разбор кода

`declare_exchange` здесь и в user-сервисе — один и тот же вызов. Кто стартовал первым, тот создал exchange, второй только убедился, что он есть.

`set_qos(prefetch_count=10)` не даёт одному консьюмеру забрать всю очередь в память. Для урока это не про нагрузку, а про привычку не читать сообщения пачкой без ack.

`GET /profiles` закрыт тем же JWT, что и комнаты. Это учебный смотровой люк, не отдельный продукт.

## ✅ Проверка

Чат должен быть healthy (очередь уже объявлена), затем регистрация **нового** пользователя. Alice с шага 2 в проекцию не попадёт: её событие ушло до появления очереди.

```bash
curl -s -X POST http://127.0.0.1:8081/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"username":"dave","password":"secret"}'

TOKEN=$(curl -s -X POST http://127.0.0.1:8081/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"dave","password":"secret"}' | python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')

curl -s http://127.0.0.1:8082/profiles -H "Authorization: Bearer $TOKEN"
```

В списке есть `dave`. В UI брокера очередь `chat.users` привязана к `users` / `user.registered`.

Неизвестный id в истории DM — 404, потому что проекции нет:

```bash
curl -s -o /dev/null -w "%{http_code}\n" \
  http://127.0.0.1:8082/dm/99999 \
  -H "Authorization: Bearer $TOKEN"
# 404
```

**Готово →** [step-06-frontend.md](step-06-frontend.md)
