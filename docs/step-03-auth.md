# Шаг 3 — UserRepository, регистрация, логин, JWT

**Предыдущий:** [step-02-models.md](step-02-models.md) · **Следующий:** [step-04-rooms.md](step-04-rooms.md)

## Задача

Сделать простой auth: `POST /auth/register`, `POST /auth/login` → JWT.  
Вся работа с таблицей `users` — только через `UserRepository`. Роут не пишет `select`.

---

## Теория: зачем репозиторий уже на auth

Можно было бы в роуте сделать `select(User).where(...)`. Через два шага тот же запрос понадобится в WebSocket («найти пользователя по id из токена») и в DM. SQL начнут копировать.

**Репозиторий** — объект «работай с этой таблицей». Он знает SQLAlchemy. Он не знает HTTP-статусы и Pydantic-схемы ответа.

```text
POST /auth/login
      │
      ▼
роутер: проверить пароль, выдать JWT
      │
      ▼
UserRepository.get_by_username(...)
      │
      ▼
Postgres
```

`BaseRepository` из каркаса уже умеет `get` / `get_all` / `add` / `update`. Нам добавится один метод `get_by_username` — `get(id)` для логина по нику не подходит.

---

## Теория: JWT простыми словами

После успешного логина сервер отдаёт **токен** — длинную подписанную строку. Клиент потом прикладывает её:

```http
Authorization: Bearer eyJhbGciOiJI...
```

Сервер проверяет подпись секретом из `.env` (`JWT_SECRET`) и читает из токена `sub` (id пользователя). Отдельной «сессии на сервере» нет: кто принёс валидный токен — тот и считается этим пользователем.

Внутри токена (payload) для урока:

- `sub` — id пользователя (строкой, так принято в JWT);
- `username` — удобно логировать;
- `exp` — когда протухнет (из `JWT_EXPIRE_MINUTES`).

Это учебный auth: нет refresh-токенов и logout-blacklist. Для чата на занятии хватает.

---

## Теория: bcrypt

Пароль `"secret"` в БД не кладём. Кладём **хэш** — результат одностороннего преобразования.

- При регистрации: `hash_password` → в колонку `password_hash`.
- При логине: `verify_password(введённый, хэш_из_бд)` → true/false.

Расшифровать хэш обратно в пароль нельзя — только проверить «совпадает ли».

---

## Код: `app/schemas.py`

```python
from datetime import datetime

from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=4, max_length=128)


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserRead(BaseModel):
    id: int
    username: str
    created_at: datetime

    model_config = {"from_attributes": True}
```

**Разбор:** `RegisterRequest` / `LoginRequest` — то, что приходит в JSON. FastAPI сам вернёт 422, если поле короткое или отсутствует.  
`UserRead` — безопасный ответ: **без** `password_hash`. `from_attributes=True` позволяет собрать DTO прямо из ORM-объекта `User`.

---

## Код: `app/repositories/users.py`

```python
from sqlalchemy import select

from app.models import User
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    model = User

    async def get_by_username(self, username: str) -> User | None:
        result = await self._session.execute(
            select(User).where(User.username == username)
        )
        return result.scalar_one_or_none()
```

**Разбор:** наследуемся от `BaseRepository[User]` — получаем `get`, `add` и остальное бесплатно.  
`get_by_username` возвращает `None`, если ника нет: для логина/регистрации это нормальный случай, не 404.  
`get(id)` из базы при отсутствии строки кинет `NotFoundError` → HTTP 404 (уже настроено в `main.py`).

---

## Код: `app/deps.py`

```python
from typing import Annotated

from fastapi import Depends

from app.db import SessionDep
from app.repositories.users import UserRepository


def get_user_repository(session: SessionDep) -> UserRepository:
    return UserRepository(session)


UserRepoDep = Annotated[UserRepository, Depends(get_user_repository)]
```

**Разбор:** FastAPI перед хендлером вызовет `get_user_repository`, а тот через `SessionDep` получит сессию.  
В роуте пишете `users: UserRepoDep` — и не думаете, откуда взялась сессия. Один запрос = одна сессия (Depends кэширует).

