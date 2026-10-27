from fastapi import APIRouter, HTTPException
from starlette import status

from app.auth import CurrentUser
from app.deps import MessageRepoDep, RoomRepoDep, UserRepoDep
from app.errors import NotFoundError
from app.schemas import MessageRead

router = APIRouter(tags=["messages"])


@router.get("/rooms/{room_id}/messages", response_model=list[MessageRead])
async def room_history(
    room_id: int,
    rooms: RoomRepoDep,
    messages: MessageRepoDep,
    _: CurrentUser,
    limit: int = 50,
) -> list[MessageRead]:

    await rooms.get(room_id)

    rows = await messages.list_for_room(room_id, limit=min(limit, 100))
    return [MessageRead.from_message_model(m) for m in rows]


@router.get("/dm/{user_id}", response_model=list[MessageRead])
async def dm_history(
    user_id: int,
    profiles: ProfileRepoDep,
    messages: MessageRepoDep,
    me: CurrentUser,
    limit: int = 50,
) -> list[MessageRead]:
    if user_id == me.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot open DM with yourself",
        )
    await profiles.get(user_id)
    rows = await messages.list_dm(me.id, user_id, limit=min(limit, 100))
    return [MessageRead.from_message_model(m) for m in rows]