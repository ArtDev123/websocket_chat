from sqlalchemy.dialects.postgresql import insert

from app.models import UserProfile
from app.repositories.base import BaseRepository


class UserProfileRepository(BaseRepository[UserProfile]):
    model = UserProfile

    async def upsert(self, *, user_id: int, username: str) -> None:
        stmt = insert(UserProfile).values(id=user_id, username=username)
        stmt = stmt.on_conflict_do_update(
            index_elements=[UserProfile.id],
            set_={"username": stmt.excluded.username},
        )
        await self._session.execute(stmt)
        await self._session.commit()
