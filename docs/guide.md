# Чат на WebSocket — обзор и архитектура

Пошаговая реализация — в [README.md](README.md). Здесь — **карта**: зачем сокет, какие слои, какой протокол.

> Не пишите код «вперёд гайда». Сначала таблицы и auth → REST → сокет → DM → HTML.

---

## 1. Зачем этот урок

Обычный HTTP удобен для разовых действий: «зарегистрируйся», «создай комнату», «дай историю». Клиент спросил — сервер ответил — соединение закрылось.

В чате сообщения появляются **когда угодно**. Если опрашивать `GET /messages` каждую секунду, будет поздно, шумно и бессмысленно нагружать сервер.

**WebSocket** — долгое соединение: клиент один раз подключился, и сервер сам присылает новые кадры, как только кто-то написал.

```text
без WebSocket                         с WebSocket
────────────────                      ───────────
клиент: GET /messages?after=…         клиент: открыл /ws один раз
клиент: GET /messages?after=…         сервер: сам пушит новый текст
клиент: GET /messages?after=…         клиент: рисует строку
```

На уроке собираем мини-чат:

1. Регистрация / логин (логин + пароль → JWT).
2. Комнаты (создать, список).
3. Общий чат комнаты по WebSocket.
4. Личные сообщения (DM) по тому же сокету.
5. Простая HTML-страница (два окна = два пользователя).

---

## 2. Слои приложения (как в aiohttp-уроке)

```text
роут / WebSocket-хендлер
        │  только HTTP/WS, DTO, статус-коды
        ▼
репозиторий  (UserRepository, RoomRepository, …)
        │  только SQLAlchemy: get / add / история
        ▼
AsyncSession → PostgreSQL
```

| Слой | Знает | Не знает |
|------|--------|----------|
| роут / WS | URL, JWT, JSON-кадры, `ConnectionManager` | `select`, `commit` |
| репозиторий | модель, запросы, commit | FastAPI, статус-коды, сокеты |
| `BaseRepository` | общий CRUD | конкретную бизнес-логику чата |

В каркасе уже лежит `app/repositories/base.py` и `app/errors.py` (`NotFoundError`) — те же идеи, что в FastAPI-части aiohttp-урока. Конкретные репозитории (`User`, `Room`, `Message`) добавите по шагам.

**Правило урока:** если нужен доступ к БД — пишите метод репозитория. В роуте и в `ws.py` не должно быть `select(...)`.

---

## 3. Два канала: REST и WS

| Канал | Задачи |
|-------|--------|
| REST | register, login, список users/rooms, **история** сообщений |
| WebSocket | live: join/leave, новые сообщения комнаты, DM |

Историю отдаём REST (`GET /rooms/{id}/messages`). Сокету не обязательно тащить «все старые 500» при каждом подключении — UI сам сходит за историей после `join`.

```text
браузер                         FastAPI                         Postgres
   │  POST /auth/login               │                              │
   │ ───────────────────────────────►│ UserRepository               │
   │ ◄──────── {access_token} ───────│                              │
   │  WS /ws?token=…                 │                              │
   │ ───────────────────────────────►│ JWT → user_id                │
   │  {"type":"join","room_id":1}    │ RoomRepository.get           │
   │  {"type":"message",...}         │ MessageRepository.add        │
   │ ◄──── broadcast (DTO → JSON) ───│ ConnectionManager            │
```

---

## 4. Модели (шаг 2)

```text
users     id, username, password_hash, created_at
rooms     id, name, created_by_id → users, created_at
messages  id, text, sender_id, created_at
          room_id      NULL  — сообщение в комнате
          recipient_id NULL  — личное сообщение
```

У сообщения заполнен **либо** `room_id`, **либо** `recipient_id`. Проверку делаем в коде (репозиторий / хендлер), не обязательно CHECK в БД.

«Членства» в комнате в БД нет: кто авторизован и знает `room_id` — может войти. Для урока достаточно.

---

## 5. Протокол кадров (enum + DTO)

Строки `"join"` / `"dm"` в коде не сравниваем руками — заводим `enum`. Тела кадров — Pydantic-модели: валидация и `model_dump()` вместо словарей «из головы».

Клиент → сервер:

| type (enum) | поля | смысл |
|-------------|------|--------|
| `join` | `room_id` | подписаться на комнату |
| `leave` | `room_id` | отписаться |
| `message` | `room_id`, `text` | написать в комнату |
| `dm` | `to_user_id`, `text` | личное |

Сервер → клиент:

| type | поля | смысл |
|------|------|--------|
| `system` | `text` | служебное |
| `message` | id, room_id, sender_id, sender, text, created_at | комната |
| `dm` | id, sender_id, sender, recipient_id, text, created_at | ЛС |
| `error` | `text` | ошибка кадра |

Токен: `ws://127.0.0.1:8080/ws?token=<jwt>`. Браузерный `WebSocket` не умеет заголовок `Authorization` при рукопожатии — query проще всего.

---

## 6. ConnectionManager

В памяти **одного** процесса Uvicorn:

```text
active:  user_id → WebSocket
rooms:   room_id → {user_id, …}
```

- `connect` / `disconnect` — кто онлайн;
- `join_room` / `leave_room` — подписки;
- `broadcast_room` / `send_to_user` — доставка уже готового DTO.

Второй воркер этих словарей не видит. На шаге 10 (если успеем) — Redis pub/sub.

---

## 7. Карта API после гайда

`http://127.0.0.1:8080`, Swagger: `/docs`.

| Метод | URL | Назначение |
|-------|-----|------------|
| GET | `/health` | каркас + БД |
| POST | `/auth/register` | регистрация |
| POST | `/auth/login` | JWT |
| GET | `/users` | список для DM |
| GET/POST | `/rooms` | список / создать |
| GET | `/rooms/{id}/messages` | история комнаты |
| GET | `/dm/{user_id}` | история ЛС |
| WS | `/ws?token=…` | live |
| GET | `/` | HTML (шаг 8) |

---

## 8. Структура после гайда

```text
app/
  main.py              # lifespan, NotFoundError → 404, роуты, static
  config.py
  db.py
  errors.py            # уже в каркасе
  models.py
  schemas.py           # REST + WS DTO
  enums.py             # WsClientType / WsServerType
  auth.py
  deps.py              # Depends на репозитории
  manager.py
  repositories/
    base.py            # уже в каркасе
    users.py
    rooms.py
    messages.py
  routes/
    auth.py
    users.py
    rooms.py
    messages.py
    ws.py              # короткие handle_* + match по enum
  static/index.html
```

---

## 9. Этапы

| # | Файл | Что делаете |
|---|------|-------------|
| 1 | [step-01-setup.md](step-01-setup.md) | запуск каркаса |
| 2 | [step-02-models.md](step-02-models.md) | таблицы |
| 3 | [step-03-auth.md](step-03-auth.md) | UserRepository + JWT |
| 4 | [step-04-rooms.md](step-04-rooms.md) | RoomRepository + REST |
| 5 | [step-05-ws.md](step-05-ws.md) | enum, DTO, join/leave |
| 6 | [step-06-messages.md](step-06-messages.md) | MessageRepository + чат |
| 7 | [step-07-dm.md](step-07-dm.md) | DM |
| 8 | [step-08-frontend.md](step-08-frontend.md) | HTML |
| 9 | [step-09-final.md](step-09-final.md) | чеклист |
| 10 | [step-10-redis.md](step-10-redis.md) | Redis (опционально) |

**Старт:** [README.md](README.md)
