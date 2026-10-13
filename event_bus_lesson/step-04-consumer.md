# Шаг 4 — Консьюмер

**Предыдущий:** [step-03-sqs.md](step-03-sqs.md) · **Следующий:** [step-05-final.md](step-05-final.md)

## Задача

Модуль `consumer` читает сообщение из очереди и печатает:

```text
Обрабатываю файл: cat.png
```

Имя берётся из JSON, который отправил `publisher`. После обработки сообщение из очереди удаляется. `consumer` не импортирует `storage` и `publisher`.

---

## Теория: консьюмер опрашивает очередь

SQS в этом уроке ничего никому не пушит. Консьюмер сам вызывает `receive_message` и спрашивает: «есть что-нибудь?».

Полезные аргументы:

| Аргумент | Значение | Зачем |
|----------|----------|--------|
| `QueueUrl` | URL из `create_queue` | какую очередь читать |
| `MaxNumberOfMessages` | `1` | за раз забираем одно сообщение. API разрешает до 10 |
| `WaitTimeSeconds` | `1` | подождать до одной секунды, если очередь пуста (long polling). В моке сообщение уже лежит, ответ приходит сразу |

Ответ — словарь. Если сообщений нет, ключа `Messages` в нём нет, поэтому читаем через `.get("Messages", [])`.

Одно сообщение выглядит так:

```text
{
  "MessageId": "...",
  "ReceiptHandle": "...",
  "Body": "{\"event\": \"file_uploaded\", \"filename\": \"cat.png\", \"url\": \"https://...\"}"
}
```

`Body` — снова строка. `json.loads` возвращает словарь, и `event["filename"]` — это `cat.png`.

`ReceiptHandle` — квитанция именно этой выдачи. Её и передают в `delete_message`. `MessageId` для удаления не подходит.

Пока сообщение не удалили, другие `receive_message` его не видят (оно «в полёте» на время visibility timeout). Удаление говорит очереди: обработка прошла, повторять не нужно. Вызов стоит после `print`, чтобы сбой до печати не стёр событие.

Пустая очередь на уроке — повод напечатать `Очередь пуста` и выйти. Так видно, что консьюмер отработал, а сообщение потерялось раньше (например, его уже прочитали при отладке).

Клиент SQS консьюмер не создаёт. Его передаёт `main` — тот же объект, которым `publisher` отправил событие, уже внутри `mock_aws()`.

---

## Код: `event_bus/consumer.py`

```python
import json


def consume(sqs, queue_url: str) -> None:
    response = sqs.receive_message(
        QueueUrl=queue_url,
        MaxNumberOfMessages=1,
        WaitTimeSeconds=1,
    )
    messages = response.get("Messages", [])
    if not messages:
        print("Очередь пуста")
        return

    message = messages[0]
    event = json.loads(message["Body"])
    print(f"Обрабатываю файл: {event['filename']}")
    sqs.delete_message(
        QueueUrl=queue_url,
        ReceiptHandle=message["ReceiptHandle"],
    )
```

**Разбор:** в файле нет импортов `storage`, `publisher` и даже `config`. Хватает клиента и URL очереди. Имя файла достаётся из тела сообщения — того JSON, который собрал `publish_upload`. `delete_message` снимает сообщение, чтобы повторный запуск консьюмера в том же моке не обработал его второй раз.

---

## Код: заменить `event_bus/main.py`

Счётчик `ApproximateNumberOfMessages` больше не нужен: чтение само покажет, что сообщение было.

```python
from moto import mock_aws

from event_bus.config import FILENAME, IMAGE_BYTES, setup_aws_env
from event_bus.consumer import consume
from event_bus.publisher import create_queue, publish_upload, sqs_client
from event_bus.storage import create_bucket, s3_client, upload_image


def main() -> None:
    setup_aws_env()
    with mock_aws():
        s3 = s3_client()
        sqs = sqs_client()

        create_bucket(s3)
        url = upload_image(s3, FILENAME, IMAGE_BYTES)
        print("URL:", url)

        queue_url = create_queue(sqs)
        publish_upload(sqs, queue_url, FILENAME, url)
        consume(sqs, queue_url)


if __name__ == "__main__":
    main()
```

**Разбор:** `main` — единственное место, где встречаются все три модуля. Имя файла между `storage` и `consumer` едет внутри `MessageBody`. `consume` стоит в том же `with`: за его границей очереди уже нет.

---

## ✅ Проверка

```bash
python -m event_bus
```

```text
URL: https://lesson-uploads.s3.amazonaws.com/cat.png?AWSAccessKeyId=...&Signature=...&Expires=...
Обрабатываю файл: cat.png
```

`Очередь пуста` вместо второй строки — `receive_message` уже вызывали выше по `main` и не удалили сообщение, либо `consume` оказался снаружи `mock_aws()`. `KeyError: 'filename'` — в JSON другое имя поля, не то, что читает `event["filename"]`.

**Готово →** [step-05-final.md](step-05-final.md)
