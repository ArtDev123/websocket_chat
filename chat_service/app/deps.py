from typing import Annotated

from fastapi import Depends

from app.db import SessionDep
from app.repositories.messages import MessageRepository
from app.repositories.profiles import UserProfileRepository
from app.repositories.rooms import RoomRepository


def get_room_repository(session: SessionDep) -> RoomRepository:
    return RoomRepository(session)


def get_message_repository(session: SessionDep) -> MessageRepository:
    return MessageRepository(session)


def get_profile_repository(session: SessionDep) -> UserProfileRepository:
    return UserProfileRepository(session)


RoomRepoDep = Annotated[RoomRepository, Depends(get_room_repository)]
MessageRepoDep = Annotated[MessageRepository, Depends(get_message_repository)]
ProfileRepoDep = Annotated[UserProfileRepository, Depends(get_profile_repository)]