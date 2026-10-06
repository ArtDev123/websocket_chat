# Шаг 9 — Чеклист

**Предыдущий:** [step-08-frontend.md](step-08-frontend.md) · **Дальше (если успеем):** [step-10-redis.md](step-10-redis.md)

## Задача

Пройти сценарий целиком. Новый код не пишем — только проверка, что слои сложились.

---

## Чеклист

### Инфра

- [ ] `make install` / `.env` из `.env.example`
- [ ] Postgres: `scripts/init_postgres*` **или** `docker compose up`
- [ ] `make migrate` после моделей
- [ ] `GET /health` → `{"status":"ok"}`
- [ ] В каркасе есть `BaseRepository` и handler на `NotFoundError`

### Слой репозиториев

- [ ] В `routes/` и `ws.py` нет прямого `select(...)` / `session.add`
- [ ] `UserRepository`, `RoomRepository`, `MessageRepository` покрывают все обращения к БД

### Auth

- [ ] Register alice / bob
- [ ] Login → `access_token`
- [ ] `/rooms` без токена → 401/403
- [ ] Повторный register → 409

### Комнаты

- [ ] `POST /rooms` создаёт `general`
- [ ] `GET /rooms`, `GET /users` работают

### WebSocket

- [ ] Типы кадров через `WsClientType` / `WsServerType`, не строковые `elif`
- [ ] Исходящие кадры — Pydantic DTO (`WsSystemOut`, `WsMessageOut`, …)
- [ ] `join` / `leave` / `message` / `dm` — отдельные короткие `handle_*`
- [ ] Два клиента в комнате видят одно сообщение с одним `id`
- [ ] История REST совпадает с live

### DM

- [ ] Онлайн: кадр у обоих
- [ ] Оффлайн: запись в БД + `GET /dm/{id}`

### UI

- [ ] http://127.0.0.1:8080/ — логин, join, чат, DM в двух окнах

### Docker (по желанию)

- [ ] `docker compose up --build`, UI на `:8080`

---

## Что получилось

| Слой | Реализация |
|------|------------|
| REST | тонкие роуты + DTO |
| БД | только репозитории (`BaseRepository` + потомки) |
| Realtime | `/ws`, `match` по enum, `handle_*` |
| Кадры | Pydantic in/out |
| Рассылка | `ConnectionManager` в памяти процесса |
| Клиент | static HTML |

Ограничение для финального обсуждения: **второй воркер Uvicorn не шарит `manager`**. Если есть время — [step-10-redis.md](step-10-redis.md).

---

## Карта файлов (итог)

```text
app/
  main.py                 # lifespan, NotFoundError→404, routes, static
  config.py
  db.py
  errors.py               # был в каркасе
  models.py
  schemas.py              # REST + WS DTO + message_to_*
  enums.py                # WsClientType / WsServerType
  auth.py
  deps.py                 # UserRepoDep / RoomRepoDep / MessageRepoDep
  manager.py
  repositories/
    base.py               # был в каркасе
    users.py
    rooms.py
    messages.py
  routes/
    __init__.py
    auth.py
    users.py
    rooms.py
    messages.py
    ws.py                 # resolve_user, dispatch, handle_*
  static/
    index.html
```

**Основной гайд закончен.** Опционально → [step-10-redis.md](step-10-redis.md)
