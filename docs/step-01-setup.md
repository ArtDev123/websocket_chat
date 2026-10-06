# Шаг 1 — Запуск каркаса

**Предыдущий:** [README](README.md) · **Следующий:** [step-02-models.md](step-02-models.md)

## Задача

Поднять venv и PostgreSQL, убедиться что каркас отвечает: `GET /health` → `{"status":"ok"}`. Код приложения на этом шаге **не дописываем** — только запускаем то, что уже в репозитории.

---

## Теория: что уже лежит в каркасе

Представьте приложение как слоёный пирог. Сейчас испечена только «форма» — ещё нет пользователей и чата, но инфраструктура готова.

| Файл | Простыми словами |
|------|------------------|
| `app/config.py` | Читает `.env` и собирает URL к Postgres |
| `app/db.py` | Умеет открыть async-сессию и отдать её в хендлер через `Depends` |
| `app/errors.py` | Своя ошибка `NotFoundError` → в `main` уже мапится в HTTP 404 |
| `app/repositories/base.py` | Общий CRUD (`get_all` / `get` / `add` / `update`) — как в aiohttp-уроке |
| `app/models.py` | Пока только пустой `Base` — таблицы появятся на шаге 2 |
| `app/main.py` | FastAPI + lifespan + `/health` |
| Alembic / Docker / Makefile | миграции и запуск в контейнерах |

`/health` делает `SELECT 1` через сессию: так мы проверяем не только «Python жив», но и «до БД достучались».

Позже SQL будут писать **только** потомки `BaseRepository`. Роуты к `select` не полезут.

---

## 1. Окружение

```bash
cd websockets_lesson
cp .env.example .env
make install
source .venv/bin/activate   # Windows: .\.venv\Scripts\Activate.ps1
```

---

## 2. PostgreSQL

Локально:

```bash
# Linux
./scripts/init_postgres.sh

# macOS
./scripts/init_postgres_mac.sh

# Windows
powershell -ExecutionPolicy Bypass -File scripts\init_postgres.ps1
```

В `.env` по умолчанию: `chat_db` / `chat_user` / `chat_pass`, порт `5432`.

Или только Docker-БД:

```bash
docker compose up -d db
```

Тогда для локального `make run` в `.env`:

```env
POSTGRES_HOST=localhost
POSTGRES_PORT=5433
```

(Compose пробрасывает `5433:5432`.)

---

## 3. Запуск

```bash
make run
```

- http://127.0.0.1:8080/health  
- http://127.0.0.1:8080/docs  

---

## ✅ Проверка

```bash
curl -s http://127.0.0.1:8080/health
# {"status":"ok"}
```

Если 500 / connection refused — БД не запущена или порт/пароль в `.env` не совпадают со скриптом.

**Готово →** [step-02-models.md](step-02-models.md)
