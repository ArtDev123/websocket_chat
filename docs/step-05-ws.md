# Шаг 5 — Enum, DTO, ConnectionManager, join/leave

**Предыдущий:** [step-04-rooms.md](step-04-rooms.md) · **Следующий:** [step-06-messages.md](step-06-messages.md)

## Задача

Открыть `WS /ws?token=...`, принять кадры `join` / `leave` через **enum + Pydantic**, держать подписки в `ConnectionManager`. Сообщения в БД — на следующем шаге; сейчас хватит `system`-кадров.

---

## Теория: чем WebSocket отличается от HTTP

HTTP: клиент спросил → сервер ответил → всё.  
WebSocket после рукопожатия — **труба в обе стороны**. Сервер может писать сам, клиент может молчать.

FastAPI даёт объект `WebSocket`: `accept()`, `receive_text()`, `send_json()`, `close()`.

```text
клиент                         сервер
  │  Upgrade: websocket            │
  │ ──────────────────────────────►│
  │ ◄──── 101 Switching ───────────│
  │  JSON {"type":"join",...}      │
  │ ──────────────────────────────►│
  │ ◄──── JSON {"type":"system"} ──│
```

Токен кладём в query (`?token=`): браузерный `new WebSocket(url)` **не умеет** поставить заголовок `Authorization` при подключении.

---

## Теория: зачем enum, а не `if msg_type == "dm"`

Строки легко опечатать (`"mesage"`), IDE не подскажет варианты, поиск по проекту неудобен.

`enum.StrEnum` фиксирует набор значений. В коде пишете `WsClientType.JOIN`, в JSON по проводу всё равно уходит `"join"`.

Дальше — не длинный `elif`-лес в одном цикле, а короткий `match` + отдельные функции `handle_join`, `handle_leave`. Каждая функция делает одно дело и читается с экрана целиком.

---

## Теория: DTO вместо словарей

Вместо:

```python
await ws.send_json({"type": "system", "text": "..."})
```

собираем Pydantic-модель и отдаём `model_dump(mode="json")`:

- поля названы в одном месте;
- даты сериализуются одинаково;
- опечатка в ключе ловится до отправки.

Входящий кадр тоже парсим в модель: лишние/битые поля → отправим `error`, а не упадём с `KeyError`.

---

## Теория: ConnectionManager

Сокеты живут в памяти **этого** процесса:

```text
active:  user_id → WebSocket     # кто онлайн
rooms:   room_id → {user_id, …}  # кто слушает комнату
```

Менеджер **не** ходит в БД. Он только знает, кому доставить уже готовый DTO. Проверку «комната существует» делает репозиторий.

Второй процесс Uvicorn этих словарей не видит — об этом шаг 10.

---

## Код: `app/enums.py`

```python
from enum import StrEnum


class WsClientType(StrEnum):
    JOIN = "join"
    LEAVE = "leave"
    MESSAGE = "message"
    DM = "dm"


class WsServerType(StrEnum):
    SYSTEM = "system"
    MESSAGE = "message"
    DM = "dm"
    ERROR = "error"
```

**Разбор:** два enum — входящие команды и исходящие события. Значения совпадают со строками в JSON, поэтому старый клиент с `"type":"join"` продолжит работать.

---

## Код: WS-схемы в `app/schemas.py`

В конец файла:

```python
from app.enums import WsClientType, WsServerType


class WsIncoming(BaseModel):
    """Общий входной кадр. Лишние поля игнорируем, нужные проверим в handle_*."""

    type: WsClientType
    room_id: int | None = None
    text: str | None = None
    to_user_id: int | None = None


class WsSystemOut(BaseModel):
    type: WsServerType = WsServerType.SYSTEM
    text: str


class WsErrorOut(BaseModel):
    type: WsServerType = WsServerType.ERROR
    text: str


class WsMessageOut(BaseModel):
    type: WsServerType = WsServerType.MESSAGE
    id: int
    room_id: int
    sender_id: int
    sender: str
    text: str
    created_at: datetime


class WsDmOut(BaseModel):
    type: WsServerType = WsServerType.DM
    id: int
    sender_id: int
    sender: str
    recipient_id: int
    text: str
    created_at: datetime
```

Импорт `datetime` уже должен быть вверху `schemas.py`.  
`WsMessageOut` / `WsDmOut` понадобятся на шагах 6–7 — заведите сразу, чтобы не прыгать по файлам.

**Разбор:** `WsIncoming` — один вход на все типы; конкретный `handle_*` сам проверит, что `room_id` или `text` заполнены. Так не плодим четыре почти одинаковых модели на вход.

---

## Код: `app/manager.py`

```python
from fastapi import WebSocket
from pydantic import BaseModel


class ConnectionManager:
    def __init__(self) -> None:
        self.active: dict[int, WebSocket] = {}
        self.rooms: dict[int, set[int]] = {}

    async def connect(self, user_id: int, websocket: WebSocket) -> None:
        await websocket.accept()
        old = self.active.get(user_id)
        if old is not None and old is not websocket:
            await old.close(code=4000)
        self.active[user_id] = websocket

    def disconnect(self, user_id: int) -> None:
        self.active.pop(user_id, None)
        empty_rooms = [
            room_id
            for room_id, members in self.rooms.items()
            if user_id in members
        ]
        for room_id in empty_rooms:
            self.leave_room(room_id, user_id)

    def join_room(self, room_id: int, user_id: int) -> None:
        self.rooms.setdefault(room_id, set()).add(user_id)

    def leave_room(self, room_id: int, user_id: int) -> None:
        members = self.rooms.get(room_id)
        if not members:
            return
        members.discard(user_id)
        if not members:
            del self.rooms[room_id]

    async def send_dto(self, user_id: int, dto: BaseModel) -> None:
        ws = self.active.get(user_id)
        if ws is None:
            return
        await ws.send_json(dto.model_dump(mode="json"))

    async def broadcast_room(self, room_id: int, dto: BaseModel) -> None:
        for uid in list(self.rooms.get(room_id, set())):
            await self.send_dto(uid, dto)


manager = ConnectionManager()
```

