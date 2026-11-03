# Шаг 2 — Pytest на тестовой базе

**Предыдущий:** [step-01-test-db.md](step-01-test-db.md) · **Следующий:** [step-03-ruff.md](step-03-ruff.md)

## Задача

Прогнать регистрацию user-сервиса и создание комнаты в чате так, чтобы открывалась только `*_test`. Брокер для этих тестов не поднимается.

## Теория

`Settings` в обоих сервисах создаётся один раз, при импорте `app.config`, и сразу читает окружение и `.env`. Если тест импортирует приложение, а потом выставит `POSTGRES_DB`, будет поздно: URL уже собран из `user_db` или `chat_db`. Поэтому `conftest.py` пишет переменные **до** любого `import app`.

Имя зашито в `TEST_DB`, а не взято из окружения. Иначе случайный `export POSTGRES_DB=user_db` в шелле снова привёл бы pytest в рабочую базу. Строка `endswith("_test")` стоит сразу под присваиванием: поменяете имя на `user_db` — сессия даже не начнётся.

Миграции накатывает `alembic upgrade head` один раз на сессию, отдельным процессом. Ему уходит уже подменённое окружение. Между тестами таблицы очищаются `TRUNCATE`, чтобы второй тест не увидел `alice` от первого. Очистка стоит после `yield`: она выполняется и когда тест упал.

User-сервис в lifespan зовёт брокера. `TestClient` этот lifespan запускает. Без подмены тест пытался бы открыть RabbitMQ и падал бы с ошибкой сети, хотя ручка регистрации здесь ни при чём. Подменяются три имени: `app.main.connect_broker`, `app.main.close_broker` и `app.routes.auth.publish_user_registered`. Последнее именно в модуле роута: `from app.broker import publish_user_registered` скопировал функцию в `app.routes.auth`. Подмена `app.broker.publish_user_registered` роут бы не задела.

Чат токен не выпускает. Тест подписывает JWT сам, тем секретом, который лежит в `settings`. Так проверяется граница разреза: чату достаточно подписи, таблица `users` ему не нужна.

Зависимости тестов — в `requirements-dev.txt`. Боевой образ их не ставит.

## Код

Одинаково для обоих сервисов, `requirements-dev.txt`:

```text
-r requirements.txt
httpx2>=2
pytest>=8.3
pytest-asyncio>=0.24
ruff>=0.8
```

`pytest.ini` тоже одинаковый. `asyncio_mode = auto` нужен фикстуре, которая чистит таблицы через asyncpg. `asyncio_default_fixture_loop_scope = function` задаёт область цикла явно: без этой строки свежий pytest-asyncio пишет предупреждение и обещает сменить умолчание. `httpx2` — клиент, на котором `TestClient` в текущем Starlette ходит в приложение. В боевой образ он не входит.

```ini
[pytest]
asyncio_mode = auto
asyncio_default_fixture_loop_scope = function
pythonpath = .
testpaths = tests
```

`user_service/tests/conftest.py`:

```python
import os
import subprocess
import sys
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

TEST_DB = "user_test"
os.environ["POSTGRES_DB"] = TEST_DB
os.environ["POSTGRES_USER"] = "user_user"
os.environ["POSTGRES_PASSWORD"] = "user_pass"
os.environ["POSTGRES_HOST"] = "localhost"
os.environ["POSTGRES_PORT"] = "5436"

if not TEST_DB.endswith("_test"):
    raise RuntimeError(
        f"pytest отказывается открыть базу {TEST_DB!r}: имя должно кончаться на _test"
    )


@pytest.fixture(scope="session")
def migrated() -> None:
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=ROOT,
        env=os.environ.copy(),
        check=True,
    )


@pytest.fixture(autouse=True)
async def clean_tables(migrated: None) -> AsyncIterator[None]:
    yield
    from app.config import settings

    engine = create_async_engine(settings.database_url)
    async with engine.begin() as conn:
        await conn.execute(text("TRUNCATE users RESTART IDENTITY CASCADE"))
    await engine.dispose()
```

