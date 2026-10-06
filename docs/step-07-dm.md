# Шаг 7 — Личные сообщения (DM)

**Предыдущий:** [step-06-messages.md](step-06-messages.md) · **Следующий:** [step-08-frontend.md](step-08-frontend.md)

## Задача

Кадр `dm`: сохранить через `MessageRepository`, доставить получателю (если онлайн) и эхом отправителю. История — `GET /dm/{user_id}`.

---

## Теория: чем DM отличается от комнаты

| | Комната | DM |
|--|---------|-----|
| Куда пишем | `room_id` | `recipient_id` |
| Кому слать live | всем в `manager.rooms[room_id]` | отправителю + получателю в `manager.active` |
| Подписка `join` | нужна | не нужна |

Если bob сейчас оффлайн — сообщение всё равно попадает в Postgres. Когда bob откроет диалог, история подтянется REST-ом.

Переписка alice↔bob — все DM, где они встречаются в любой роли:

```text
(sender = me AND recipient = other)
  OR
(sender = other AND recipient = me)
```

И обязательно `room_id IS NULL`, чтобы не смешать с комнатными сообщениями.

---

## Код: методы в `MessageRepository`

В `app/repositories/messages.py` добавьте:

```python
from sqlalchemy import or_, select


async def list_dm(
    self, user_a: int, user_b: int, *, limit: int = 50
) -> Sequence[Message]:
    result = await self._session.execute(
        select(Message)
        .where(
            Message.room_id.is_(None),
            or_(
                (Message.sender_id == user_a)
                & (Message.recipient_id == user_b),
                (Message.sender_id == user_b)
                & (Message.recipient_id == user_a),
            ),
        )
        .options(selectinload(Message.sender))
        .order_by(Message.id.desc())
        .limit(limit)
    )
    rows = list(result.scalars().all())
    rows.reverse()
    return rows


async def add_dm(
    self, *, sender_id: int, recipient_id: int, text: str
) -> Message:
    msg = await self.add(
        text=text,
        sender_id=sender_id,
        room_id=None,
        recipient_id=recipient_id,
    )
    result = await self._session.execute(
        select(Message)
        .where(Message.id == msg.id)
        .options(selectinload(Message.sender))
    )
    return result.scalar_one()
```

(Методы — внутри класса `MessageRepository`, рядом с `list_for_room`.)

**Разбор:** `add_dm` зеркалит `add_room_message`, только поля наоборот. Так в коде явно видно инвариант «ровно одно из room/recipient».

---

## Код: `message_to_ws_dm` в `app/schemas.py`

```python
def message_to_ws_dm(msg: Message) -> WsDmOut:
    return WsDmOut(
        id=msg.id,
        sender_id=msg.sender_id,
        sender=msg.sender.username,
        recipient_id=msg.recipient_id,
        text=msg.text,
        created_at=msg.created_at,
    )
```

---

## Код: история в `app/routes/messages.py`

```python
from fastapi import APIRouter, HTTPException, status

from app.auth import CurrentUser
from app.deps import MessageRepoDep, RoomRepoDep, UserRepoDep
from app.schemas import MessageRead, message_to_read

# ... room_history как был ...


@router.get("/dm/{user_id}", response_model=list[MessageRead])
async def dm_history(
    user_id: int,
    users: UserRepoDep,
    messages: MessageRepoDep,
    me: CurrentUser,
    limit: int = 50,
) -> list[MessageRead]:
    if user_id == me.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot open DM with yourself",
        )
    await users.get(user_id)  # NotFoundError → 404
    rows = await messages.list_dm(me.id, user_id, limit=min(limit, 100))
    return [message_to_read(m) for m in rows]
```

**Разбор:** `users.get(user_id)` проверяет, что собеседник существует, без ручного `select`. Писать себе запрещаем отдельной 400.

---

## Код: `handle_dm` в `app/routes/ws.py`

```python
from app.schemas import message_to_ws_dm


async def handle_dm(user: User, data: WsIncoming, session_factory) -> None:
    if data.to_user_id is None:
        await send_error(user.id, "to_user_id required")
        return

    text = (data.text or "").strip()
    if not text:
        await send_error(user.id, "empty text")
        return

    if data.to_user_id == user.id:
        await send_error(user.id, "cannot DM yourself")
        return

    async with session_factory() as session:
        users = UserRepository(session)
        messages = MessageRepository(session)
        try:
            await users.get(data.to_user_id)
        except NotFoundError:
            await send_error(user.id, "user not found")
            return
        msg = await messages.add_dm(
            sender_id=user.id,
            recipient_id=data.to_user_id,
            text=text,
        )

    dto = message_to_ws_dm(msg)
    await manager.send_dto(user.id, dto)
    await manager.send_dto(data.to_user_id, dto)
```

В `dispatch`:

```python
        case WsClientType.DM:
            await handle_dm(user, data, session_factory)
```

**Разбор:** снова короткий хендлер: валидация полей → репозиторий → два `send_dto` одним и тем же DTO. Если получатель оффлайн, `send_dto` просто ничего не сделает — запись в БД уже есть.

---

## ✅ Проверка

1. Alice и Bob онлайн.  
2. Alice → `{"type":"dm","to_user_id":<bob_id>,"text":"ping"}`.  
3. Оба видят `type: dm`.  
4. Bob оффлайн: у Alice всё равно эхо; у Bob после логина:

```bash
curl -s "http://127.0.0.1:8080/dm/<alice_id>" \
  -H "Authorization: Bearer $BOB_TOKEN"
```

**Готово →** [step-08-frontend.md](step-08-frontend.md)
