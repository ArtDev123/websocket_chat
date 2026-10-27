from collections.abc import Sequence
from typing import Any, Generic, TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase

from app.errors import NotFoundError

ModelType = TypeVar("ModelType", bound=DeclarativeBase)


class BaseRepository(Generic[ModelType]):
    model: type[ModelType]

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_all(self) -> Sequence[ModelType]:
        result = await self._session.execute(
            select(self.model).order_by(self.model.id)
        )
        return result.scalars().all()

    async def get(self, id: int) -> ModelType:
        obj = await self._session.get(self.model, id)
        if obj is None:
            raise NotFoundError(f"{self.model.__name__} with id {id} not found")
        return obj

    async def add(self, **fields: Any) -> ModelType:
        obj = self.model(**fields)
        self._session.add(obj)
        await self._session.commit()
        await self._session.refresh(obj)
        return obj

    async def update(self, id: int, **fields: Any) -> ModelType:
        obj = await self.get(id)
        for key, value in fields.items():
            setattr(obj, key, value)
        await self._session.commit()
        await self._session.refresh(obj)
        return obj
