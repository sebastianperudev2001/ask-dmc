import boto3


class S3StorageProvider:
    def __init__(self, bucket: str, prefix: str) -> None:
        self._bucket = bucket
        self._prefix = prefix.rstrip("/") + "/"
        self._client = boto3.client("s3")

    def list_brochures(self) -> list[str]:
        paginator = self._client.get_paginator("list_objects_v2")
        keys: list[str] = []
        for page in paginator.paginate(Bucket=self._bucket, Prefix=self._prefix):
            for obj in page.get("Contents", []):
                key = obj["Key"]
                if key.lower().endswith(".pdf"):
                    keys.append(key)
        return sorted(keys)

    def get_object(self, path: str) -> bytes:
        response = self._client.get_object(Bucket=self._bucket, Key=path)
        return response["Body"].read()
