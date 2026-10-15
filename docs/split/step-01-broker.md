# Шаг 1 — Брокер и общая сеть

**Предыдущий:** [guide.md](guide.md) · **Следующий:** [step-02-user-service.md](step-02-user-service.md)

## Задача

Поднять RabbitMQ в своём compose. Сервисы к нему ещё не подключаются: нужна сеть, в которую они войдут на следующих шагах.

## Теория

Из чего в брокере exchange, очередь и привязка — в [guide.md](guide.md), раздел «Компоненты RabbitMQ». Здесь только то, без чего контейнер не поднимется.

У user и chat будет по своему `docker-compose.yml`. Если положить брокер внутрь одного из них, второй его не увидит, а два брокера друг с другом не разговаривают. Брокер — третья, маленькая compose-конфигурация. Она создаёт сеть `lesson-net`. Оба сервиса потом подключатся к ней как к `external`.

Пользователь `guest` / `guest` в RabbitMQ по умолчанию принимает соединения только с localhost. Контейнер API для брокера — чужая машина, поэтому в конфиге снимаем это ограничение. Иначе логин в брокер из другого контейнера будет молча отваливаться.

Порты `5672` (AMQP) и `15672` (веб-UI) смотрят на хост, чтобы проверку можно было сделать из браузера.

## Код

Каталог `rabbit/` в корне репозитория.

`rabbit/rabbitmq.conf`:

```text
loopback_users = none
```

`rabbit/docker-compose.yml`:

```yaml
services:
  rabbitmq:
    image: rabbitmq:3-management
    ports:
      - "5672:5672"
      - "15672:15672"
    volumes:
      - ./rabbitmq.conf:/etc/rabbitmq/rabbitmq.conf:ro
    healthcheck:
      test: ["CMD", "rabbitmq-diagnostics", "ping"]
      interval: 5s
      timeout: 5s
      retries: 12
    networks:
      - lesson-net

networks:
  lesson-net:
    name: lesson-net
```

`name: lesson-net` фиксирует имя сети. Без этого Compose назвал бы её `rabbit_lesson-net`, и сервисы не попали бы в ту же сеть по имени `lesson-net`.

## Разбор кода

Образ `rabbitmq:3-management` — это брокер плюс UI. Конфиг монтируется в `/etc/rabbitmq/rabbitmq.conf`, образ читает его сам. Healthcheck `rabbitmq-diagnostics ping` нужен, чтобы не регистрировать пользователей, пока процесс ещё стартует.

Сервис внутри сети называется `rabbitmq`. URL с других контейнеров будет `amqp://guest:guest@rabbitmq:5672/`. С хоста — `localhost:5672`.

## ✅ Проверка

Из корня репозитория:

```bash
docker compose -f rabbit/docker-compose.yml up -d
docker compose -f rabbit/docker-compose.yml ps
```

В колонке статуса у `rabbitmq` должно быть `healthy`. UI: http://127.0.0.1:15672 , логин `guest`, пароль `guest`. Вкладка Exchanges пока пустая относительно наших имён: exchange `users` объявят сервисы на шагах 3 и 5.

**Готово →** [step-02-user-service.md](step-02-user-service.md)
