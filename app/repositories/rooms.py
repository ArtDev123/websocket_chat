from sqlalchemy import select

from app.models import Room
from app.repositories.base import BaseRepository


class RoomRepository(BaseRepository[Room]):
    model = Room

    async def get_by_name(self, name: str) -> Room | None:
        result = await self._session.execute(
            select(Room).where(Room.name == name)
        )
        return result.scalar_one_or_none()
