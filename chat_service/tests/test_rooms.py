import jwt
from unittest.mock import AsyncMock
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import settings


def _patch_broker(monkeypatch) -> None:
    mock = AsyncMock()
    mock.close.return_value = None

    monkeypatch.setattr("app.main.start_consumer", mock)


def _token(user_id: int = 1, username: str = "alice") -> str:
    return jwt.encode(
        {"sub": str(user_id), "username": username},
        settings.jwt_secret,
        algorithm="HS256",
    )


def test_health_and_create_room(monkeypatch) -> None:
    _patch_broker(monkeypatch)
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