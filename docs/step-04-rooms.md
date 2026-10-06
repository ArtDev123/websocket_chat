# Шаг 4 — RoomRepository, комнаты и пользователи

**Предыдущий:** [step-03-auth.md](step-03-auth.md) · **Следующий:** [step-05-ws.md](step-05-ws.md)

## Задача

REST: список пользователей, создать/список комнат. Снова без SQL в роутах — только репозитории. Сообщения пока не пишем.

Все эндпоинты — **с JWT** (`CurrentUser`).

---

## Теория: комната как «канал»

Комната — именованный канал чата (`general`, `random`). В БД храним имя и кто создал (`created_by_id`). Отдельной таблицы «участники» нет: на уроке любой авторизованный пользователь может сделать `join` по `room_id`.

Список `/users` нужен UI на шаге 8: выбрать, кому писать в DM.

---

## Теория: Depends на несколько репозиториев

На одном запросе могут понадобиться и users, и rooms. FastAPI вызовет оба провайдера, но **сессию** создаст один раз (кэш `Depends` на запрос). Поэтому не открывайте сессию вручную в роуте — только через `UserRepoDep` / `RoomRepoDep`.

---

## Код: дописать `app/schemas.py`

```python
class RoomCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class RoomRead(BaseModel):
    id: int
    name: str
    created_by_id: int
    created_at: datetime

    model_config = {"from_attributes": True}
```

**Разбор:** `RoomCreate` — вход. `RoomRead` — выход без лишних полей. Имена схем отделяют «что клиент прислал» от «что отдаём».

---

## Код: `app/repositories/rooms.py`

```python
from sqlalchemy import select

from app.models import Room
from app.repositories.base import BaseRepository


class RoomRepository(BaseRepository[Room]):
    model = Room

    async def get_by_name(self, name: str) -> Room | None:
        result = await self._session.execute(
            select(Room).where(Room.name == name)
        )
        return result.scalar_one_or_none()
```

**Разбор:** `get_all` / `get` / `add` уже есть в базе. `get_by_name` нужен, чтобы при создании комнаты проверить уникальность имени и вернуть 409, а не падать на constraint.

---

## Код: обновить `app/deps.py`

Добавьте Room-репозиторий рядом с User:

```python
from typing import Annotated

from fastapi import Depends

from app.db import SessionDep
from app.repositories.rooms import RoomRepository
from app.repositories.users import UserRepository


def get_user_repository(session: SessionDep) -> UserRepository:
    return UserRepository(session)


def get_room_repository(session: SessionDep) -> RoomRepository:
    return RoomRepository(session)


UserRepoDep = Annotated[UserRepository, Depends(get_user_repository)]
RoomRepoDep = Annotated[RoomRepository, Depends(get_room_repository)]
```

---

## Код: `app/routes/users.py`

```python
from fastapi import APIRouter

from app.auth import CurrentUser
from app.deps import UserRepoDep
from app.schemas import UserRead

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserRead])
async def list_users(
    users: UserRepoDep,
    _: CurrentUser,
) -> list[UserRead]:
    rows = await users.get_all()
    return [UserRead.model_validate(u) for u in rows]
```

**Разбор:** `_ : CurrentUser` — «пользователь нам в теле не нужен, но без токена пускать нельзя».  
`get_all()` — из `BaseRepository`, без копипасты `select`.

---

## Код: `app/routes/rooms.py`

```python
from fastapi import APIRouter, HTTPException, status

from app.auth import CurrentUser
from app.deps import RoomRepoDep
from app.schemas import RoomCreate, RoomRead

router = APIRouter(prefix="/rooms", tags=["rooms"])


@router.get("", response_model=list[RoomRead])
async def list_rooms(
    rooms: RoomRepoDep,
    _: CurrentUser,
) -> list[RoomRead]:
    rows = await rooms.get_all()
    return [RoomRead.model_validate(r) for r in rows]


@router.post("", response_model=RoomRead, status_code=status.HTTP_201_CREATED)
async def create_room(
    body: RoomCreate,
    rooms: RoomRepoDep,
    user: CurrentUser,
) -> RoomRead:
    if await rooms.get_by_name(body.name) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Room name already taken",
        )
    room = await rooms.add(name=body.name, created_by_id=user.id)
    return RoomRead.model_validate(room)
```

**Разбор:** создатель берётся из JWT (`user.id`), клиент его в body не присылает — иначе можно было бы подставить чужой id.

---

## Код: зарегистрировать роуты

`app/routes/__init__.py`:

```python
from fastapi import FastAPI

from app.routes import auth, rooms, users


def register_routes(app: FastAPI) -> None:
    app.include_router(auth.router)
    app.include_router(users.router)
    app.include_router(rooms.router)
```

`app/repositories/__init__.py`:

```python
from app.repositories.base import BaseRepository
from app.repositories.rooms import RoomRepository
from app.repositories.users import UserRepository

__all__ = ["BaseRepository", "UserRepository", "RoomRepository"]
```

---

## ✅ Проверка

```bash
TOKEN=$(curl -s -X POST http://127.0.0.1:8080/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"alice","password":"secret"}' \
  | python -c 'import sys,json; print(json.load(sys.stdin)["access_token"])')

curl -s -X POST http://127.0.0.1:8080/rooms \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"name":"general"}'

curl -s http://127.0.0.1:8080/rooms -H "Authorization: Bearer $TOKEN"
curl -s http://127.0.0.1:8080/users -H "Authorization: Bearer $TOKEN"
```

Без `Authorization` → 401/403.  
Зарегистрируйте второго пользователя `bob` — пригодится дальше.

**Готово →** [step-05-ws.md](step-05-ws.md)
