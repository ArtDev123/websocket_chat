import jwt
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from app.auth import decode_token_payload
from app.enums import WsClientType
from app.errors import NotFoundError
from app.manager import manager
from app.repositories.messages import MessageRepository
from app.repositories.rooms import RoomRepository
from app.auth import TokenUser, decode_token_payload
from app.repositories.profiles import UserProfileRepository
from app.schemas import WsErrorOut, WsIncoming, WsSystemOut, WsMessageOut, WsDmOut

router = APIRouter(tags=["ws"])


def resolve_user(token: str) -> TokenUser | None:
    try:
        payload = decode_token_payload(token)
    except jwt.PyJWTError:
        return None
    return TokenUser(id=int(payload["sub"]), username=str(payload["username"]))


async def send_error(user_id: int, text: str) -> None:
    await manager.send_dto(user_id, WsErrorOut(text=text))


async def handle_join(user: TokenUser, data: WsIncoming, session_factory) -> None:
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


async def handle_leave(user: TokenUser, data: WsIncoming) -> None:
    if data.room_id is None:
        await send_error(user.id, "room_id required")
        return
    manager.leave_room(data.room_id, user.id)
    await manager.send_dto(
        user.id,
        WsSystemOut(text=f"left room {data.room_id}"),
    )


async def handle_message(user: TokenUser, data: WsIncoming, session_factory) -> None:
    if data.room_id is None:
        await send_error(user.id, "room_id required")
        return

    text = (data.text or "").strip()
    if not text:
        await send_error(user.id, "empty text")
        return

    if user.id not in manager.rooms.get(data.room_id, set()):
        await send_error(user.id, "join the room first")
        return

    async with session_factory() as session:
        rooms = RoomRepository(session)
        messages = MessageRepository(session)
        try:
            await rooms.get(data.room_id)
        except NotFoundError:
            await send_error(user.id, "room not found")
            return
        msg = await messages.add_room_message(
            room_id=data.room_id,
            sender_id=user.id,
            text=text,
        )

    await manager.broadcast_room(data.room_id, WsMessageOut.from_message_model(msg))


async def handle_dm(user: TokenUser, data: WsIncoming, session_factory) -> None:
    if data.to_user_id is None:
        await send_error(user.id, "to_user_id required")
        return

    text = (data.text or "").strip()
    if not text:
        await send_error(user.id, "empty text")
        return

    if data.to_user_id == user.id:
        await send_error(user.id, "cannot DM yourself")
        return

    async with session_factory() as session:
        profiles = UserProfileRepository(session)
        messages = MessageRepository(session)
        try:
            await profiles.get(data.to_user_id)
        except NotFoundError:
            await send_error(user.id, "user not found")
            return

        msg = await messages.add_dm(
            sender_id=user.id,
            recipient_id=data.to_user_id,
            text=text,
        )

    dto = WsDmOut.from_message_model(msg)
    await manager.send_dto(user.id, dto)
    await manager.send_dto(data.to_user_id, dto)


async def dispatch(user: TokenUser, data: WsIncoming, session_factory) -> None:
    match data.type:
        case WsClientType.JOIN:
            await handle_join(user, data, session_factory)
        case WsClientType.LEAVE:
            await handle_leave(user, data)
        case WsClientType.MESSAGE:
            await handle_message(user, data, session_factory)
        case WsClientType.DM:
            await handle_dm(user, data, session_factory)
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