**Разбор:**

- При повторном логине с того же аккаунта старый сокет закрываем (`4000`) — один user = один живой сокет.
- `disconnect` чистит и `active`, и все комнаты, иначе broadcast пойдёт в никуда.
- `send_dto` / `broadcast_room` принимают **Pydantic**, не сырой `dict`.

---

## Код: `app/routes/ws.py`

Файл длиннее предыдущих — поэтому сразу режем на короткие функции.

```python
import jwt
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from app.auth import decode_token_payload
from app.enums import WsClientType
from app.errors import NotFoundError
from app.manager import manager
from app.models import User
from app.repositories.rooms import RoomRepository
from app.repositories.users import UserRepository
from app.schemas import WsErrorOut, WsIncoming, WsSystemOut

router = APIRouter(tags=["ws"])


async def resolve_user(token: str, session_factory) -> User | None:
    try:
        payload = decode_token_payload(token)
    except jwt.PyJWTError:
        return None
    user_id = int(payload["sub"])
    async with session_factory() as session:
        users = UserRepository(session)
        try:
            return await users.get(user_id)
        except NotFoundError:
            return None


async def send_error(user_id: int, text: str) -> None:
    await manager.send_dto(user_id, WsErrorOut(text=text))


async def handle_join(user: User, data: WsIncoming, session_factory) -> None:
    if data.room_id is None:
        await send_error(user.id, "room_id required")
        return

    async with session_factory() as session:
        rooms = RoomRepository(session)
        try:
            await rooms.get(data.room_id)
        except NotFoundError:
            await send_error(user.id, "room not found")
            return

    manager.join_room(data.room_id, user.id)
    await manager.send_dto(
        user.id,
        WsSystemOut(text=f"joined room {data.room_id}"),
    )


async def handle_leave(user: User, data: WsIncoming) -> None:
    if data.room_id is None:
        await send_error(user.id, "room_id required")
        return
    manager.leave_room(data.room_id, user.id)
    await manager.send_dto(
        user.id,
        WsSystemOut(text=f"left room {data.room_id}"),
    )


async def dispatch(user: User, data: WsIncoming, session_factory) -> None:
    match data.type:
        case WsClientType.JOIN:
            await handle_join(user, data, session_factory)
        case WsClientType.LEAVE:
            await handle_leave(user, data)
        case WsClientType.MESSAGE | WsClientType.DM:
            await send_error(user.id, f"{data.type} not implemented yet")
        case _:
            await send_error(user.id, f"unknown type: {data.type}")


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str = "") -> None:
    session_factory = websocket.app.state.session_factory
    user = await resolve_user(token, session_factory)
    if user is None:
        # close() до accept() Starlette превращает в HTTP 403,
        # и код 4401 до клиента не доходит. Сначала accept, потом close.
        await websocket.accept()
        await websocket.close(code=4401)
        return

    await manager.connect(user.id, websocket)
    await manager.send_dto(
        user.id,
        WsSystemOut(text=f"connected as {user.username}"),
    )

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data = WsIncoming.model_validate_json(raw)
            except ValidationError:
                await send_error(user.id, "invalid payload")
                continue
            await dispatch(user, data, session_factory)
    except WebSocketDisconnect:
        manager.disconnect(user.id)
```

**Разбор по функциям:**

| Функция | Одно дело |
|---------|-----------|
| `resolve_user` | токен → User через `UserRepository` |
| `send_error` | единообразно отправить `WsErrorOut` |
| `handle_join` | проверить комнату в БД → подписать в manager |
| `handle_leave` | снять подписку |
| `dispatch` | `match` по `WsClientType`, без строковых `elif` |
| `websocket_endpoint` | цикл приёма кадров |

Почему `async with session_factory()` внутри хендлеров, а не одна сессия на весь сокет? Сокет живёт минутами. Держать транзакцию/сессию открытой всё это время — плохо. Открываем сессию на одно действие и закрываем.

`MESSAGE` / `DM` пока отвечают «not implemented» — реализуете на шагах 6–7, ветки в `match` уже зарезервированы.

---

## Код: регистрация роутера

```python
from app.routes import auth, rooms, users, ws


def register_routes(app: FastAPI) -> None:
    app.include_router(auth.router)
    app.include_router(users.router)
    app.include_router(rooms.router)
    app.include_router(ws.router)
```

---

## ✅ Проверка

```bash
export TOKEN=...   # из /auth/login

python - <<'PY'
import asyncio, json, os
import websockets

TOKEN = os.environ["TOKEN"]

async def main():
    uri = f"ws://127.0.0.1:8080/ws?token={TOKEN}"
    async with websockets.connect(uri) as ws:
        print(await ws.recv())
        await ws.send(json.dumps({"type": "join", "room_id": 1}))
        print(await ws.recv())
        await ws.send(json.dumps({"type": "leave", "room_id": 1}))
        print(await ws.recv())

asyncio.run(main())
PY
```

Ожидаете `connected as …`, `joined room 1`, `left room 1`.  
Без токена — сокет сразу закрывается.  
`{"type":"message",...}` пока → `error: message not implemented yet`.

**Готово →** [step-06-messages.md](step-06-messages.md)