---

## Код: `app/auth.py`

```python
from datetime import datetime, timedelta, timezone
from typing import Annotated

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import settings
from app.deps import UserRepoDep
from app.models import User

bearer_scheme = HTTPBearer(auto_error=True)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())


def create_access_token(*, user_id: int, username: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.jwt_expire_minutes
    )
    payload = {
        "sub": str(user_id),
        "username": username,
        "exp": expire,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_token_payload(token: str) -> dict:
    """Сырой decode. REST обернёт в 401, WS — закроет сокет."""
    return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])


def decode_token(token: str) -> dict:
    try:
        return decode_token_payload(token)
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        ) from exc


async def get_current_user(
    users: UserRepoDep,
    credentials: Annotated[
        HTTPAuthorizationCredentials, Depends(bearer_scheme)
    ],
) -> User:
    payload = decode_token(credentials.credentials)
    user_id = int(payload["sub"])
    return await users.get(user_id)


CurrentUser = Annotated[User, Depends(get_current_user)]
```

**Разбор:**

| Функция | Роль |
|---------|------|
| `hash_password` / `verify_password` | пароль ↔ хэш |
| `create_access_token` | собрать JWT после логина |
| `decode_token_payload` | проверить подпись без HTTP (пригодится на WS) |
| `decode_token` | то же + `HTTPException 401` для REST |
| `get_current_user` | достать пользователя **через репозиторий**, не через `select` |
| `CurrentUser` | короткий тип для сигнатур роутов |

`users.get(user_id)` при отсутствии пользователя поднимет `NotFoundError` → 404. Для «битого» токена с несуществующим id это нормально; чаще сработает 401 на этапе decode.

---

## Код: `app/routes/auth.py`

```python
from fastapi import APIRouter, HTTPException, status

from app.auth import create_access_token, hash_password, verify_password
from app.deps import UserRepoDep
from app.schemas import LoginRequest, RegisterRequest, TokenResponse, UserRead

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
)
async def register(body: RegisterRequest, users: UserRepoDep) -> UserRead:
    if await users.get_by_username(body.username) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already taken",
        )
    user = await users.add(
        username=body.username,
        password_hash=hash_password(body.password),
    )
    return UserRead.model_validate(user)


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, users: UserRepoDep) -> TokenResponse:
    user = await users.get_by_username(body.username)
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )
    token = create_access_token(user_id=user.id, username=user.username)
    return TokenResponse(access_token=token)
```

**Разбор:** роут тонкий: валидация body → репозиторий → ответ.  
Пароль в `add` не передаём сырым — только `password_hash`.  
При логине одну и ту же ошибку отдаём и для «нет пользователя», и для «неверный пароль» — чтобы не подсказывать, существует ли ник.

---

## Код: `app/routes/__init__.py`

```python
from fastapi import FastAPI

from app.routes import auth


def register_routes(app: FastAPI) -> None:
    app.include_router(auth.router)
```

В `app/main.py` внутри `create_app` **после** exception handler, перед `return app`:

```python
from app.routes import register_routes
# ...
    register_routes(app)
    return app
```

(импорт можно сверху файла.)

В `.env` должны быть `JWT_SECRET` и `JWT_EXPIRE_MINUTES` (есть в `.env.example`).

Обновите `app/repositories/__init__.py`:

```python
from app.repositories.base import BaseRepository
from app.repositories.users import UserRepository

__all__ = ["BaseRepository", "UserRepository"]
```

---

## ✅ Проверка

```bash
curl -s -X POST http://127.0.0.1:8080/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"username":"alice","password":"secret"}'

curl -s -X POST http://127.0.0.1:8080/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"alice","password":"secret"}'
# {"access_token":"...","token_type":"bearer"}
```

Повторный register → 409. Неверный пароль → 401.

**Готово →** [step-04-rooms.md](step-04-rooms.md)
