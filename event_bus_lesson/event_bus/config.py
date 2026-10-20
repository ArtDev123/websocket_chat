import os

REGION = "us-east-1"
BUCKET = "lesson-uploads"
FILENAME = "cat.png"
IMAGE_BYTES = b"\x89PNG\r\nlesson-image"
QUEUE_NAME = "file-uploaded"

def setup_aws_env() -> None:
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = REGION