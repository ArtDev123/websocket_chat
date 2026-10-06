import jwt
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from app.auth import decode_token_payload
from app.enums import WsClientType
from app.errors import NotFoundError
from app.manager import manager
from app.models import User
from app.repositories.rooms import RoomRepository
from app.repositories.users import UserRepository
from app.schemas import WsErrorOut, WsIncoming, WsSystemOut

router = APIRouter(tags=["ws"])


async def resolve_user(token: str, session_factory) -> User | None:
    try:
        payload = decode_token_payload(token)
    except jwt.PyJWTError:
        return None
    user_id = int(payload["sub"])
    async with session_factory() as session:
        users = UserRepository(session)
        try:
            return await users.get(user_id)
        except NotFoundError:
            return None


async def send_error(user_id: int, text: str) -> None:
    await manager.send_dto(user_id, WsErrorOut(text=text))


async def handle_join(user: User, data: WsIncoming, session_factory) -> None:
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


async def handle_leave(user: User, data: WsIncoming) -> None:
    if data.room_id is None:
        await send_error(user.id, "room_id required")
        return
    manager.leave_room(data.room_id, user.id)
    await manager.send_dto(
        user.id,
        WsSystemOut(text=f"left room {data.room_id}"),
    )


async def dispatch(user: User, data: WsIncoming, session_factory) -> None:
    match data.type:
        case WsClientType.JOIN:
            await handle_join(user, data, session_factory)
        case WsClientType.LEAVE:
            await handle_leave(user, data)
        case WsClientType.MESSAGE | WsClientType.DM:
            await send_error(user.id, f"{data.type} not implemented yet")
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
