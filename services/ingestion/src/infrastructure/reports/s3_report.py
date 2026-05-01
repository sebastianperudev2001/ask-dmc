from __future__ import annotations

import dataclasses
import json

import boto3

from src.domain.entities import IngestionReport


class S3ReportRepository:
    def __init__(self, bucket: str, prefix: str) -> None:
        self._bucket = bucket
        self._prefix = prefix.rstrip("/")
        self._client = boto3.client("s3")

    def save(self, report: IngestionReport) -> None:
        key = f"{self._prefix}/report_{report.timestamp}.json"
        body = json.dumps(dataclasses.asdict(report), indent=2)
        self._client.put_object(
            Bucket=self._bucket,
            Key=key,
            Body=body.encode(),
            ContentType="application/json",
        )
