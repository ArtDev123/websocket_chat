# Шаг 1 — Окружение и пустой мок

**Предыдущий:** [guide.md](guide.md) · **Следующий:** [step-02-s3.md](step-02-s3.md)

## Задача

Поставить `boto3` и `moto`, завести пакет `event_bus`. `config.py` готовит учебные ключи, `main.py` включает мок и печатает, что шина в памяти жива. Корзины и очереди на этом шаге ещё нет.

---

## Теория: клиент и мок

`boto3.client("s3")` — объект с методами HTTP API Amazon S3. `boto3.client("sqs")` — то же для очередей. Код урока вызывает эти методы. Куда уходит вызов, решает окружение.

`mock_aws()` из moto на время блока `with` отвечает на вызовы сам. Данные лежат в процессе Python: отдельный сервис запускать не нужно.

Клиентов создаём **внутри** блока. Туда же позже попадут загрузка и чтение очереди. Закрыли блок — память мока очистилась. Сам `with` стоит в `main`: остальные модули про moto не знают.

Перед клиентами процесс записывает три переменные. Это делает `config.setup_aws_env`, его зовёт только `main`.

| Переменная | Значение на уроке | Зачем |
|------------|-------------------|--------|
| `AWS_ACCESS_KEY_ID` | `testing` | boto3 видит «ключ» и не ищет его в `~/.aws` |
| `AWS_SECRET_ACCESS_KEY` | `testing` | пара к ключу, moto её не сверяет с AWS |
| `AWS_DEFAULT_REGION` | `us-east-1` | регион по умолчанию для клиентов |

Это не секрет боевого аккаунта. Настоящий AWS этими строками не открывается, пока вызов перехватывает moto.

---

## 1. Виртуальное окружение

Из корня репозитория:

```bash
cd event_bus_lesson
python3 -m venv .venv
source .venv/bin/activate   # Windows: .\.venv\Scripts\Activate.ps1
pip install boto3 moto
```

Пакеты лежат в `requirements.txt`, команда выше ставит то же самое.

---

## Код: пакет

Каталог `event_bus_lesson/event_bus/` — пакет. Пустой `event_bus/__init__.py` нужен, чтобы Python увидел каталог как пакет.

`event_bus/__main__.py` — вход `python -m event_bus`:

```python
from event_bus.main import main

if __name__ == "__main__":
    main()
```

**Разбор:** `-m event_bus` выполняет этот файл. Он только вызывает `main` и сам ничего не знает про S3 и SQS.

---

## Код: `event_bus/config.py`

```python
import os

REGION = "us-east-1"


def setup_aws_env() -> None:
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = REGION
```

**Разбор:** здесь только данные и окружение. boto3 этот файл не импортирует. Имена корзины, файла и очереди добавятся на следующих шагах в тот же модуль, чтобы `storage` и `publisher` не заводили свои копии строк.

---

## Код: `event_bus/main.py`

```python
from moto import mock_aws

from event_bus.config import setup_aws_env


def main() -> None:
    setup_aws_env()
    with mock_aws():
        print("Мок AWS включён, шина в памяти процесса")


if __name__ == "__main__":
    main()
```

**Разбор:** `setup_aws_env` меняет окружение текущего процесса до любых клиентов. `with mock_aws()` включает перехват на время тела блока и выключает его на выходе. `if __name__` позволяет запустить и `python -m event_bus.main`.

---

## ✅ Проверка

Из каталога `event_bus_lesson`:

```bash
python -m event_bus
```

Ожидается одна строка:

```text
Мок AWS включён, шина в памяти процесса
```

Если `ModuleNotFoundError: moto` — окружение не активировано или пакеты ставились в другой интерпретатор. Повторите `source .venv/bin/activate` и `pip install boto3 moto`.

`ModuleNotFoundError: event_bus` — команда запущена не из `event_bus_lesson`.

**Готово →** [step-02-s3.md](step-02-s3.md)
