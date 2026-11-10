from unittest.mock import AsyncMock

import jwt
import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.manager import manager


@pytest.fixture(autouse=True)
def reset_manager() -> None:
    manager.active.clear()
    manager.rooms.clear()
    yield
    manager.active.clear()
    manager.rooms.clear()


def _patch_broker(monkeypatch) -> None:
    mock = AsyncMock()
    mock.close.return_value = None
    monkeypatch.setattr("app.main.start_consumer", mock)


def _token(user_id: int, username: str) -> str:
    return jwt.encode(
        {"sub": str(user_id), "username": username},
        settings.jwt_secret,
        algorithm="HS256",
    )


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _create_room(client: TestClient, token: str, name: str) -> int:
    created = client.post("/rooms", json={"name": name}, headers=_auth(token))
    assert created.status_code == 201
    return created.json()["id"]


@pytest.mark.parametrize(
    ("setup", "payload", "error"),
    [
        pytest.param("connected", {"type": "typing"}, "room_id required", id="missing-room"),
        pytest.param(
            "connected",
            {"type": "typing", "room_id": None},
            "room_id required",
            id="null-room",
        ),
        pytest.param(
            "connected",
            {"type": "typing", "room_id": "this"},
            "join the room first",
            id="before-join",
        ),
        pytest.param(
            "join-other",
            {"type": "typing", "room_id": "other"},
            "join the room first",
            id="other-room",
        ),
        pytest.param(
            "leave",
            {"type": "typing", "room_id": "this"},
            "join the room first",
            id="after-leave",
        ),
    ],
)
def test_typing_errors(setup, payload, error, monkeypatch) -> None:
    _patch_broker(monkeypatch)
    from app.main import app

    alice = _token(1, "alice")
    with TestClient(app) as client:
        room_id = _create_room(client, alice, "general")
        other_id = _create_room(client, alice, "other")
        body = dict(payload)
        if body.get("room_id") == "this":
            body["room_id"] = room_id
        elif body.get("room_id") == "other":
            body["room_id"] = other_id

        with client.websocket_connect(f"/ws?token={alice}") as ws:
            assert ws.receive_json()["text"] == "connected as alice"
            if setup in {"join-other", "leave"}:
                ws.send_json({"type": "join", "room_id": room_id})
                assert ws.receive_json()["text"] == f"joined room {room_id}"
            if setup == "leave":
                ws.send_json({"type": "leave", "room_id": room_id})
                assert ws.receive_json()["text"] == f"left room {room_id}"
            ws.send_json(body)
            assert ws.receive_json() == {"type": "error", "text": error}


def test_typing_reaches_only_the_other_member(monkeypatch) -> None:
    _patch_broker(monkeypatch)
    from app.main import app

    alice = _token(1, "alice")
    bob = _token(2, "bob")
    with TestClient(app) as client:
        room_id = _create_room(client, alice, "general")
        with (
            client.websocket_connect(f"/ws?token={alice}") as ws_alice,
            client.websocket_connect(f"/ws?token={bob}") as ws_bob,
        ):
            assert ws_alice.receive_json()["text"] == "connected as alice"
            assert ws_bob.receive_json()["text"] == "connected as bob"
            ws_alice.send_json({"type": "join", "room_id": room_id})
            ws_bob.send_json({"type": "join", "room_id": room_id})
            assert ws_alice.receive_json()["text"] == f"joined room {room_id}"
            assert ws_bob.receive_json()["text"] == f"joined room {room_id}"

            ws_alice.send_json({"type": "typing", "room_id": room_id})
            assert ws_bob.receive_json() == {
                "type": "typing",
                "room_id": room_id,
                "username": "alice",
            }
            # Следующий кадр Алисы — ошибка разбора. Если бы typing вернулся ей,
            # он пришёл бы раньше этой ошибки.
            ws_alice.send_json({"type": "nope"})
            assert ws_alice.receive_json() == {
                "type": "error",
                "text": "invalid payload",
            }

        history = client.get(f"/rooms/{room_id}/messages", headers=_auth(alice))
        assert history.status_code == 200
        assert history.json() == []
