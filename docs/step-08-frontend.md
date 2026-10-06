# Шаг 8 — HTML-клиент

**Предыдущий:** [step-07-dm.md](step-07-dm.md) · **Следующий:** [step-09-final.md](step-09-final.md)

## Задача

Отдать простую страницу на `/`: логин/регистрация, список комнат, чат комнаты, DM. Без React — один `index.html` + немного JS. Два окна браузера (или один обычный + инкогнито) = два пользователя.

---

## Теория: зачем отдельная HTML-страница

Бэкенд уже умеет REST и WebSocket. Чтобы не отвлекаться на React/Vue, делаем **один** файл: форма логина, выбор комнаты, лог сообщений, поле ввода. Два окна браузера (обычное + инкогнито) = alice и bob.

Как устроена связка:

1. REST (`fetch`) — register/login, список комнат и users, подгрузка истории.
2. WebSocket — live-кадры. В JSON по-прежнему строки `"join"`, `"message"`, `"dm"` — они совпадают со значениями `WsClientType` / `WsServerType` на сервере.
3. JWT кладём в `localStorage` и в query сокета: `ws://host/ws?token=...`.

FastAPI отдаёт файл так:

- `StaticFiles` на `/static` — на будущее (css/js), если разрежете страницу;
- `GET /` → `FileResponse` на `index.html`, чтобы открыть чат с корня.

Для localhost протокол сокета — `ws://`. `wss://` нужен только за HTTPS.

---

## Код: `app/static/index.html`

Создайте каталог `app/static/` и файл:

