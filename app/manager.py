from fastapi import WebSocket
from pydantic import BaseModel


class ConnectionManager:
    def __init__(self) -> None:
        self.active: dict[int, WebSocket] = {}
        self.rooms: dict[int, set[int]] = {}

    async def connect(self, user_id: int, websocket: WebSocket) -> None:
        await websocket.accept()
        old = self.active.get(user_id)
        if old is not None and old is not websocket:
            await old.close(code=4000)
        self.active[user_id] = websocket

    def disconnect(self, user_id: int) -> None:
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
        await ws.send_json(dto.model_dump(mode="json"))

    async def broadcast_room(self, room_id: int, dto: BaseModel) -> None:
        for uid in list(self.rooms.get(room_id, set())):
            await self.send_dto(uid, dto)


manager = ConnectionManager()
