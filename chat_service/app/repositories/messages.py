from collections.abc import Sequence

from sqlalchemy import select, or_
from sqlalchemy.orm import selectinload

from app.models import Message
from app.repositories.base import BaseRepository


class MessageRepository(BaseRepository[Message]):
    model = Message

    async def list_for_room(
        self, room_id: int, *, limit: int = 50
    ) -> Sequence[Message]:
        result = await self._session.execute(
            select(Message)
            .where(Message.room_id == room_id)
            .options(selectinload(Message.sender))
            .order_by(Message.id.desc())
            .limit(limit)
        )
        rows = list(result.scalars().all())
        rows.reverse()
        return rows

    async def add_room_message(
        self, *, room_id: int, sender_id: int, text: str
    ) -> Message:
        msg = await self.add(
            text=text,
            sender_id=sender_id,
            room_id=room_id,
            recipient_id=None,
        )
        # после commit relationship может быть не загружен — читаем с selectinload
        result = await self._session.execute(
            select(Message)
            .where(Message.id == msg.id)
            .options(selectinload(Message.sender))
        )
        return result.scalar_one()

    async def list_dm(
            self, user_a: int, user_b: int, *, limit: int = 50
    ) -> Sequence[Message]:
        result = await self._session.execute(
            select(Message)
            .where(
                Message.room_id.is_(None),
                or_(
                    (Message.sender_id == user_a)
                    & (Message.recipient_id == user_b),
                    (Message.sender_id == user_b)
                    & (Message.recipient_id == user_a),
                ),
            )
            .options(selectinload(Message.sender))
            .order_by(Message.id.desc())
            .limit(limit)
        )
        rows = list(result.scalars().all())
        rows.reverse()
        return rows

    async def add_dm(
            self, *, sender_id: int, recipient_id: int, text: str
    ) -> Message:
        msg = await self.add(
            text=text,
            sender_id=sender_id,
            room_id=None,
            recipient_id=recipient_id,
        )
        result = await self._session.execute(
            select(Message)
            .where(Message.id == msg.id)
            .options(selectinload(Message.sender))
        )
        return result.scalar_one()