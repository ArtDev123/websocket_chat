from datetime import datetime

from pydantic import BaseModel, Field
from app.enums import WsClientType, WsServerType
from app.models import Message


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


class RoomCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class RoomRead(BaseModel):
    id: int
    name: str
    created_by_id: int
    created_at: datetime

    model_config = {"from_attributes": True}


class WsIncoming(BaseModel):
    """Общий входной кадр. Лишние поля игнорируем, нужные проверим в handle_*."""

    type: WsClientType
    room_id: int | None = None
    text: str | None = None
    to_user_id: int | None = None


class WsSystemOut(BaseModel):
    type: WsServerType = WsServerType.SYSTEM
    text: str


class WsErrorOut(BaseModel):
    type: WsServerType = WsServerType.ERROR
    text: str


class WsMessageOut(BaseModel):
    type: WsServerType = WsServerType.MESSAGE
    id: int
    room_id: int
    sender_id: int
    sender: str
    text: str
    created_at: datetime

    @classmethod
    def from_message_model(cls, msg: Message) -> "WsMessageOut":
        return WsMessageOut(
            id=msg.id,
            room_id=msg.room_id,
            sender_id=msg.sender_id,
            sender=msg.sender.username,
            text=msg.text,
            created_at=msg.created_at,
        )


class WsDmOut(BaseModel):
    type: WsServerType = WsServerType.DM
    id: int
    sender_id: int
    sender: str
    recipient_id: int
    text: str
    created_at: datetime

    @classmethod
    def from_message_model(cls, msg: Message) -> "WsDmOut":
        return WsDmOut(
            id=msg.id,
            sender_id=msg.sender_id,
            sender=msg.sender.username,
            recipient_id=msg.recipient_id,
            text=msg.text,
            created_at=msg.created_at,
        )


class MessageRead(BaseModel):
    id: int
    text: str
    sender_id: int
    sender: str
    room_id: int | None = None
    recipient_id: int | None = None
    created_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_message_model(cls, msg: Message) -> "MessageRead":
        return MessageRead(
            id=msg.id,
            text=msg.text,
            sender_id=msg.sender_id,
            sender=msg.sender.username,
            room_id=msg.room_id,
            recipient_id=msg.recipient_id,
            created_at=msg.created_at,
        )