# Шаг 4 — Chat-сервис без таблицы паролей

**Предыдущий:** [step-03-publish.md](step-03-publish.md) · **Следующий:** [step-05-consumer.md](step-05-consumer.md)

## Задача

Перенести комнаты, сообщения и WebSocket в `chat_service`. Своя база `chat_db`, API на `8082`. Паролей здесь нет. `CurrentUser` собирается из JWT. Таблица `user_profiles` создаётся сразу, но наполнять её будет консьюмер на следующем шаге.

## Теория

`created_by_id`, `sender_id` и `recipient_id` остаются целыми числами: это id из user-сервиса. `ForeignKey` на `users` убрать нельзя «наполовину» — таблицы `users` в этой базе нет. `room_id` по-прежнему ссылается на `rooms`: обе таблицы живут здесь.

Имя отправителя в кадре по-прежнему берётся как `msg.sender.username`. Связь `Message.sender` смотрит на `UserProfile`, не на `User`. В базе это не внешний ключ, только `primaryjoin` для SQLAlchemy. Пока проекция пустая, отправка сообщения упадёт на пустом `sender`. Поэтому на этом шаге проверяем комнату, а не текст.

Сокет больше не делает `UserRepository.get`. Подпись токена либо верна, либо нет. Что пользователя уже скопировали в `user_profiles`, для входа в сокет не требуется.

## Код

Каталог `chat_service/`. Скопируйте без правок:

- `docker-entrypoint.sh`, `alembic.ini`, `alembic/env.py`
- `app/db.py`, `app/errors.py`, `app/enums.py`, `app/manager.py`
- `app/repositories/base.py`, `app/repositories/rooms.py`, `app/repositories/messages.py`
- `app/routes/rooms.py`
- `app/static/index.html` (два origin поправите на шаге 6)

`chat_service/requirements.txt`:

```text
aio-pika>=9.4
alembic>=1.13
asyncpg
fastapi>=0.115
greenlet
psycopg2-binary
pydantic>=2.0
pydantic-settings>=2.0
PyJWT>=2.8
python-dotenv>=1.0
SQLAlchemy[asyncio]>=2.0,<2.2
uvicorn[standard]>=0.32
websockets>=12.0
```

`bcrypt` не нужен: пароли проверяет user-сервис.

Dockerfile — копия user-сервиса, в конце `EXPOSE 8082`.

`chat_service/docker-compose.yml`:

```yaml
services:
  db:
    image: postgres:16
    environment:
      POSTGRES_DB: chat_db
      POSTGRES_USER: chat_user
      POSTGRES_PASSWORD: chat_pass
    ports:
      - "5434:5432"
    volumes:
      - chat_pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U chat_user -d chat_db"]
      interval: 3s
      timeout: 3s
      retries: 10
    networks:
      - backend

  chat-api:
    build: .
    ports:
      - "8082:8082"
    environment:
      POSTGRES_DB: chat_db
      POSTGRES_USER: chat_user
      POSTGRES_PASSWORD: chat_pass
      POSTGRES_HOST: db
      POSTGRES_PORT: 5432
      APP_HOST: 0.0.0.0
      APP_PORT: 8082
      JWT_SECRET: lesson-secret-key-at-least-32b
      JWT_EXPIRE_MINUTES: 1440
      RABBITMQ_URL: amqp://guest:guest@rabbitmq:5672/
    depends_on:
      db:
        condition: service_healthy
    networks:
      - backend
      - lesson-net

networks:
  backend:
  lesson-net:
    external: true
    name: lesson-net

volumes:
  chat_pgdata:
```

`JWT_SECRET` тот же, что у user-сервиса.

`chat_service/.env.example`:

```text
POSTGRES_DB=chat_db
POSTGRES_USER=chat_user
POSTGRES_PASSWORD=chat_pass
POSTGRES_HOST=localhost
POSTGRES_PORT=5434
APP_HOST=127.0.0.1
APP_PORT=8082

JWT_SECRET=lesson-secret-key-at-least-32b
JWT_EXPIRE_MINUTES=1440

RABBITMQ_URL=amqp://guest:guest@localhost:5672/
```

`chat_service/app/config.py`:

```python
from urllib.parse import quote_plus

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    postgres_db: str = "chat_db"
    postgres_user: str = "chat_user"
    postgres_password: str = "chat_pass"
    postgres_host: str = "localhost"
    postgres_port: int = 5434
    app_host: str = "127.0.0.1"
    app_port: int = 8082

    jwt_secret: str = "lesson-secret-key-at-least-32b"
    jwt_expire_minutes: int = 1440

    rabbitmq_url: str = "amqp://guest:guest@localhost:5672/"

    @property
    def database_url(self) -> str:
        password = quote_plus(self.postgres_password)
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def database_url_sync(self) -> str:
        password = quote_plus(self.postgres_password)
        return (
            f"postgresql+psycopg2://{self.postgres_user}:{password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


settings = Settings()
```

