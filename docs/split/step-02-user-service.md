# Шаг 2 — User-сервис и своя база

**Предыдущий:** [step-01-broker.md](step-01-broker.md) · **Следующий:** [step-03-publish.md](step-03-publish.md)

## Задача

Вынести личность из монолита: таблица `users`, регистрация, логин, `GET /users`. Свой Postgres, свой compose, порт API `8081`. Очереди на этом шаге ещё нет — регистрация только пишет строку и отдаёт 201.

## Теория

В монолите `users`, `rooms` и `messages` лежат в одной базе, и у комнат есть `ForeignKey` на `users.id`. После разреза user-сервис про эту связь не знает. Ему оставляем модель `User` без `relationship` на комнаты и сообщения.

Каркас (`db.py`, `errors.py`, `BaseRepository`, Alembic) копируется, а не импортируется из корня. Иначе «два сервиса» на самом деле один пакет с двумя процессами.

Старая ревизия `788c83caced5` создаёт все три таблицы. Её не переносим. Новая ревизия создаёт только `users`.

## Код

Каталог `user_service/` в корне. Скопируйте без правок:

- `docker-entrypoint.sh` из корня репозитория
- `alembic.ini` и `alembic/env.py`
- `app/db.py`, `app/errors.py`
- `app/repositories/base.py`, `app/repositories/users.py`
- `app/auth.py`
- `app/routes/users.py`
- `app/routes/auth.py` (на следующем шаге в `register` добавится publish)

Пустые `app/__init__.py` и `app/repositories/__init__.py`.

`user_service/requirements.txt`:

```text
alembic>=1.13
asyncpg
bcrypt>=4.0
fastapi>=0.115
greenlet
psycopg2-binary
pydantic>=2.0
pydantic-settings>=2.0
PyJWT>=2.8
python-dotenv>=1.0
SQLAlchemy[asyncio]>=2.0,<2.2
uvicorn[standard]>=0.32
```

`aio-pika` добавите на шаге 3.

`user_service/Dockerfile` — как корневой, порт другой:

```dockerfile
FROM python:3.12-slim
WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY alembic.ini .
COPY alembic ./alembic
COPY app ./app
COPY docker-entrypoint.sh /docker-entrypoint.sh

RUN apt-get update && apt-get install -y dos2unix && \
    dos2unix /docker-entrypoint.sh && \
    chmod +x /docker-entrypoint.sh && \
    apt-get --purge remove -y dos2unix && rm -rf /var/lib/apt/lists/*

EXPOSE 8081
ENTRYPOINT ["/docker-entrypoint.sh"]
```

`user_service/docker-compose.yml`:

```yaml
services:
  db:
    image: postgres:16
    environment:
      POSTGRES_DB: user_db
      POSTGRES_USER: user_user
      POSTGRES_PASSWORD: user_pass
    ports:
      - "5433:5432"
    volumes:
      - user_pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U user_user -d user_db"]
      interval: 3s
      timeout: 3s
      retries: 10
    networks:
      - backend

  user-api:
    build: .
    ports:
      - "8081:8081"
    environment:
      POSTGRES_DB: user_db
      POSTGRES_USER: user_user
      POSTGRES_PASSWORD: user_pass
      POSTGRES_HOST: db
      POSTGRES_PORT: 5432
      APP_HOST: 0.0.0.0
      APP_PORT: 8081
      JWT_SECRET: lesson-secret-key-at-least-32b
      JWT_EXPIRE_MINUTES: 1440
      RABBITMQ_URL: amqp://guest:guest@rabbitmq:5672/
      CORS_ORIGINS: http://127.0.0.1:8082,http://localhost:8082
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
  user_pgdata:
```

Сервис назван `user-api`, не `api`. Chat тоже будет в `lesson-net`, и два контейнера с одним именем `api` в общей сети начнут делить DNS-имя.

`user_service/.env.example`:

