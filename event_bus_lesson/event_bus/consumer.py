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
