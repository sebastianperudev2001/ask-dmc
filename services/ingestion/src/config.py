from __future__ import annotations

import os

from src.domain.entities import ENV, IngestionConfig


def load_config() -> IngestionConfig:
    raw_env = os.environ.get("INGESTION_ENV", "local").strip().lower()
    try:
        env = ENV(raw_env)
    except ValueError:
        raise ValueError(
            f"INGESTION_ENV must be 'local' or 'production', got: {raw_env!r}"
        )

    vector_db_url = os.environ.get("VECTOR_DB_URL", "")
    if not vector_db_url:
        raise ValueError("VECTOR_DB_URL environment variable is required")

    response = IngestionConfig(
        env=env,
        vector_db_url=vector_db_url,
        local_knowledge_dir=os.environ.get("LOCAL_KNOWLEDGE_DIR", "knowledge_source"),
        s3_bucket=os.environ.get("S3_BUCKET"),
        s3_prefix=os.environ.get("S3_BROCHURES_PREFIX", "brochures/"),
        local_reports_dir=os.environ.get("LOCAL_REPORTS_DIR", "reports"),
        s3_reports_prefix=os.environ.get("S3_REPORTS_PREFIX", "reports"),
        ollama_base_url=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434"),
        ollama_model=os.environ.get("OLLAMA_EMBEDDINGS_MODEL", "nomic-embed-text"),
        bedrock_embeddings_model=os.environ.get(
            "BEDROCK_EMBEDDINGS_MODEL", "amazon.titan-embed-text-v2:0"
        ),
        keywords_model=os.environ.get("KEYWORDS_MODEL", "gemma3:4b"),
        ingestion_workers=int(os.environ.get("INGESTION_WORKERS", "4")),
    )
    return response