```html
<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>WebSocket Chat</title>
  <style>
    :root {
      --bg: #0f1419;
      --panel: #1a2332;
      --line: #2d3a4f;
      --text: #e7ecf3;
      --muted: #8b9bb4;
      --accent: #3d9cf0;
      --ok: #3ecf8e;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0; font-family: "Segoe UI", system-ui, sans-serif;
      background: radial-gradient(1200px 600px at 10% -10%, #1b2a44, var(--bg));
      color: var(--text); min-height: 100vh;
    }
    main { max-width: 960px; margin: 0 auto; padding: 1.5rem; }
    h1 { font-weight: 650; letter-spacing: -0.02em; }
    .card {
      background: color-mix(in srgb, var(--panel) 92%, black);
      border: 1px solid var(--line); border-radius: 12px; padding: 1rem;
      margin-bottom: 1rem;
    }
    label { display: block; font-size: 0.85rem; color: var(--muted); margin-bottom: 0.25rem; }
    input, select, button, textarea {
      font: inherit; border-radius: 8px; border: 1px solid var(--line);
      background: #0c1118; color: var(--text); padding: 0.5rem 0.7rem;
    }
    button {
      background: var(--accent); border-color: transparent; cursor: pointer;
      font-weight: 600;
    }
    button.secondary { background: transparent; border-color: var(--line); }
    .row { display: flex; gap: 0.5rem; flex-wrap: wrap; align-items: end; }
    .row > div { flex: 1; min-width: 140px; }
    #log {
      height: 320px; overflow: auto; background: #0c1118;
      border: 1px solid var(--line); border-radius: 8px; padding: 0.75rem;
      font-family: ui-monospace, monospace; font-size: 0.85rem;
      white-space: pre-wrap;
    }
    .muted { color: var(--muted); }
    .ok { color: var(--ok); }
    .err { color: #ff6b6b; }
    #auth-panel.hidden, #chat-panel.hidden { display: none; }
  </style>
</head>
<body>
<main>
  <h1>WebSocket Chat</h1>
  <p class="muted">Учебный клиент: REST + один сокет на пользователя.</p>

  <section id="auth-panel" class="card">
    <div class="row">
      <div>
        <label>Username</label>
        <input id="username" value="alice" />
      </div>
      <div>
        <label>Password</label>
        <input id="password" type="password" value="secret" />
      </div>
      <button type="button" id="btn-register">Register</button>
      <button type="button" id="btn-login">Login</button>
    </div>
    <p id="auth-status" class="muted"></p>
  </section>

  <section id="chat-panel" class="card hidden">
    <div class="row">
      <div>
        <label>Комната</label>
        <select id="rooms"></select>
      </div>
      <button type="button" id="btn-refresh-rooms" class="secondary">Обновить</button>
      <button type="button" id="btn-join">Join</button>
      <div>
        <label>Новая комната</label>
        <input id="new-room" placeholder="general" />
      </div>
      <button type="button" id="btn-create-room">Создать</button>
    </div>
    <div class="row" style="margin-top:0.75rem">
      <div>
        <label>DM пользователю</label>
        <select id="users"></select>
      </div>
      <button type="button" id="btn-load-dm" class="secondary">История DM</button>
      <button type="button" id="btn-logout" class="secondary">Logout</button>
    </div>
    <p id="ws-status" class="muted"></p>
    <div id="log"></div>
    <div class="row" style="margin-top:0.75rem">
      <div style="flex:3">
        <label>Текст</label>
        <input id="text" placeholder="сообщение…" style="width:100%" />
      </div>
      <button type="button" id="btn-send-room">В комнату</button>
      <button type="button" id="btn-send-dm">DM</button>
    </div>
  </section>
</main>
<script>
  const $ = (id) => document.getElementById(id);
  const logEl = $("log");
  let token = localStorage.getItem("token") || "";
  let ws = null;
  let currentRoomId = null;

  function log(line, cls = "") {
    const div = document.createElement("div");
    if (cls) div.className = cls;
    div.textContent = line;
    logEl.appendChild(div);
    logEl.scrollTop = logEl.scrollHeight;
  }

  function api(path, options = {}) {
    const headers = Object.assign(
      { "Content-Type": "application/json" },
      options.headers || {}
    );
    if (token) headers["Authorization"] = `Bearer ${token}`;
    return fetch(path, { ...options, headers }).then(async (r) => {
      const text = await r.text();
      let data = null;
      try { data = text ? JSON.parse(text) : null; } catch { data = text; }
      if (!r.ok) throw new Error(typeof data === "object" ? (data.detail || JSON.stringify(data)) : text);
      return data;
    });
  }

  function showChat(loggedIn) {
    $("auth-panel").classList.toggle("hidden", loggedIn);
    $("chat-panel").classList.toggle("hidden", !loggedIn);
  }

  function wsUrl() {
    const proto = location.protocol === "https:" ? "wss" : "ws";
    return `${proto}://${location.host}/ws?token=${encodeURIComponent(token)}`;
  }

  function connectWs() {
    if (ws) { try { ws.close(); } catch {} }
    ws = new WebSocket(wsUrl());
    $("ws-status").textContent = "connecting…";
    ws.onopen = () => { $("ws-status").innerHTML = '<span class="ok">ws connected</span>'; };
    ws.onclose = () => { $("ws-status").innerHTML = '<span class="err">ws closed</span>'; };
    ws.onmessage = (ev) => {
      let data;
      try { data = JSON.parse(ev.data); } catch { log(ev.data); return; }
      if (data.type === "error") log(`error: ${data.text}`, "err");
      else if (data.type === "system") log(`* ${data.text}`, "muted");
      else if (data.type === "message")
        log(`[room ${data.room_id}] ${data.sender}: ${data.text}`);
      else if (data.type === "dm")
        log(`[dm] ${data.sender} → ${data.recipient_id}: ${data.text}`);
      else log(JSON.stringify(data));
    };
  }

  async function refreshRooms() {
    const rooms = await api("/rooms");
    const sel = $("rooms");
    sel.innerHTML = "";
    rooms.forEach((r) => {
      const opt = document.createElement("option");
      opt.value = r.id;
      opt.textContent = `${r.id}: ${r.name}`;
      sel.appendChild(opt);
    });
  }

  async function refreshUsers() {
    const users = await api("/users");
    const sel = $("users");
    sel.innerHTML = "";
    users.forEach((u) => {
      const opt = document.createElement("option");
      opt.value = u.id;
      opt.textContent = `${u.id}: ${u.username}`;
      sel.appendChild(opt);
    });
  }

  async function afterLogin() {
    showChat(true);
    connectWs();
    await refreshRooms();
    await refreshUsers();
  }

  $("btn-register").onclick = async () => {
    try {
      await api("/auth/register", {
        method: "POST",
        body: JSON.stringify({
          username: $("username").value,
          password: $("password").value,
        }),
      });
      $("auth-status").textContent = "registered, now login";
    } catch (e) {
      $("auth-status").textContent = e.message;
    }
  };

  $("btn-login").onclick = async () => {
    try {
      const data = await api("/auth/login", {
        method: "POST",
        body: JSON.stringify({
          username: $("username").value,
          password: $("password").value,
        }),
      });
      token = data.access_token;
      localStorage.setItem("token", token);
      await afterLogin();
    } catch (e) {
      $("auth-status").textContent = e.message;
    }
  };

  $("btn-logout").onclick = () => {
    token = "";
    localStorage.removeItem("token");
    if (ws) ws.close();
    showChat(false);
  };

  $("btn-refresh-rooms").onclick = () => refreshRooms().catch((e) => log(e.message, "err"));
  $("btn-create-room").onclick = async () => {
    try {
      await api("/rooms", {
        method: "POST",
        body: JSON.stringify({ name: $("new-room").value }),
      });
      await refreshRooms();
    } catch (e) { log(e.message, "err"); }
  };

  $("btn-join").onclick = async () => {
    currentRoomId = Number($("rooms").value);
    ws.send(JSON.stringify({ type: "join", room_id: currentRoomId }));
    try {
      const history = await api(`/rooms/${currentRoomId}/messages`);
      logEl.innerHTML = "";
      history.forEach((m) => log(`[room ${m.room_id}] ${m.sender}: ${m.text}`));
    } catch (e) { log(e.message, "err"); }
  };

  $("btn-load-dm").onclick = async () => {
    const uid = Number($("users").value);
    try {
      const history = await api(`/dm/${uid}`);
      logEl.innerHTML = "";
      history.forEach((m) =>
        log(`[dm] ${m.sender} → ${m.recipient_id}: ${m.text}`)
      );
    } catch (e) { log(e.message, "err"); }
  };

  $("btn-send-room").onclick = () => {
    const text = $("text").value.trim();
    if (!text || !currentRoomId) return;
    ws.send(JSON.stringify({ type: "message", room_id: currentRoomId, text }));
    $("text").value = "";
  };

  $("btn-send-dm").onclick = () => {
    const text = $("text").value.trim();
    const to = Number($("users").value);
    if (!text || !to) return;
    ws.send(JSON.stringify({ type: "dm", to_user_id: to, text }));
    $("text").value = "";
  };

  if (token) afterLogin().catch(() => showChat(false));
</script>
</body>
</html>
```

---

## Код: отдать страницу из `app/main.py`

Импорты:

```python
from pathlib import Path

from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
```

В `create_app` после `register_routes(app)`:

```python
    static_dir = Path(__file__).resolve().parent / "static"
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/")
    async def index() -> FileResponse:
        return FileResponse(static_dir / "index.html")

    return app
```

Убедитесь, что `/health` объявлен **до** mount или не перекрывается — сейчас `/health` остаётся отдельным роутом, mount только `/static`, всё ок.

---

## Docker: статика в образе

`Dockerfile` уже копирует `COPY app ./app` — `static/` попадёт в образ. Менять Dockerfile не нужно.

---

## ✅ Проверка

1. `make run`, открыть http://127.0.0.1:8080/
2. Зарегистрировать alice и bob (второе окно / инкогнито).
3. Создать комнату `general`, оба Join.
4. Переписка в комнате видна обоим.
5. DM: выбрать пользователя → «DM» → у онлайн-собеседника появляется кадр; «История DM» подтягивает REST.

**Готово →** [step-09-final.md](step-09-final.md)
