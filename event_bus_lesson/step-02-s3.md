# Шаг 2 — Корзина S3, картинка, URL

**Предыдущий:** [step-01-setup.md](step-01-setup.md) · **Следующий:** [step-03-sqs.md](step-03-sqs.md)

## Задача

Модуль `storage` внутри мока создаёт корзину, кладёт байты картинки и возвращает URL. `main` печатает ссылку. Очереди пока нет: `storage` про SQS не знает.

---

## Теория: корзина, ключ, объект

S3 хранит **объекты** (байты + служебные заголовки). Адрес объекта — два слова:

- **bucket** — корзина, контейнер с именем, уникальным среди мока (в бою — глобально);
- **key** — имя объекта внутри корзины. Папок на самом деле нет: ключ `photos/cat.png` — просто строка.

Имя корзины на уроке: `lesson-uploads`. Имена короче 3 символов и с заглавными буквами API отклоняет.

Регион клиента — `us-east-1`. `create_bucket` тогда вызывается только с именем. Для другого региона к вызову добавляют `CreateBucketConfiguration` с `LocationConstraint`, иначе S3 ответит `IllegalLocationConstraintException`. На уроке регион не меняем.

`put_object` записывает байты по ключу. `ContentType` говорит, что это `image/png`. Сам S3 содержимое не открывает: ему всё равно, настоящий это PNG или учебная строка байтов. В `config` лежит короткая заглушка, чтобы не тащить файл с диска. Ключ при этом честный: `cat.png`.

---

## Теория: откуда берётся URL

Объект в новой корзине закрытый. Постоянной публичной ссылки у него нет.

`generate_presigned_url` собирает **временную ссылку**: обычный адрес объекта плюс подпись и время жизни (`ExpiresIn`, в секундах). Кто успел до истечения — может скачать объект этим URL.

В моке ссылка ведёт на адрес вида `https://lesson-uploads.s3.amazonaws.com/...`. Браузер её не откроет: moto не поднимает сайт, он отвечает только на вызовы boto3 внутри процесса. Проверка урока — `get_object` в `main`: прочитали тот же ключ и увидели те же байты. Эту ссылку на следующем шаге положим в JSON события.

`storage` возвращает URL и на этом заканчивается. Кто вызовет очередь — решит `main`.

---

## Код: дописать `event_bus/config.py`

Рядом с `REGION`:

```python
BUCKET = "lesson-uploads"
FILENAME = "cat.png"
IMAGE_BYTES = b"\x89PNG\r\nlesson-image"
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

**Разбор:** модуль импортирует только `config`. `s3_client` собирает клиент с одним регионом. `create_bucket` создаёт пустую корзину. `upload_image` пишет байты под ключом `filename` и возвращает ссылку на скачивание, живую час (`3600` секунд). Ключ и есть имя файла, которое позже уедет в очередь. Очереди в этом файле нет.

---

## Код: заменить `event_bus/main.py`

```python
from moto import mock_aws

from event_bus.config import BUCKET, FILENAME, IMAGE_BYTES, setup_aws_env
from event_bus.storage import create_bucket, s3_client, upload_image


def main() -> None:
    setup_aws_env()
    with mock_aws():
        s3 = s3_client()
        create_bucket(s3)
        url = upload_image(s3, FILENAME, IMAGE_BYTES)
        print("URL:", url)

        saved = s3.get_object(Bucket=BUCKET, Key=FILENAME)
        print("В корзине:", saved["Body"].read())


if __name__ == "__main__":
    main()
```

**Разбор:** клиент рождается внутри мока, хотя функция `s3_client` описана в другом файле. Важен момент вызова, не место `def`. `get_object` возвращает словарь, у которого `Body` — поток. `.read()` забирает байты целиком. Строка `В корзине:` — проверка этого шага, она остаётся в `main` и в финале исчезнет: консьюмер работает с сообщением, а не печатает байты.

---

## ✅ Проверка

```bash
python -m event_bus
```

Две строки. Подпись в URL каждый запуск новая, начало стабильное:

```text
URL: https://lesson-uploads.s3.amazonaws.com/cat.png?AWSAccessKeyId=...&Signature=...&Expires=...
В корзине: b'\x89PNG\r\nlesson-image'
```

Если `IllegalLocationConstraintException` — клиент создан не в `us-east-1`. Если `InvalidBucketName` — имя корзины короче 3 символов или с заглавной буквы.

**Готово →** [step-03-sqs.md](step-03-sqs.md)
