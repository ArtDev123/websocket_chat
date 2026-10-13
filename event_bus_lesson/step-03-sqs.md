# Шаг 3 — Очередь SQS и событие о загрузке

**Предыдущий:** [step-02-s3.md](step-02-s3.md) · **Следующий:** [step-04-consumer.md](step-04-consumer.md)

## Задача

Модуль `publisher` создаёт очередь, собирает JSON «файл загружен» (имя + URL из `storage`) и отправляет его. Консьюмер — на следующем шаге. Сейчас `main` только проверяет, что в очереди лежит одно сообщение.

`publisher` не импортирует `storage`. URL и имя файла приходят аргументами.

---

## Теория: очередь как шина

Очередь SQS хранит **сообщения**, пока их кто-нибудь не заберёт. У очереди есть имя (`file-uploaded`) и **URL**. В `send_message` и `receive_message` передают URL, не имя: после `create_queue` сервис возвращает готовый адрес в поле `QueueUrl`.

Тело сообщения — **строка**. Словарь Python туда не кладут: API ответит `ParamValidationError`. Словарь сначала превращаем в текст через `json.dumps`. На той стороне `json.loads` собирает словарь обратно.

Событие урока:

```json
{
  "event": "file_uploaded",
  "filename": "cat.png",
  "url": "https://lesson-uploads.s3.amazonaws.com/cat.png?..."
}
```

| Поле | Смысл |
|------|--------|
| `event` | что случилось. Позже в ту же очередь можно положить другой тип и отличить его по этому полю |
| `filename` | ключ объекта. Его напечатает консьюмер |
| `url` | временная ссылка из `upload_image` |

`publish_upload` не знает, кто будет читать очередь. Она знает URL очереди и текст события.

Картинку в `MessageBody` не кладём. Байты уже в S3. В шине едет новость.

---

## Теория: как понять, что сообщение на месте

`receive_message` сообщение **забирает** с точки зрения других читателей: на время visibility timeout (по умолчанию 30 секунд) его больше не отдают. Если прочитать его сейчас «для проверки», на шаге 4 консьюмер увидит пустую очередь.

Счётчик очереди сообщение не забирает:

```python
sqs.get_queue_attributes(
    QueueUrl=queue_url,
    AttributeNames=["ApproximateNumberOfMessages"],
)
```

В моке после одной отправки атрибут `ApproximateNumberOfMessages` равен строке `"1"` (SQS отдаёт атрибуты строками). Этот вызов живёт в `main` и только на этом шаге: в `publisher` ему не место.

---

## Код: дописать `event_bus/config.py`

Рядом с `BUCKET`:

```python
QUEUE_NAME = "file-uploaded"
```

---

## Код: `event_bus/publisher.py`

```python
import json

import boto3

from event_bus.config import QUEUE_NAME, REGION


def sqs_client():
    return boto3.client("sqs", region_name=REGION)


def create_queue(sqs) -> str:
    response = sqs.create_queue(QueueName=QUEUE_NAME)
    return response["QueueUrl"]


def publish_upload(sqs, queue_url: str, filename: str, url: str) -> None:
    event = {
        "event": "file_uploaded",
        "filename": filename,
        "url": url,
    }
    sqs.send_message(
        QueueUrl=queue_url,
        MessageBody=json.dumps(event),
    )
```

**Разбор:** импорт только `config`. `create_queue` создаёт очередь и возвращает её URL — его сохраняет `main` и передаёт дальше. `publish_upload` собирает словарь из аргументов, сериализует его в JSON и кладёт строку в очередь. Откуда взялся `url`, модуль не знает.

---

## Код: заменить `event_bus/main.py`

Печать байтов из корзины уберите: файл уже проверен. Оставьте URL и счётчик очереди.

```python
from moto import mock_aws

from event_bus.config import FILENAME, IMAGE_BYTES, setup_aws_env
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

        attrs = sqs.get_queue_attributes(
            QueueUrl=queue_url,
            AttributeNames=["ApproximateNumberOfMessages"],
        )
        print("В очереди:", attrs["Attributes"]["ApproximateNumberOfMessages"])


if __name__ == "__main__":
    main()
```

**Разбор:** S3 и SQS — два клиента внутри одного мока, поэтому корзина и очередь видят одну и ту же память, хотя живут в разных файлах. `main` перекладывает `url` из `storage` в `publisher`. Счётчик печатаем до того, как кто-либо вызовет `receive_message`.

---

## ✅ Проверка

```bash
python -m event_bus
```

```text
URL: https://lesson-uploads.s3.amazonaws.com/cat.png?AWSAccessKeyId=...&Signature=...&Expires=...
В очереди: 1
```

`ParamValidationError` про `MessageBody` значит, что в очередь ушёл словарь, а не `json.dumps(...)`.

**Готово →** [step-04-consumer.md](step-04-consumer.md)