`chat_service/tests/conftest.py` — тот же файл, с тремя отличиями: `TEST_DB = "chat_test"`, пользователь `chat_user` / `chat_pass`, порт `5437`, а `TRUNCATE` чистит `messages, rooms, user_profiles`.

`user_service/tests/test_auth.py`:

```python
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import settings


def _patch_broker(monkeypatch) -> None:
    async def _ok(*args, **kwargs) -> None:
        return None

    monkeypatch.setattr("app.main.connect_broker", _ok)
    monkeypatch.setattr("app.main.close_broker", _ok)
    monkeypatch.setattr("app.routes.auth.publish_user_registered", _ok)


def test_register_and_login_use_test_database(monkeypatch) -> None:
    _patch_broker(monkeypatch)
    assert settings.postgres_db == "user_test"

    from app.main import app

    with TestClient(app) as client:
        health = client.get("/health")
        assert health.status_code == 200
        assert health.json() == {"status": "ok"}

        created = client.post(
            "/auth/register",
            json={"username": "alice", "password": "secret"},
        )
        assert created.status_code == 201
        assert created.json()["username"] == "alice"

        logged = client.post(
            "/auth/login",
            json={"username": "alice", "password": "secret"},
        )
        assert logged.status_code == 200
        token = logged.json()["access_token"]

        users = client.get("/users", headers={"Authorization": f"Bearer {token}"})
        assert users.status_code == 200
        assert [row["username"] for row in users.json()] == ["alice"]


async def test_current_database_is_user_test() -> None:
    engine = create_async_engine(settings.database_url)
    async with engine.connect() as conn:
        name = await conn.scalar(text("SELECT current_database()"))
    await engine.dispose()
    assert name == "user_test"
```

`chat_service/tests/test_rooms.py`:

```python
import jwt
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import settings


def _token(user_id: int = 1, username: str = "alice") -> str:
    return jwt.encode(
        {"sub": str(user_id), "username": username},
        settings.jwt_secret,
        algorithm="HS256",
    )


def test_health_and_create_room() -> None:
    assert settings.postgres_db == "chat_test"

    from app.main import app

    with TestClient(app) as client:
        health = client.get("/health")
        assert health.status_code == 200
        assert health.json() == {"status": "ok"}

        created = client.post(
            "/rooms",
            json={"name": "general"},
            headers={"Authorization": f"Bearer {_token()}"},
        )
        assert created.status_code == 201
        body = created.json()
        assert body["name"] == "general"
        assert body["created_by_id"] == 1


async def test_current_database_is_chat_test() -> None:
    engine = create_async_engine(settings.database_url)
    async with engine.connect() as conn:
        name = await conn.scalar(text("SELECT current_database()"))
    await engine.dispose()
    assert name == "chat_test"
```

## Разбор кода

`TestClient` ходит в приложение в процессе, без порта `8081`. Порт `5436` нужен только базе. Поэтому рабочий user-api на `8081` тесту не мешает.

`assert settings.postgres_db == "user_test"` падает раньше, чем тест успеет что-то записать, если подмена окружения не сработала.

`SELECT current_database()` спрашивает сам Postgres. Совпадение с `settings` значит, что URL и живое соединение — одна и та же база.

`created_by_id == 1` приходит из claim `sub` токена. Строки в `user_profiles` для этого запроса нет: создание комнаты пользователя в базе чата не ищет.

## ✅ Проверка

Базы из шага 1 должны быть запущены.

```bash
cd user_service
pip install -r requirements-dev.txt
pytest

cd ../chat_service
pip install -r requirements-dev.txt
pytest
```

Ожидание: оба прогона зелёные, в выводе нет `user_db` и `chat_db`.

✅ Готово, когда pytest обоих сервисов проходит.
