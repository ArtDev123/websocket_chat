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