from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from app.auth import TokenUser
from app.enums import WsClientType
from app.manager import ConnectionManager, manager
from app.routes.ws import dispatch, handle_typing
from app.schemas import WsIncoming, WsTypingOut

AUTHOR = 1


@pytest.fixture(autouse=True)
def reset_manager() -> None:
    manager.active.clear()
    manager.rooms.clear()
    yield
    manager.active.clear()
    manager.rooms.clear()


async def test_connect_keeps_new_socket_when_old_is_already_closed() -> None:
    room = ConnectionManager()
    old = AsyncMock()
    old.close.side_effect = RuntimeError(
        'Cannot call "send" once a close message has been sent.'
    )
    new = AsyncMock()
    room.active[1] = old

    await room.connect(1, new)

    assert room.active[1] is new
    new.accept.assert_awaited_once()


def test_disconnect_keeps_replacement_socket() -> None:
    room = ConnectionManager()
    old = AsyncMock()
    new = AsyncMock()
    room.active[1] = new
    room.rooms[7] = {1}

    room.disconnect(1, old)

    assert room.active[1] is new
    assert room.rooms[7] == {1}


async def test_send_dto_drops_closed_socket() -> None:
    room = ConnectionManager()
    ws = AsyncMock()
    ws.send_json.side_effect = RuntimeError(
        'Cannot call "send" once a close message has been sent.'
    )
    room.active[1] = ws
    room.rooms[7] = {1}

    await room.send_dto(1, WsTypingOut(room_id=7, username="a"))

    assert 1 not in room.active
    assert 7 not in room.rooms


@pytest.mark.parametrize(
    ("members", "active", "exclude", "expected"),
    [
        pytest.param([], [], None, [], id="empty-room"),
        pytest.param([1], [], None, [], id="member-without-socket"),
        pytest.param([1], [1], None, [1], id="include-only-member"),
        pytest.param([1], [1], 1, [], id="exclude-only-member"),
        pytest.param([1, 2], [1, 2], None, [1, 2], id="include-everyone"),
        pytest.param([1, 2], [1, 2], 1, [2], id="exclude-sender"),
        pytest.param([1, 2, 3], [1, 3], 1, [3], id="skip-excluded-and-disconnected"),
        pytest.param([1, 2], [1, 2], 99, [1, 2], id="unknown-exclude-id"),
    ],
)
async def test_broadcast_room(members, active, exclude, expected) -> None:
    room = ConnectionManager()
    if members:
        room.rooms[7] = set(members)
    sockets = {uid: AsyncMock() for uid in active}
    room.active.update(sockets)
    dto = WsTypingOut(room_id=7, username="alice")

    await room.broadcast_room(7, dto, exclude_user_id=exclude)

    payload = dto.model_dump(mode="json")
    for uid, ws in sockets.items():
        if uid in expected:
            ws.send_json.assert_awaited_once_with(payload)
        else:
            ws.send_json.assert_not_awaited()


@pytest.mark.parametrize(
    ("room_id", "members", "text", "to_user_id", "username", "repeat", "error"),
    [
        pytest.param(None, set(), None, None, "alice", 1, "room_id required", id="no-room"),
        pytest.param(1, set(), None, None, "alice", 1, "join the room first", id="empty-room"),
        pytest.param(1, {2}, None, None, "alice", 1, "join the room first", id="foreign-member"),
        pytest.param(1, {AUTHOR}, None, None, "alice", 1, None, id="alone"),
        pytest.param(1, {AUTHOR, 2}, "hi", 9, "alice", 1, None, id="extra-fields-ignored"),
        pytest.param(1, {AUTHOR, 2}, None, None, "alice", 2, None, id="repeat"),
        pytest.param(1, {AUTHOR}, None, None, "a", 1, None, id="short-username"),
        pytest.param(1, {AUTHOR}, None, None, "alice bob", 1, None, id="username-with-space"),
    ],
)
async def test_handle_typing(
    room_id,
    members,
    text,
    to_user_id,
    username,
    repeat,
    error,
    monkeypatch,
) -> None:
    if members:
        manager.rooms[1] = set(members)
    sock = AsyncMock()
    manager.active[AUTHOR] = sock
    calls: list[tuple] = []

    async def spy(broadcast_room_id, dto, exclude_user_id=None) -> None:
        calls.append((broadcast_room_id, dto, exclude_user_id))

    monkeypatch.setattr(manager, "broadcast_room", spy)
    user = TokenUser(id=AUTHOR, username=username)
    data = WsIncoming(
        type=WsClientType.TYPING,
        room_id=room_id,
        text=text,
        to_user_id=to_user_id,
    )

    for _ in range(repeat):
        await handle_typing(user, data)

    if error is not None:
        assert calls == []
        sock.send_json.assert_awaited_once_with({"type": "error", "text": error})
        return

    expected = WsTypingOut(room_id=room_id, username=username)
    assert calls == [(room_id, expected, AUTHOR)] * repeat
    sock.send_json.assert_not_awaited()


@pytest.mark.parametrize("client_type", list(WsClientType))
async def test_dispatch_routes_each_type(client_type, monkeypatch) -> None:
    called: list[WsClientType] = []

    def install(name: str, kind: WsClientType) -> None:
        async def fake(*args, **kwargs) -> None:
            called.append(kind)

        monkeypatch.setattr(f"app.routes.ws.{name}", fake)

    install("handle_join", WsClientType.JOIN)
    install("handle_leave", WsClientType.LEAVE)
    install("handle_message", WsClientType.MESSAGE)
    install("handle_dm", WsClientType.DM)
    install("handle_typing", WsClientType.TYPING)

    await dispatch(
        TokenUser(id=AUTHOR, username="alice"),
        WsIncoming(type=client_type, room_id=1, text="x", to_user_id=2),
        None,
    )
    assert called == [client_type]


@pytest.mark.parametrize(
    ("payload", "ok"),
    [
        pytest.param({"type": "nope"}, False, id="unknown-type"),
        pytest.param({"type": "typing"}, True, id="typing-without-room"),
    ],
)
def test_incoming_typing_schema(payload, ok) -> None:
    if not ok:
        with pytest.raises(ValidationError):
            WsIncoming.model_validate(payload)
        return
    data = WsIncoming.model_validate(payload)
    assert data.type is WsClientType.TYPING
    assert data.room_id is None