`chat_service/app/models.py`:

```python
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class UserProfile(Base):
    """Локальная копия id и username. Пароля здесь нет — его пишет консьюмер."""

    __tablename__ = "user_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Room(Base):
    __tablename__ = "rooms"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    created_by_id: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    messages: Mapped[list["Message"]] = relationship(back_populates="room")


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    text: Mapped[str] = mapped_column(Text)
    sender_id: Mapped[int] = mapped_column(Integer, index=True)
    room_id: Mapped[int | None] = mapped_column(
        ForeignKey("rooms.id"), nullable=True, index=True
    )
    recipient_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    sender: Mapped[UserProfile | None] = relationship(
        primaryjoin="foreign(Message.sender_id) == UserProfile.id",
        viewonly=True,
    )
    room: Mapped[Room | None] = relationship(back_populates="messages")
```

`id` профиля без `autoincrement`: число приходит из события и должно совпасть с `users.id`. Свой sequence выдал бы другие id.

`chat_service/app/auth.py` — проверка подписи, без базы:

```python
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from app.config import settings

bearer_scheme = HTTPBearer(auto_error=True)


class TokenUser(BaseModel):
    """Пользователь из подписи JWT. В таблице чата его может ещё не быть."""

    id: int
    username: str


def decode_token_payload(token: str) -> dict:
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
    credentials: Annotated[
        HTTPAuthorizationCredentials, Depends(bearer_scheme)
    ],
) -> TokenUser:
    payload = decode_token(credentials.credentials)
    return TokenUser(id=int(payload["sub"]), username=str(payload["username"]))


CurrentUser = Annotated[TokenUser, Depends(get_current_user)]
```

`chat_service/app/repositories/profiles.py` пока умеет только то, что даёт `BaseRepository` (`get` / `get_all`). Метод `upsert` — на шаге 5.

```python
from app.models import UserProfile
from app.repositories.base import BaseRepository


class UserProfileRepository(BaseRepository[UserProfile]):
    model = UserProfile
```

`chat_service/app/deps.py`:

```python
from typing import Annotated

from fastapi import Depends

from app.db import SessionDep
from app.repositories.messages import MessageRepository
from app.repositories.profiles import UserProfileRepository
from app.repositories.rooms import RoomRepository


def get_room_repository(session: SessionDep) -> RoomRepository:
    return RoomRepository(session)


def get_message_repository(session: SessionDep) -> MessageRepository:
    return MessageRepository(session)


def get_profile_repository(session: SessionDep) -> UserProfileRepository:
    return UserProfileRepository(session)


RoomRepoDep = Annotated[RoomRepository, Depends(get_room_repository)]
MessageRepoDep = Annotated[MessageRepository, Depends(get_message_repository)]
ProfileRepoDep = Annotated[UserProfileRepository, Depends(get_profile_repository)]
```

`app/schemas.py` скопируйте из монолита и удалите `RegisterRequest`, `LoginRequest`, `TokenResponse`, `UserRead`. Кадры и `MessageRead` не меняются: `sender.username` теперь читается с `UserProfile`.

`app/routes/messages.py` — история DM ищет человека в проекции, не в `users`. Замените `UserRepoDep` на `ProfileRepoDep` и вызов `users.get` на `profiles.get`. Сигнатура `dm_history`:

```python
async def dm_history(
    user_id: int,
    profiles: ProfileRepoDep,
    messages: MessageRepoDep,
    me: CurrentUser,
    limit: int = 50,
) -> list[MessageRead]:
    if user_id == me.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot open DM with yourself",
        )
    await profiles.get(user_id)
    rows = await messages.list_dm(me.id, user_id, limit=min(limit, 100))
    return [MessageRead.from_message_model(m) for m in rows]
```

`app/routes/ws.py` скопируйте из монолита и поменяйте четыре места. Файл целиком переписывать не нужно.

Импорты: уберите `User` и `UserRepository`. Добавьте `TokenUser` и `UserProfileRepository`.

```python
from app.auth import TokenUser, decode_token_payload
from app.repositories.profiles import UserProfileRepository
```

`resolve_user` больше не открывает сессию:

```python
def resolve_user(token: str) -> TokenUser | None:
    try:
        payload = decode_token_payload(token)
    except jwt.PyJWTError:
        return None
    return TokenUser(id=int(payload["sub"]), username=str(payload["username"]))
```

В аннотациях `handle_join`, `handle_leave`, `handle_message`, `handle_dm`, `dispatch` тип `User` замените на `TokenUser`.

В `handle_dm` вместо `UserRepository` — проекция:

```python
        profiles = UserProfileRepository(session)
        messages = MessageRepository(session)
        try:
            await profiles.get(data.to_user_id)
        except NotFoundError:
            await send_error(user.id, "user not found")
            return
```

