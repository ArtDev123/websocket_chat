# WebSocket Chat — FastAPI

Учебный чат на **FastAPI + WebSocket**: комнаты, личные сообщения, простой auth, слой **репозиториев** (как в aiohttp-уроке).

В репозитории уже лежит **каркас**: config, db, `/health`, `BaseRepository`, `NotFoundError`, Alembic, Docker, Makefile. Модели, auth, REST, сокет и фронт — по гайду.

**Старт:** [docs/README.md](docs/README.md)

```bash
# Linux
./scripts/init_postgres.sh

# macOS
./scripts/init_postgres_mac.sh

# Windows (PowerShell)
powershell -ExecutionPolicy Bypass -File scripts\init_postgres.ps1
```

```bash
cp .env.example .env
make install
make run
# http://127.0.0.1:8080/health
# http://127.0.0.1:8080/docs
```

Docker (когда Postgres не хочется ставить локально):

```bash
cp .env.example .env
# в .env: POSTGRES_HOST=db не нужен — compose подставит
docker compose up --build
```

> В Compose Postgres снаружи на порту **5433**. Для локального `make run` без Docker оставьте `POSTGRES_PORT=5432` и локальную БД из `scripts/`.

Следующий урок режет этот монолит на user-сервис и chat-сервис, они общаются через RabbitMQ: [docs/split/README.md](docs/split/README.md).
