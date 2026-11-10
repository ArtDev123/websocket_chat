from fastapi import WebSocket, WebSocketDisconnect
from pydantic import BaseModel


class ConnectionManager:
    def __init__(self) -> None:
        self.active: dict[int, WebSocket] = {}
        self.rooms: dict[int, set[int]] = {}

    async def connect(self, user_id: int, websocket: WebSocket) -> None:
        await websocket.accept()
        old = self.active.get(user_id)
        self.active[user_id] = websocket
        if old is None or old is websocket:
            return
        try:
            await old.close(code=4000)
        except (WebSocketDisconnect, RuntimeError):
            pass

    def disconnect(self, user_id: int, websocket: WebSocket | None = None) -> None:
        current = self.active.get(user_id)
        if websocket is not None and current is not websocket:
            return
        self.active.pop(user_id, None)
        empty_rooms = [
            room_id
            for room_id, members in self.rooms.items()
            if user_id in members
        ]
        for room_id in empty_rooms:
            self.leave_room(room_id, user_id)

    def join_room(self, room_id: int, user_id: int) -> None:
        self.rooms.setdefault(room_id, set()).add(user_id)

    def leave_room(self, room_id: int, user_id: int) -> None:
        members = self.rooms.get(room_id)
        if not members:
            return
        members.discard(user_id)
        if not members:
            del self.rooms[room_id]

    async def send_dto(self, user_id: int, dto: BaseModel) -> None:
        ws = self.active.get(user_id)
        if ws is None:
            return
        try:
            await ws.send_json(dto.model_dump(mode="json"))
        except (WebSocketDisconnect, RuntimeError):
            self.disconnect(user_id, ws)

    async def broadcast_room(
        self,
        room_id: int,
        dto: BaseModel,
        exclude_user_id: int | None = None,
    ) -> None:
        for uid in list(self.rooms.get(room_id, set())):
            if uid == exclude_user_id:
                continue
            await self.send_dto(uid, dto)


manager = ConnectionManager()
