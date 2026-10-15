# Шаг 7 — Сценарий целиком

**Предыдущий:** [step-06-frontend.md](step-06-frontend.md)

## Задача

Прогнать разрез с пустых баз: два пользователя, оба появляются в проекции чата, сообщение в комнате несёт имя из `user_profiles`, личка с несуществующим id — 404.

Новых файлов нет.

## Теория

Это тот же контур, что собирался по шагам, но в порядке, при котором события не теряются.

1. Брокер, сеть `lesson-net`.
2. Chat. Lifespan объявляет очередь `chat.users` и только потом открывает порт.
3. User. Lifespan подключается к exchange `users`.
4. Регистрация. Commit, затем `user.registered`. Очередь уже есть, консьюмер пишет проекцию.
5. Логин. JWT с `sub` и `username`. Чат подпись проверяет сам.
6. Комната и кадр сокета. `sender` — `username` из `user_profiles`, не из токена и не из базы user-сервиса.

Что на уроке сознательно не сделано:

- **Outbox.** Сейчас commit и publish — два шага. Между ними процесс может умереть: пользователь есть, события нет. Outbox пишет событие в ту же транзакцию, что и строку, и отдельный процесс дочитывает его в брокер.
- **Смена username.** Проекция умеет обновить имя тем же upsert, но user-сервис такого события не шлёт.
- **События от чата к user.** Шине здесь достаточно одного направления. Обратный факт «написал сообщение» user-сервису не нужен.
- **Общий Python-пакет.** Каркас скопирован. Общая библиотека снова связала бы сервисы на этапе сборки.

## ✅ Проверка

Сбросить тома сервисов, брокер оставить:

```bash
docker compose -f user_service/docker-compose.yml down -v
docker compose -f chat_service/docker-compose.yml down -v
docker compose -f rabbit/docker-compose.yml up -d
docker compose -f chat_service/docker-compose.yml up --build -d
docker compose -f user_service/docker-compose.yml up --build -d
```

Дождитесь `{"status":"ok"}` на `http://127.0.0.1:8082/health`, затем на `http://127.0.0.1:8081/health`.

Дальше из контейнера чата (ему видны оба API: user по имени `user-api` в `lesson-net`, сам чат на `127.0.0.1:8082`):

```bash
docker compose -f chat_service/docker-compose.yml exec -T chat-api python - <<'PY'
import asyncio, json, time, urllib.request
import websockets

USER = "http://user-api:8081"
CHAT = "http://127.0.0.1:8082"

def request(method, url, token=None, body=None):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=10) as resp:
        raw = resp.read().decode()
        return resp.status, json.loads(raw) if raw else None

for base in (USER, CHAT):
    status, payload = request("GET", f"{base}/health")
    assert payload == {"status": "ok"}, payload

for name in ("alice", "bob"):
    request("POST", f"{USER}/auth/register", body={"username": name, "password": "secret"})

_, login = request("POST", f"{USER}/auth/login", body={"username": "alice", "password": "secret"})
token = login["access_token"]

deadline = time.time() + 15
profiles = []
while time.time() < deadline:
    _, profiles = request("GET", f"{CHAT}/profiles", token=token)
    if {"alice", "bob"} <= {row["username"] for row in profiles}:
        break
    time.sleep(0.4)
else:
    raise SystemExit(f"profiles: {profiles}")

_, room = request("POST", f"{CHAT}/rooms", token=token, body={"name": "general"})

async def say():
    uri = f"ws://127.0.0.1:8082/ws?token={token}"
    async with websockets.connect(uri) as ws:
        await ws.recv()
        await ws.send(json.dumps({"type": "join", "room_id": room["id"]}))
        await ws.recv()
        await ws.send(json.dumps({
            "type": "message", "room_id": room["id"], "text": "hello",
        }))
        return json.loads(await ws.recv())

frame = asyncio.run(say())
assert frame["sender"] == "alice" and frame["text"] == "hello", frame
_, history = request("GET", f"{CHAT}/rooms/{room['id']}/messages", token=token)
assert history[0]["sender"] == "alice"
print("ok")
PY
```

Ожидаемая последняя строка — `ok`.

Отдельно, с токеном alice, чужой id:

```bash
curl -s -o /dev/null -w "%{http_code}\n" \
  http://127.0.0.1:8082/dm/99999 \
  -H "Authorization: Bearer ТОКЕН"
# 404
```

Страница http://127.0.0.1:8082/ делает то же самое кнопками: регистрация уходит на `:8081`, комната и сокет — на чат, в логе видно имя отправителя.

Монолит в `app/` этот урок не заменяет. Его по-прежнему поднимает корневой `docker compose up`.
