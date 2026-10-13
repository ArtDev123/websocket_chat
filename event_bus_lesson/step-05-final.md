# Шаг 5 — Сверка пакета и чеклист

**Предыдущий:** [step-04-consumer.md](step-04-consumer.md)

## Задача

Пройти сценарий целиком: байты в мок-S3, JSON в мок-SQS, строка консьюмера в консоли. Новой логики нет. Ниже финальные файлы — сверьте со своими.

`__init__.py` пустой. `__main__.py` с шага 1 не менялся.

---

## Код: `event_bus/config.py`

```python
import os

REGION = "us-east-1"
BUCKET = "lesson-uploads"
QUEUE_NAME = "file-uploaded"
FILENAME = "cat.png"
IMAGE_BYTES = b"\x89PNG\r\nlesson-image"


def setup_aws_env() -> None:
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = REGION
```

---

## Код: `event_bus/storage.py`

```python
import boto3

from event_bus.config import BUCKET, REGION


def s3_client():
    return boto3.client("s3", region_name=REGION)


def create_bucket(s3) -> None:
    s3.create_bucket(Bucket=BUCKET)


def upload_image(s3, filename: str, body: bytes) -> str:
    s3.put_object(
        Bucket=BUCKET,
        Key=filename,
        Body=body,
        ContentType="image/png",
    )
    return s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": BUCKET, "Key": filename},
        ExpiresIn=3600,
    )
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

---

## Код: `event_bus/main.py`

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

---

## ✅ Проверка

```bash
cd event_bus_lesson
source .venv/bin/activate
python -m event_bus
```

```text
URL: https://lesson-uploads.s3.amazonaws.com/cat.png?AWSAccessKeyId=...&Signature=...&Expires=...
Обрабатываю файл: cat.png
```

Подпись и `Expires` в ссылке меняются между запусками. Имя файла во второй строке — нет.

---

## Чеклист

### Окружение

- [ ] `pip install boto3 moto` в активированном `.venv`
- [ ] Запуск из `event_bus_lesson`: `python -m event_bus`
- [ ] `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` выставлены в `testing` до клиентов
- [ ] Регион клиентов — `us-east-1`

### Границы модулей

- [ ] `storage.py` не импортирует `publisher` и `consumer`
- [ ] `publisher.py` не импортирует `storage` и `consumer`
- [ ] `consumer.py` не импортирует `storage`, `publisher` и `config`
- [ ] `mock_aws()` есть только в `main.py`

### S3

- [ ] Корзина `lesson-uploads` создаётся внутри `mock_aws()`
- [ ] `put_object` пишет байты с ключом `cat.png`
- [ ] Напечатанный URL — результат `generate_presigned_url`

### Очередь

- [ ] Очередь `file-uploaded`, в вызовах участвует `QueueUrl`
- [ ] Тело сообщения — `json.dumps` словаря с полями `event`, `filename`, `url`
- [ ] В `MessageBody` нет байтов картинки

### Консьюмер

- [ ] `consume` вызывает `receive_message` и читает `event["filename"]`
- [ ] В консоли ровно строка `Обрабатываю файл: cat.png`
- [ ] После печати вызывается `delete_message` с `ReceiptHandle`
- [ ] `create_bucket`, `send_message` и `consume` вызываются из одного `with mock_aws()` в `main`

---

## Если скрипт врёт

| Что видите | Куда смотреть |
|------------|----------------|
| `ModuleNotFoundError: moto` | venv не активирован |
| `ModuleNotFoundError: event_bus` | команда запущена не из `event_bus_lesson` |
| Запрос уходит в сеть / таймаут | вызов оказался вне `with mock_aws()` |
| `IllegalLocationConstraintException` | регион не `us-east-1` |
| `InvalidBucketName` | имя корзины короче 3 символов или с заглавными буквами |
| `ParamValidationError` на `MessageBody` | в очередь передан `dict`, нужен `json.dumps` |
| `Очередь пуста` | сообщение уже забрали другим `receive_message` или консьюмер снаружи мока |
| `KeyError: 'filename'` | в JSON другое поле, чем то, что читает `consume` |
