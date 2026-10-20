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
