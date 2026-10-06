# Шаг 2 — Модели и миграция

**Предыдущий:** [step-01-setup.md](step-01-setup.md) · **Следующий:** [step-03-auth.md](step-03-auth.md)

## Задача

Описать таблицы `users`, `rooms`, `messages` и накатить первую миграцию. Репозитории и API ещё не трогаем — сначала схема БД.

---

## Теория: зачем три таблицы

Чат хранит три разных «вещи»:

1. **Кто** пишет — пользователь (логин и хэш пароля).
2. **Куда** можно писать вместе — комната (имя вроде `general`).
3. **Что** написали — сообщение (текст + кто + когда).

Сообщения бывают двух видов: в комнату и лично. Чтобы не плодить две почти одинаковые таблицы, используем **одну** `messages` с двумя необязательными ссылками:

| Ситуация | `room_id` | `recipient_id` |
|----------|-----------|----------------|
| Сообщение в комнате | заполнен | `NULL` |
| Личное (DM) | `NULL` | заполнен |

Так история комнаты — это «все строки с этим `room_id`», а переписка alice↔bob — «строки, где они отправитель и получатель в любом порядке».

Пароль в открытом виде **не храним**. Колонка называется `password_hash`: на шаге 3 туда положим результат bcrypt.

---

## Теория: модель ≠ таблица глазами SQL

SQLAlchemy-модель — Python-класс, который описывает таблицу. Alembic смотрит на `Base.metadata` (уже подключено в `alembic/env.py`) и генерирует SQL `CREATE TABLE`. Вам не нужно писать миграцию руками — достаточно моделей + `make migrations`.

---

## Код: `app/models.py`

Замените файл целиком:

```python
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    rooms_created: Mapped[list["Room"]] = relationship(back_populates="creator")
    messages_sent: Mapped[list["Message"]] = relationship(
        back_populates="sender",
        foreign_keys="Message.sender_id",
    )


class Room(Base):
    __tablename__ = "rooms"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    creator: Mapped[User] = relationship(back_populates="rooms_created")
    messages: Mapped[list["Message"]] = relationship(back_populates="room")


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    text: Mapped[str] = mapped_column(Text)
    sender_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    room_id: Mapped[int | None] = mapped_column(
        ForeignKey("rooms.id"), nullable=True, index=True
    )
    recipient_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    sender: Mapped[User] = relationship(
        back_populates="messages_sent",
        foreign_keys=[sender_id],
    )
    room: Mapped[Room | None] = relationship(back_populates="messages")
    recipient: Mapped[User | None] = relationship(foreign_keys=[recipient_id])
```

---

## Разбор кода

- `Mapped[...]` + `mapped_column` — современный стиль SQLAlchemy 2: тип поля виден и редактору, и БД.
- `server_default=func.now()` — время ставит **Postgres** при INSERT, не ваш ноутбук с кривыми часами.
- У `Message` два внешних ключа на `users` (`sender_id` и `recipient_id`). Без явного `foreign_keys=` SQLAlchemy не поймёт, какая связь к какому столбцу.
- `relationship` нужны, чтобы потом удобно читать `msg.sender.username` (с `selectinload` в репозитории). Сами по себе они таблиц не создают.

---

## Миграция

```bash
make migrations m="users rooms messages"
make migrate
```

Появится файл вроде `alembic/versions/0001_users_rooms_messages.py`. Откройте глазами: должны быть три `create_table`.

---

## ✅ Проверка

```bash
psql "postgresql://chat_user:chat_pass@localhost:5432/chat_db" -c '\dt'
```

(Если БД в Docker — порт `5433`.)

Ожидаются `users`, `rooms`, `messages`, `alembic_version`.  
`GET /health` по-прежнему ок.

**Готово →** [step-03-auth.md](step-03-auth.md)
