from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CourseMetadata:
    id: str
    title: str
    program_type: str
    aliases: list[str]
    keywords: list[str]
    topics: list[str]


@dataclass
class ApiConfig:
    metadata_path: str
    aws_region: str
    bedrock_model_id: str
