"""Seed the courses table from catalog_seed_data.json, generating each course's
embedding via Azure OpenAI (business-logic-model.md Section 1). Run once at catalog
load time or whenever seed data changes (BR-06: embeddings are pre-computed, not
generated per recommendation request).

Usage: python -m scripts.seed_catalog
"""
from __future__ import annotations

import asyncio
import json
from decimal import Decimal
from pathlib import Path

from azure.identity import DefaultAzureCredential

from src.adapters.azure_openai_embedding import AzureOpenAIEmbeddingService
from src.adapters.connection_pool import ConnectionPool
from src.adapters.retry_policy import RetryPolicy
from src.config import ENV, load_config
from src.domain.models import Course

SEED_DATA_PATH = Path(__file__).parent / "catalog_seed_data.json"

_UPSERT_QUERY = """
    INSERT INTO courses (course_id, name, description, category, curriculum,
                          price, duration_weeks, embedding)
    VALUES ($1, $2, $3, $4, $5, $6, $7, $8::vector)
    ON CONFLICT (course_id) DO UPDATE SET
        name = EXCLUDED.name,
        description = EXCLUDED.description,
        category = EXCLUDED.category,
        curriculum = EXCLUDED.curriculum,
        price = EXCLUDED.price,
        duration_weeks = EXCLUDED.duration_weeks,
        embedding = EXCLUDED.embedding
"""


def _load_seed_courses() -> list[Course]:
    raw = json.loads(SEED_DATA_PATH.read_text(encoding="utf-8"))
    return [
        Course(
            course_id=entry["course_id"],
            name=entry["name"],
            description=entry["description"],
            category=entry["category"],
            curriculum=tuple(entry["curriculum"]),
            price=Decimal(str(entry["price"])),
            duration_weeks=entry["duration_weeks"],
        )
        for entry in raw
    ]


async def main() -> None:
    config = load_config()
    credential = DefaultAzureCredential()
    retry_policy = RetryPolicy(
        max_attempts=config.retry_max_attempts, base_delay_seconds=config.retry_base_delay_seconds
    )
    embedding_service = AzureOpenAIEmbeddingService(
        endpoint=config.azure_openai_endpoint,
        deployment=config.azure_openai_embedding_deployment,
        credential=credential,
        retry_policy=retry_policy,
    )
    connection_pool = ConnectionPool(
        config.database_url, require_ssl=(config.env == ENV.PRODUCTION)
    )
    await connection_pool.start()

    try:
        courses = _load_seed_courses()
        for course in courses:
            embedding = await embedding_service.embed(course.embedding_text())
            embedding_literal = "[" + ",".join(repr(v) for v in embedding) + "]"
            await connection_pool.pool.execute(
                _UPSERT_QUERY,
                course.course_id,
                course.name,
                course.description,
                course.category,
                list(course.curriculum),
                course.price,
                course.duration_weeks,
                embedding_literal,
            )
            print(f"seeded: {course.course_id}")
    finally:
        await connection_pool.close()


if __name__ == "__main__":
    asyncio.run(main())
