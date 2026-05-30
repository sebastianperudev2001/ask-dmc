from __future__ import annotations

import os
from pathlib import Path

from src.domain.entities import ApiConfig


def load_config() -> ApiConfig:
    default_metadata_path = Path(__file__).resolve().parent / "domain" / "metadata.json"
    return ApiConfig(
        metadata_path=default_metadata_path,
        aws_region=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"),
        bedrock_model_id=os.environ.get("BEDROCK_MODEL_ID", "us.anthropic.claude-sonnet-4-5-20251001"),
    )
