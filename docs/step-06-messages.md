# Шаг 6 — MessageRepository и сообщения комнаты

**Предыдущий:** [step-05-ws.md](step-05-ws.md) · **Следующий:** [step-07-dm.md](step-07-dm.md)

## Задача

Реализовать кадр `message`: сохранить через репозиторий, разослать `WsMessageOut` всем в комнате. Добавить `GET /rooms/{id}/messages` для истории.

---

## Теория: сначала БД, потом broadcast

Порядок такой:

1. Пользователь должен быть в комнате (`join` уже был).
2. Репозиторий делает `INSERT` + `commit`.
3. Только потом `broadcast_room` с DTO, у которого уже есть серверный `id` и `created_at`.

Если слать кадр до commit, клиенты увидят сообщение, которого нет в истории после F5. Если INSERT упал — никто не должен получить «фантом».

Рассылаем **включая отправителя**: у всех один и тот же JSON с серверным id, а не «у меня локально нарисовал, у остальных с сервера».

---

## Теория: что добавляет MessageRepository

Базовый `add(**fields)` умеет вставить строку. Нам ещё нужно:

- история комнаты с подгрузкой `sender` (`selectinload`), чтобы отдать `sender` как username;
- позже — история DM.

Всё это — методы репозитория. Роут и WS только вызывают их.

---

## Код: `MessageRead` в `app/schemas.py`

Если ещё нет:

```python
class MessageRead(BaseModel):
    id: int
    text: str
    sender_id: int
    sender: str
    room_id: int | None = None
    recipient_id: int | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
```

`sender` — не колонка в БД, а имя из связи. Соберём вручную маленькой функцией.

---

## Код: `app/repositories/messages.py`

```python
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models import Message
from app.repositories.base import BaseRepository


class MessageRepository(BaseRepository[Message]):
    model = Message

    async def list_for_room(
        self, room_id: int, *, limit: int = 50
    ) -> Sequence[Message]:
        result = await self._session.execute(
            select(Message)
            .where(Message.room_id == room_id)
            .options(selectinload(Message.sender))
            .order_by(Message.id.desc())
            .limit(limit)
        )
        rows = list(result.scalars().all())
        rows.reverse()
        return rows

    async def add_room_message(
        self, *, room_id: int, sender_id: int, text: str
    ) -> Message:
        msg = await self.add(
            text=text,
            sender_id=sender_id,
            room_id=room_id,
            recipient_id=None,
        )
        # после commit relationship может быть не загружен — читаем с selectinload
        result = await self._session.execute(
            select(Message)
            .where(Message.id == msg.id)
            .options(selectinload(Message.sender))
        )
        return result.scalar_one()
```

**Разбор:**

- `list_for_room` берёт последние N и разворачивает в хронологический порядок (сначала старые).
- `add_room_message` явно ставит `recipient_id=None`, чтобы не перепутать с DM.
- Повторный select с `selectinload` — чтобы сразу иметь `msg.sender.username` для DTO.

---

## Код: хелпер DTO (можно в `app/schemas.py` или рядом с роутом)

В `app/schemas.py`:

```python
from app.models import Message


def message_to_read(msg: Message) -> MessageRead:
    return MessageRead(
        id=msg.id,
        text=msg.text,
        sender_id=msg.sender_id,
        sender=msg.sender.username,
        room_id=msg.room_id,
        recipient_id=msg.recipient_id,
        created_at=msg.created_at,
    )


def message_to_ws_room(msg: Message) -> WsMessageOut:
    return WsMessageOut(
        id=msg.id,
        room_id=msg.room_id,
        sender_id=msg.sender_id,
        sender=msg.sender.username,
        text=msg.text,
        created_at=msg.created_at,
    )
```

**Разбор:** одна точка преобразования ORM → API/WS. Роут и сокет не дублируют поля вручную.

---

## Код: `app/routes/messages.py`

```python
from fastapi import APIRouter, HTTPException

from app.auth import CurrentUser
from app.deps import MessageRepoDep, RoomRepoDep
from app.errors import NotFoundError
from app.schemas import MessageRead, message_to_read

router = APIRouter(tags=["messages"])


@router.get("/rooms/{room_id}/messages", response_model=list[MessageRead])
async def room_history(
    room_id: int,
    rooms: RoomRepoDep,
    messages: MessageRepoDep,
    _: CurrentUser,
    limit: int = 50,
) -> list[MessageRead]:
    try:
        await rooms.get(room_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message) from exc

    rows = await messages.list_for_room(room_id, limit=min(limit, 100))
    return [message_to_read(m) for m in rows]
```

Либо не ловите `NotFoundError` вручную — глобальный handler в `main` уже отдаёт 404. Тогда достаточно:

```python
    await rooms.get(room_id)  # NotFoundError → 404
    rows = await messages.list_for_room(room_id, limit=min(limit, 100))
    return [message_to_read(m) for m in rows]
```

---

## Код: deps + `__init__`

В `app/deps.py`:

```python
from app.repositories.messages import MessageRepository


def get_message_repository(session: SessionDep) -> MessageRepository:
    return MessageRepository(session)


MessageRepoDep = Annotated[MessageRepository, Depends(get_message_repository)]
```

В `repositories/__init__.py` добавьте `MessageRepository`.  
В `routes/__init__.py` — `messages.router`.

---

## Код: `handle_message` в `app/routes/ws.py`

Добавьте функцию и подключите в `match`:

```python
from app.repositories.messages import MessageRepository
from app.schemas import message_to_ws_room


async def handle_message(user: User, data: WsIncoming, session_factory) -> None:
    if data.room_id is None:
        await send_error(user.id, "room_id required")
        return

    text = (data.text or "").strip()
    if not text:
        await send_error(user.id, "empty text")
        return

    if user.id not in manager.rooms.get(data.room_id, set()):
        await send_error(user.id, "join the room first")
        return

    async with session_factory() as session:
        rooms = RoomRepository(session)
        messages = MessageRepository(session)
        try:
            await rooms.get(data.room_id)
        except NotFoundError:
            await send_error(user.id, "room not found")
            return
        msg = await messages.add_room_message(
            room_id=data.room_id,
            sender_id=user.id,
            text=text,
        )

    await manager.broadcast_room(data.room_id, message_to_ws_room(msg))
```

В `dispatch`:

```python
    match data.type:
        case WsClientType.JOIN:
            await handle_join(user, data, session_factory)
        case WsClientType.LEAVE:
            await handle_leave(user, data)
        case WsClientType.MESSAGE:
            await handle_message(user, data, session_factory)
        case WsClientType.DM:
            await send_error(user.id, "dm not implemented yet")
        case _:
            await send_error(user.id, f"unknown type: {data.type}")
```

**Разбор:** проверка «в комнате ли ты» — по `manager` (live-подписка). Проверка «комната есть» — по репозиторию. Сохранение — только `add_room_message`. Рассылка — готовый `WsMessageOut`.

---

## ✅ Проверка

1. Два клиента (alice и bob), оба `join` room 1.  
2. Alice: `{"type":"message","room_id":1,"text":"hello"}`.  
3. Оба получают один `WsMessageOut` с одним `id`.  
4. REST:

```bash
curl -s "http://127.0.0.1:8080/rooms/1/messages" \
  -H "Authorization: Bearer $TOKEN"
```

Без `join` → `error: join the room first`.

**Готово →** [step-07-dm.md](step-07-dm.md)
