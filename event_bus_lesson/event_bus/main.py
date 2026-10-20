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