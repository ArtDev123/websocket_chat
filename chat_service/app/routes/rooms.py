from fastapi import APIRouter, HTTPException, status

from app.auth import CurrentUser
from app.deps import RoomRepoDep
from app.schemas import RoomCreate, RoomRead

router = APIRouter(prefix="/rooms", tags=["rooms"])


@router.get("", response_model=list[RoomRead])
async def list_rooms(
    rooms: RoomRepoDep,
    _: CurrentUser,
) -> list[RoomRead]:
    rows = await rooms.get_all()
    return [RoomRead.model_validate(r) for r in rows]


@router.post("", response_model=RoomRead, status_code=status.HTTP_201_CREATED)
async def create_room(
    body: RoomCreate,
    rooms: RoomRepoDep,
    user: CurrentUser,
) -> RoomRead:
    if await rooms.get_by_name(body.name) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Room name already taken",
        )
    room = await rooms.add(name=body.name, created_by_id=user.id)
    return RoomRead.model_validate(room)
