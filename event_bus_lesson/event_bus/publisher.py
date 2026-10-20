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