# Шаг 6 — Два origin в клиенте

**Предыдущий:** [step-05-consumer.md](step-05-consumer.md) · **Следующий:** [step-07-final.md](step-07-final.md)

## Задача

Страницу по-прежнему отдаёт чат (`http://127.0.0.1:8082/`). Регистрация, логин и список пользователей уходят на user-сервис `:8081`. Чат больше не обслуживает `/auth` и `/users`. Комнаты, история и сокет остаются на том же origin, что и страница.

## Теория

Браузер считает `127.0.0.1:8082` и `127.0.0.1:8081` разными сайтами. `fetch` на 8081 с заголовком `Authorization` и `Content-Type: application/json` — не «простой» запрос, браузер сначала шлёт `OPTIONS`. User-сервис должен ответить, что origin чата разрешён. Иначе кнопка Login в консоли браузера покажет CORS, хотя `curl` с хоста уже работает: у curl нет политики origin.

Сокет к чату остаётся `location.host`. Его на user-сервис переносить не нужно.

## Код

В `user_service/app/main.py` добавьте middleware. `cors_origin_list` уже есть в `config.py` с шага 2, в compose задан `CORS_ORIGINS`.

```python
from fastapi.middleware.cors import CORSMiddleware
```

Сразу после создания `FastAPI(...)`:

```python
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["*"],
        allow_headers=["*"],
    )
```

Пересоберите user-сервис: `docker compose -f user_service/docker-compose.yml up --build -d`.

В `chat_service/app/static/index.html` поменяйте клиент. Абзац под заголовком:

```html
  <p class="muted">Учебный клиент. Логин и список пользователей — user-сервис :8081, комнаты и сокет — этот чат.</p>
```

В начале скрипта:

```javascript
  const USER_API = "http://127.0.0.1:8081";
```

`api` принимает базу. Пустая база — тот же origin, то есть чат.

```javascript
  function api(path, options = {}, base = "") {
    const headers = Object.assign(
      { "Content-Type": "application/json" },
      options.headers || {}
    );
    if (token) headers["Authorization"] = `Bearer ${token}`;
    return fetch(`${base}${path}`, { ...options, headers }).then(async (r) => {
```

Три вызова получают третий аргумент `USER_API`:

- `refreshUsers`: `api("/users", {}, USER_API)`
- регистрация: `api("/auth/register", { ... }, USER_API)`
- логин: `api("/auth/login", { ... }, USER_API)`

`/rooms`, история и `/ws` остаются без базы. `wsUrl()` не меняется.

Пересоберите чат, чтобы в образ попал новый `index.html`.

## Разбор кода

`allow_origins` — список конкретных origin, не `*`. Секрет здесь не кука, а заголовок, но явный список всё равно честнее: страница чата — единственный браузерный клиент этого урока.

Токен по-прежнему кладётся в `localStorage` и уходит и на 8081, и на 8082. Оба сервиса проверяют его одним секретом. User-сервис дополнительно находит строку в своей таблице (`GET /users`, `GET /auth/me`). Чат — нет.

## ✅ Проверка

Откройте http://127.0.0.1:8082/ . Зарегистрируйте новое имя (старые с прошлых шагов уже заняты), залогиньтесь. В списке комнат можно создать комнату, Join, отправить текст. В логе строка вида `[room 1] имя: текст`. Имя берётся из проекции, не из таблицы паролей.

Если Login красный в консоли из-за CORS — user-сервис не пересобран с middleware либо открыли страницу как `localhost`, а в `CORS_ORIGINS` есть только `127.0.0.1`. В compose разрешены оба.

**Готово →** [step-07-final.md](step-07-final.md)
