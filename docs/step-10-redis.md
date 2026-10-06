# Шаг 10 — Redis pub/sub (если успеем)

**Предыдущий:** [step-09-final.md](step-09-final.md)

## Задача

Переписать рассылку так, чтобы **несколько воркеров** Uvicorn видели одни и те же события. Локальный `ConnectionManager` остаётся: он знает только сокеты **этого** процесса. Между процессами — канал Redis.

Это необязательный хвост. Если времени нет — достаточно понимания проблемы из чеклиста.

---

## Теория: почему памяти процесса мало

Представьте два процесса Uvicorn за одним портом (или два контейнера за балансировщиком). У каждого свой `ConnectionManager` в RAM.

```text
клиент A ──► worker-1 (manager знает только A)
клиент B ──► worker-2 (manager знает только B)

A пишет в комнату
  → worker-1 сохраняет через MessageRepository (БД общая — ок)
  → worker-1 делает broadcast_room → видит только своих
  → B молчит, хотя «в той же комнате»
```

Redis pub/sub — «радио» между воркерами:

```text
worker-1: publish chat:events  {DTO сообщения}
worker-2: subscribe            → send_dto локальному B
```

Важно разделить обязанности:

| Что | Где остаётся |
|-----|----------------|
| INSERT сообщения | `MessageRepository` (без изменений) |
| список «кто в комнате на этом процессе» | локальный `manager.rooms` |
| факт «появилось новое сообщение» | Redis publish |
| доставка в живой сокет | listener на каждом воркере → `manager.send_dto` |

Подписки `join` по-прежнему локальные: B подключился к worker-2, значит worker-2 и так знает `B ∈ room`. Pub/sub несёт **событие**, не список мемберов.

Репозитории и enum/DTO **не ломаем**: в Redis кладёте тот же JSON, что уходит клиенту (`WsMessageOut.model_dump(mode="json")`).

---

## Что добавить в инфру

`requirements.txt`:

```text
redis>=5.0
```

`.env.example`:

```env
REDIS_URL=redis://localhost:6379/0
```

В `docker-compose.yml` — сервис `redis` и у `app`:

```yaml
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  app:
    environment:
      REDIS_URL: redis://redis:6379/0
    depends_on:
      redis:
        condition: service_healthy
```

(healthcheck как в aiohttp-уроке: `redis-cli ping`.)

Для нескольких процессов локально:

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8080 --workers 2
```

Reload с несколькими workers обычно не смешивают — для проверки лучше без `--reload`.

---

## Набросок кода (собираете сами по схеме)

### `app/config.py`

Поле `redis_url: str = "redis://localhost:6379/0"`.

### `app/manager.py` — publish после локальной логики

Идея: методы `publish_room(room_id, payload)` / `publish_user(user_id, payload)` пишут в Redis. Локальный `broadcast_room` **не** вызываем напрямую из ws-хендлера — только publish. Слушатель на каждом воркере вызывает `send_to_user` / локальный обход `self.rooms`.

Каналы:

| Событие | Канал | Кто доставляет |
|---------|--------|----------------|
| сообщение комнаты | `chat:room:{room_id}` | воркеры, у кого есть мемберы room в `self.rooms` |
| DM | `chat:user:{user_id}` | воркер, где `user_id in self.active` |

Либо один канал `chat:events` и в JSON: `{"scope":"room","room_id":1,...}` / `{"scope":"user","user_id":2,...}`.

### Lifespan

На старте:

1. `redis.asyncio.from_url(settings.redis_url)`
2. `asyncio.create_task(listener())` — `pubsub.subscribe("chat:events")`, цикл `get_message`, разбор, доставка
3. На shutdown — cancel task, `aclose()`

Хендлер `message` / `dm` после commit: `await redis.publish("chat:events", json.dumps(...))`.

---

## На что обратить внимание

- Не публиковать пароли/токены в канале — только кадры как клиенту.
- Идемпотентность: один publish → каждый воркер шлёт своим сокетам один раз; отправитель получит кадр от **своего** воркера, когда listener обработает сообщение (или сразу локально + skip на listener — договоритесь об одном способе, иначе будет дубль).
- Простой способ без дублей: **только** publish, даже на том воркере, куда пришёл кадр; listener везде доставляет. Тогда эхо отправителю придёт из listener, не из хендлера.
- Postgres по-прежнему источник правды для истории.

---

## ✅ Проверка (когда сделаете)

1. `docker compose up` с Redis.
2. Uvicorn с `--workers 2`.
3. Два браузера: несколько reconnect, пока A и B не окажутся на разных воркерах (или просто шлите много сообщений — при workers=2 часть попадёт «вразнобой»).
4. Сообщение комнаты видно обоим; DM — тоже.
5. История REST без изменений.

---

## Итог шага

| Было | Стало |
|------|--------|
| broadcast только в памяти процесса | событие через Redis, доставка локальным сокетам |
| один worker | несколько workers / несколько машин за балансировщиком |

Если шаг не успели закодить на занятии — достаточно устно разобрать схему и оставить как домашнее.
