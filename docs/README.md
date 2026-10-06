# Чат на WebSocket — документация

Пошаговый гайд: **FastAPI**, **PostgreSQL**, **репозитории**, **JWT-auth**, **комнаты**, **личные сообщения**, простой **HTML-клиент**.

Каркас уже есть: `/health`, `config`, `db`, `BaseRepository`, `NotFoundError`, Alembic, Docker. Остальное — по шагам ниже.

Расчёт на **~2.5 часа**. Redis — опциональный хвост.

## Как читать

1. Сначала [guide.md](guide.md) — что строим, слои, протокол кадров.
2. Затем шаги по порядку — не дальше, пока не отметили «✅ Готово».

В каждом шаге:

1. **Задача** — что должно получиться.
2. **Теория** — своими словами, зачем так.
3. **Код** — что писать в файлы.
4. **Разбор кода** — что делает каждая часть.
5. **✅ Проверка** — `curl` / браузер прямо сейчас.

## Порядок шагов (~150 мин)

| # | Файл | Что делаете | ~мин |
|---|------|-------------|------|
| 0 | [guide.md](guide.md) | Карта | 10 |
| 1 | [step-01-setup.md](step-01-setup.md) | venv, Postgres, `/health` | 10 |
| 2 | [step-02-models.md](step-02-models.md) | модели + миграция | 20 |
| 3 | [step-03-auth.md](step-03-auth.md) | UserRepository, register/login, JWT | 25 |
| 4 | [step-04-rooms.md](step-04-rooms.md) | RoomRepository, REST комнат | 15 |
| 5 | [step-05-ws.md](step-05-ws.md) | enum + DTO + ConnectionManager + join/leave | 25 |
| 6 | [step-06-messages.md](step-06-messages.md) | MessageRepository, чат комнаты | 15 |
| 7 | [step-07-dm.md](step-07-dm.md) | личные сообщения | 15 |
| 8 | [step-08-frontend.md](step-08-frontend.md) | HTML-клиент | 15 |
| 9 | [step-09-final.md](step-09-final.md) | чеклист | 5 |
| 10 | [step-10-redis.md](step-10-redis.md) | *(если успеем)* Redis | — |

> **Правило:** SQL только в репозиториях. Роуты и WebSocket вызывают репозиторий, не пишут `select` сами. Типы кадров — через `enum`, тела — через Pydantic DTO.

## Стек

| Компонент | Зачем |
|-----------|--------|
| FastAPI | REST + WebSocket |
| Uvicorn | ASGI-сервер |
| PostgreSQL | хранение |
| SQLAlchemy 2.x async | ORM |
| **BaseRepository** | весь доступ к БД в одном слое |
| Alembic | миграции |
| Pydantic / enum | DTO и типы кадров |
| PyJWT + bcrypt | простой auth |
| HTML + JS | проверка без фронтенд-стека |

**Старт:** [step-01-setup.md](step-01-setup.md)
