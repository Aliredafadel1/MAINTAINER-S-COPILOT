import io
import os

from minio import Minio

from app.infra import vault

_client: Minio | None = None

BUCKETS = [
    "raw-data",
    "datasets",
    "models",
    "rag-corpus",
    "rag-snapshots",
    "ci-reports",
]


def init() -> None:
    global _client
    endpoint = os.environ["MINIO_ENDPOINT"]
    access_key = vault.get("MINIO_ACCESS_KEY")
    secret_key = vault.get("MINIO_SECRET_KEY")
    _client = Minio(
        endpoint, access_key=access_key, secret_key=secret_key, secure=False
    )
    for bucket in BUCKETS:
        if not _client.bucket_exists(bucket):
            _client.make_bucket(bucket)


def client() -> Minio:
    assert _client is not None, "call init() first"
    return _client


def put_bytes(
    bucket: str, key: str, data: bytes, content_type: str = "application/octet-stream"
) -> None:
    client().put_object(
        bucket, key, io.BytesIO(data), length=len(data), content_type=content_type
    )


def get_bytes(bucket: str, key: str) -> bytes:
    response = client().get_object(bucket, key)
    try:
        return response.read()
    finally:
        response.close()
        response.release_conn()