```text
POSTGRES_DB=user_db
POSTGRES_USER=user_user
POSTGRES_PASSWORD=user_pass
POSTGRES_HOST=localhost
POSTGRES_PORT=5433
APP_HOST=127.0.0.1
APP_PORT=8081

JWT_SECRET=lesson-secret-key-at-least-32b
JWT_EXPIRE_MINUTES=1440

RABBITMQ_URL=amqp://guest:guest@localhost:5672/
CORS_ORIGINS=http://127.0.0.1:8082,http://localhost:8082
```

`user_service/app/config.py` — тот же смысл, что у монолита, плюс URL брокера и список origin для шага 6:

```python
from urllib.parse import quote_plus

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    postgres_db: str = "user_db"
    postgres_user: str = "user_user"
    postgres_password: str = "user_pass"
    postgres_host: str = "localhost"
    postgres_port: int = 5433
    app_host: str = "127.0.0.1"
    app_port: int = 8081

    jwt_secret: str = "lesson-secret-key-at-least-32b"
    jwt_expire_minutes: int = 1440

    rabbitmq_url: str = "amqp://guest:guest@localhost:5672/"
    cors_origins: str = "http://127.0.0.1:8082,http://localhost:8082"

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

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


settings = Settings()
```

`user_service/app/models.py` — только `User`, без связей на комнаты:

```python
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
```

`user_service/app/schemas.py` — кусок монолита про auth, без комнат и кадров:

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

`user_service/app/deps.py` — репозиторий только пользователей:

```python
from typing import Annotated

from fastapi import Depends

from app.db import SessionDep
from app.repositories.users import UserRepository


def get_user_repository(session: SessionDep) -> UserRepository:
    return UserRepository(session)


UserRepoDep = Annotated[UserRepository, Depends(get_user_repository)]
```

`user_service/app/routes/__init__.py`:

```python
from app.routes import auth, users


def register_routes(app) -> None:
    app.include_router(auth.router)
    app.include_router(users.router)
```

`user_service/app/main.py` — без брокера и без CORS. Их добавите следующими шагами. Статики здесь нет: страницу отдаёт чат.

```python
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
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
        title="User service",
        version="0.1.0",
        description="Личность: регистрация, логин, список пользователей.",
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

`user_service/alembic/versions/0001_users.py`:

```python
"""users only

Revision ID: 0001_users
Revises:
Create Date: 2026-10-15

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001_users"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(length=50), nullable=False),
        sa.Column("password_hash", sa.String(length=128), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_username", "users", ["username"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_users_username", table_name="users")
    op.drop_table("users")
```

## Разбор кода

`POSTGRES_HOST=db` действует только внутри compose: контейнер API видит Postgres по имени сервиса. С хоста эта же база доступна как `localhost:5433`, поэтому в `.env.example` порт `5433`.

`JWT_SECRET` совпадает с тем, что потом будет у чата. Подпись проверяется тем же секретом, отдельного запроса «действителен ли токен» нет.

`user-api` сидит в двух сетях: `backend` (только своя база) и `lesson-net` (брокер). База в общую сеть не входит.

Entrypoint, как у монолита, сначала делает `alembic upgrade head`, потом запускает приложение.

## ✅ Проверка

Брокер с шага 1 уже запущен — compose user-сервиса ждёт внешнюю сеть `lesson-net`.

```bash
docker compose -f user_service/docker-compose.yml up --build -d
curl -s http://127.0.0.1:8081/health
# {"status":"ok"}

curl -s -X POST http://127.0.0.1:8081/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"username":"alice","password":"secret"}'
# 201, в теле есть "id" и "username"

curl -s -X POST http://127.0.0.1:8081/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"alice","password":"secret"}'
# {"access_token":"...","token_type":"bearer"}
```

Подставьте токен:

```bash
curl -s http://127.0.0.1:8081/users -H "Authorization: Bearer ТОКЕН"
# список из одного пользователя
```

**Готово →** [step-03-publish.md](step-03-publish.md)