В `websocket_endpoint` вызов становится `user = resolve_user(token)` без `session_factory`.

`app/routes/__init__.py`:

```python
from app.routes import messages, rooms, ws


def register_routes(app) -> None:
    app.include_router(rooms.router)
    app.include_router(messages.router)
    app.include_router(ws.router)
```

`app/main.py` на этом шаге ещё не запускает консьюмер. Статика и `/health` — как у монолита. Консьюмер добавите в этот же lifespan на шаге 5.

```python
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.config import settings
from app.db import SessionDep, make_engine, make_session_factory
from app.errors import NotFoundError
from app.routes import register_routes


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    engine = make_engine()
    app.state.engine = engine
    app.state.session_factory = make_session_factory(engine)
    yield
    await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Chat service",
        version="0.1.0",
        description="Комнаты, сообщения и WebSocket. Пользователей берёт из событий.",
        lifespan=lifespan,
    )

    @app.exception_handler(NotFoundError)
    async def not_found_handler(
        request: Request, exc: NotFoundError
    ) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": exc.message})

    @app.get("/health")
    async def health(session: SessionDep) -> dict[str, str]:
        await session.execute(text("SELECT 1"))
        return {"status": "ok"}

    register_routes(app)

    static_dir = Path(__file__).resolve().parent / "static"
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/")
    async def index() -> FileResponse:
        return FileResponse(static_dir / "index.html")

    return app


app = create_app()


def main() -> None:
    uvicorn.run(
        "app.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=True,
    )


if __name__ == "__main__":
    main()
```

`chat_service/alembic/versions/0001_chat.py` создаёт `user_profiles`, `rooms` и `messages`. У `rooms.created_by_id`, `messages.sender_id` и `messages.recipient_id` нет `ForeignKeyConstraint`. У `messages.room_id` внешний ключ на `rooms` остаётся.

```python
"""chat tables without a users foreign key

Revision ID: 0001_chat
Revises:
Create Date: 2026-10-15

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001_chat"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_profiles",
        sa.Column("id", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("username", sa.String(length=50), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_user_profiles_username", "user_profiles", ["username"], unique=True
    )
    op.create_table(
        "rooms",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_rooms_name", "rooms", ["name"], unique=True)
    op.create_table(
        "messages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("sender_id", sa.Integer(), nullable=False),
        sa.Column("room_id", sa.Integer(), nullable=True),
        sa.Column("recipient_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["room_id"], ["rooms.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_messages_recipient_id", "messages", ["recipient_id"])
    op.create_index("ix_messages_room_id", "messages", ["room_id"])
    op.create_index("ix_messages_sender_id", "messages", ["sender_id"])


def downgrade() -> None:
    op.drop_index("ix_messages_sender_id", table_name="messages")
    op.drop_index("ix_messages_room_id", table_name="messages")
    op.drop_index("ix_messages_recipient_id", table_name="messages")
    op.drop_table("messages")
    op.drop_index("ix_rooms_name", table_name="rooms")
    op.drop_table("rooms")
    op.drop_index("ix_user_profiles_username", table_name="user_profiles")
    op.drop_table("user_profiles")
```

## Разбор кода

`foreign(...)` в `primaryjoin` говорит SQLAlchemy: колонка `sender_id` ведёт себя как внешний ключ, хотя в `CREATE TABLE` ограничения нет. `viewonly=True` запрещает писать профиль через `message.sender = ...`. Пишет профиль только консьюмер.

`routes/rooms.py` копируется как есть: у `TokenUser` есть `.id`, роут комнат больше ничего про пользователя не знает.

Пока очередь не объявлена, новые регистрации с шага 3 в чат не попадают. После `up` чата очередь появится на следующем шаге. Уже зарегистрированные alice и bob в проекцию сами не доедут — событие ушло в пустой exchange. На шаге 5 заведите новых пользователей либо зарегистрируйте этих ещё раз после того, как убедитесь, что очередь есть (повторная регистрация того же ника даст 409 и событие не отправит).

## ✅ Проверка

Сначала чат, чтобы к шагу 5 очередь уже существовала. User-сервис с шага 3 пусть работает.

```bash
docker compose -f chat_service/docker-compose.yml up --build -d
curl -s http://127.0.0.1:8082/health
# {"status":"ok"}
```

Токен alice с user-сервиса (`POST /auth/login`). Комната создаётся на чате, не на user:

```bash
curl -s -X POST http://127.0.0.1:8082/rooms \
  -H "Authorization: Bearer ТОКЕН" \
  -H 'Content-Type: application/json' \
  -d '{"name":"general"}'
# 201, "created_by_id" равен id alice
```

`GET /profiles` на этом шаге ещё нет.

**Готово →** [step-05-consumer.md](step-05-consumer.md)
