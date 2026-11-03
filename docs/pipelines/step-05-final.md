# Шаг 5 — Прогон

**Предыдущий:** [step-04-github.md](step-04-github.md)

## Задача

Один раз пройти цепочку, которую runner разложит на джобы: тестовые базы, ruff, pytest. Оба сервиса, один за другим.

## Теория

На GitHub `lint`, `test` и `docker` одного сервиса стартуют вместе, и оба сервиса стартуют на один push. Локально удобнее идти по очереди: одна машина, одни порты брокера. Смысл проверок тот же.

Docker-шаг workflow здесь не повторяем. Он собирает образ и в конце делает `down -v`. На runner тома пустые. У вас в `user_pgdata` и `chat_pgdata` уже могут лежать пользователи с прошлого урока, и `-v` их удалит.

Что пайплайн не обещает: доставку `user.registered`, проекцию и кадр WebSocket. Публикация в тесте подменена, а `/health` из контейнера не шлёт сообщение в комнату. Это границы урока, они названы в [guide.md](guide.md).

## Код

Новых файлов нет.

## ✅ Проверка

Из корня репозитория:

```bash
docker compose -f user_service/docker-compose.test.yml up -d --wait
docker compose -f chat_service/docker-compose.test.yml up -d --wait

cd user_service
ruff check .
pytest

cd ../chat_service
ruff check .
pytest
```

Ожидание:

- ruff пишет `All checks passed!`;
- pytest обоих сервисов зелёный;
- user-тест регистрирует `alice` и читает её из `/users`;
- chat-тест создаёт комнату `general` с `created_by_id = 1`;
- отдельные тесты видят `current_database()` равным `user_test` и `chat_test`.

Остановить только тестовые базы, рабочие тома не трогая:

```bash
docker compose -f user_service/docker-compose.test.yml down
docker compose -f chat_service/docker-compose.test.yml down
```

✅ Готово, когда оба сервиса проходят ruff и pytest на своих `*_test`.
