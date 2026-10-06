from datetime import datetime

from pydantic import BaseModel, Field
from app.enums import WsClientType, WsServerType

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


class WsDmOut(BaseModel):
    type: WsServerType = WsServerType.DM
    id: int
    sender_id: int
    sender: str
    recipient_id: int
    text: str
    created_at: datetime
