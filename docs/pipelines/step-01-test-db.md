# Шаг 1 — Тестовая база у каждого сервиса

**Предыдущий:** [guide.md](guide.md) · **Следующий:** [step-02-tests.md](step-02-tests.md)

## Задача

Поднять рядом с рабочими базами ещё две: `user_test` и `chat_test`. Приложение в них пока не ходит. Этот шаг только про контейнер Postgres.

## Теория

Зачем имя базы кончается на `_test` и почему это не `user_db` — в [guide.md](guide.md), раздел «Почему тестовая база — не рабочая».

Compose берёт имя проекта из каталога. Каталог `user_service` уже занят рабочим `docker-compose.yml`. Второй файл в том же каталоге без своего `name:` попадёт в тот же проект и пересоздаст контейнер `db`. Первая строка `name: user_service_test` (и `chat_service_test` у чата) держит тестовый Postgres отдельно. Тома нет: данные теста не нужны после `down`, и удалять рабочий volume этот файл не может — его здесь просто нет.

Порты `5436` и `5437` не пересекаются ни друг с другом, ни с рабочими `5435` и `5434`. Оба контейнера можно держать запущенными вместе с обычным стендом.

Пользователь и пароль те же, что у рабочего сервиса. Меняется имя базы. Так `conftest` на следующем шаге переключает только `POSTGRES_DB` и порт, а не заводит второй набор секретов.

## Код

`user_service/docker-compose.test.yml`:

```yaml
name: user_service_test

services:
  db:
    image: postgres:16
    environment:
      POSTGRES_DB: user_test
      POSTGRES_USER: user_user
      POSTGRES_PASSWORD: user_pass
    ports:
      - "5436:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U user_user -d user_test"]
      interval: 3s
      timeout: 3s
      retries: 10
```

`chat_service/docker-compose.test.yml`:

```yaml
name: chat_service_test

services:
  db:
    image: postgres:16
    environment:
      POSTGRES_DB: chat_test
      POSTGRES_USER: chat_user
      POSTGRES_PASSWORD: chat_pass
    ports:
      - "5437:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U chat_user -d chat_test"]
      interval: 3s
      timeout: 3s
      retries: 10
```

## Разбор кода

`name` — имя проекта Compose, не имя базы. Базу задаёт `POSTGRES_DB`.

`pg_isready -d user_test` ждёт именно эту базу. Без `-d` проверка сказала бы «сервер жив», даже если база не создалась. `--wait` на следующем шаге опирается на этот healthcheck.

Сети `lesson-net` здесь нет. Тестовой базе не с кем разговаривать, кроме pytest на хосте.

## ✅ Проверка

Из корня репозитория:

```bash
docker compose -f user_service/docker-compose.test.yml up -d --wait
docker compose -f chat_service/docker-compose.test.yml up -d --wait
docker compose -f user_service/docker-compose.test.yml exec db \
  psql -U user_user -d user_test -c "SELECT current_database();"
docker compose -f chat_service/docker-compose.test.yml exec db \
  psql -U chat_user -d chat_test -c "SELECT current_database();"
```

Ожидание: `user_test` и `chat_test`. Рабочий `docker compose up` в `user_service/` при этом не пересоздаётся: `docker ps` показывает отдельный контейнер проекта `user_service_test`.

✅ Готово, когда обе команды `SELECT` вернули своё имя.
