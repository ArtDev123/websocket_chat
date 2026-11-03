# Шаг 4 — Два workflow

**Предыдущий:** [step-03-ruff.md](step-03-ruff.md) · **Следующий:** [step-05-final.md](step-05-final.md)

## Задача

Положить в репозиторий два файла GitHub Actions. На push и на pull request оба стартуют. В каждом три джобы: ruff, pytest, подъём Docker.

## Теория

Почему джобы без `needs` и почему нет фильтра `paths` — в [guide.md](guide.md), разделы «Что такое пайплайн» и «Почему оба workflow стартуют вместе».

Джоба `test` не вызывает `docker-compose.test.yml`. На runner Postgres приходит как `services.db`: GitHub сам поднимает контейнер и пробрасывает порт на localhost. Имя базы, пользователь и порт совпадают с тем, что `conftest` уже зашил. Один и тот же pytest проходит у вас и в CI.

Джоба `docker` собирает обычный compose сервиса, не тестовый. Вопрос другой: встаёт ли образ и отвечает ли `/health` снаружи. Внутри этого compose база по-прежнему `user_db` или `chat_db`. Тесты туда не ходят, а эта джоба в базу ничего не пишет, кроме миграций на пустом томе.

Сеть `lesson-net` объявлена как `external`. Её создаёт compose в `rabbit/`. Поэтому docker-джоба сначала поднимает брокера, потом сервис. Чат в lifespan к брокеру может ещё не подключаться — сеть всё равно должна существовать, иначе compose сервиса не найдёт её.

`curl --retry` закрывает щель: контейнер уже `running`, а uvicorn ещё не слушает порт. Healthcheck в compose есть у Postgres, у API его нет, и `--wait` API не ждёт.

`if: always()` на последнем шаге снимает контейнеры даже когда health не ответил. Иначе следующая джоба на том же runner не при чём (у каждой джобы своя машина), но упавший прогон не должен оставлять контейнеры в её логе без явной остановки. `-v` здесь безопасен: runner пустой, тома созданы этим же прогоном. Локально эту пару команд не копируйте, если в томах уже есть данные с прошлого урока.

## Код

`.github/workflows/user.yml`:

```yaml
name: user

on:
  push:
  pull_request:

jobs:
  lint:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: user_service
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: ruff
        run: |
          pip install -r requirements-dev.txt
          ruff check .

  test:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: user_service
    services:
      db:
        image: postgres:16
        env:
          POSTGRES_DB: user_test
          POSTGRES_USER: user_user
          POSTGRES_PASSWORD: user_pass
        ports:
          - 5436:5432
        options: >-
          --health-cmd "pg_isready -U user_user -d user_test"
          --health-interval 3s
          --health-timeout 3s
          --health-retries 10
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: pytest
        run: |
          pip install -r requirements-dev.txt
          pytest

  docker:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: broker
        working-directory: rabbit
        run: docker compose up -d --wait
      - name: user service
        working-directory: user_service
        run: docker compose up -d --build --wait
      - name: health
        run: curl --fail --retry 10 --retry-delay 2 http://127.0.0.1:8081/health
      - name: down
        if: always()
        run: |
          docker compose -f user_service/docker-compose.yml down -v
          docker compose -f rabbit/docker-compose.yml down -v
```

`.github/workflows/chat.yml` повторяет это для чата. Меняются каталог `chat_service`, база `chat_test`, пользователь `chat_user` / `chat_pass`, порт `5437` и проверка `http://127.0.0.1:8082/health`. В конце `down` вызывается для `chat_service/docker-compose.yml` и для брокера.

## Разбор кода

`on: push` без списка веток — любой push, включая коммит в текущую ветку. `pull_request` добавляет тот же прогон на открытый PR. Фильтра путей нет, поэтому user и chat стартуют вместе, даже если коммит трогал один каталог.

`defaults.run.working-directory` относится к шагам `run`. `uses: actions/checkout` выполняется из корня репозитория, иначе некуда клонировать.

У джоб нет `needs`. На графе GitHub они стоят в один ряд. Это видно на вкладке Actions сразу после push.

Docker-джоба не ставит Python на runner: процесс живёт внутри образа. Снаружи только `curl` на опубликованный порт.

## ✅ Проверка

Локально yaml не исполняется. Проверка этого шага — что файлы лежат где их ищет GitHub, и что команды внутри уже зелёные с прошлых шагов:

```bash
test -f .github/workflows/user.yml && test -f .github/workflows/chat.yml
cd user_service && ruff check . && pytest
cd ../chat_service && ruff check . && pytest
```

После push на GitHub у одного коммита два workflow, в каждом три джобы. Они не ждут друг друга.

✅ Готово, когда оба файла на месте, а локальные `ruff` и `pytest` проходят.
