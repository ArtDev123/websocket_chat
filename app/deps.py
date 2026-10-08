from typing import Annotated

from fastapi import Depends

from app.db import SessionDep
from app.repositories.messages import MessageRepository
from app.repositories.rooms import RoomRepository
from app.repositories.users import UserRepository


def get_user_repository(session: SessionDep) -> UserRepository:
    return UserRepository(session)


def get_room_repository(session: SessionDep) -> RoomRepository:
    return RoomRepository(session)


def get_message_repository(session: SessionDep) -> MessageRepository:
    return MessageRepository(session)


UserRepoDep = Annotated[UserRepository, Depends(get_user_repository)]
RoomRepoDep = Annotated[RoomRepository, Depends(get_room_repository)]
MessageRepoDep = Annotated[MessageRepository, Depends(get_message_repository)]
