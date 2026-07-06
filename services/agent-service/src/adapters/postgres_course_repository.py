"""PostgresCourseRepository — PATTERN-06 (ranking vía consulta pgvector por request,
sin cache), PATTERN-07 (índice HNSW), PATTERN-08 (índices B-tree en price/duration_weeks).
All queries are parameterized (SECURITY-05) — never string-concatenated."""
from __future__ import annotations

from decimal import Decimal

from src.adapters.connection_pool import ConnectionPool
from src.domain.models import Course, RecommendationCandidate

_FIND_RANKED_CANDIDATES_QUERY = """
    SELECT course_id, name, description, category, curriculum, price, duration_weeks,
           1 - (embedding <=> $1::vector) AS similarity_score
    FROM courses
    WHERE ($2::numeric IS NULL OR price <= $2)
      AND ($3::int IS NULL OR duration_weeks <= $3)
    ORDER BY embedding <=> $1::vector ASC
    LIMIT $4
"""

_CATALOG_COUNT_QUERY = "SELECT count(*) FROM courses"


def _embedding_to_pgvector_literal(embedding: tuple[float, ...]) -> str:
    return "[" + ",".join(repr(value) for value in embedding) + "]"


class PostgresCourseRepository:
    def __init__(self, connection_pool: ConnectionPool) -> None:
        self._connection_pool = connection_pool

    async def find_ranked_candidates(
        self,
        query_embedding: tuple[float, ...],
        *,
        max_price: Decimal | None,
        max_duration_weeks: int | None,
        limit: int | None,
    ) -> list[RecommendationCandidate]:
        rows = await self._connection_pool.pool.fetch(
            _FIND_RANKED_CANDIDATES_QUERY,
            _embedding_to_pgvector_literal(query_embedding),
            max_price,
            max_duration_weeks,
            limit,
        )
        return [self._row_to_candidate(row) for row in rows]

    async def catalog_is_empty(self) -> bool:
        count = await self._connection_pool.pool.fetchval(_CATALOG_COUNT_QUERY)
        return count == 0

    @staticmethod
    def _row_to_candidate(row) -> RecommendationCandidate:
        course = Course(
            course_id=row["course_id"],
            name=row["name"],
            description=row["description"],
            category=row["category"],
            curriculum=tuple(row["curriculum"]),
            price=row["price"],
            duration_weeks=row["duration_weeks"],
            embedding=None,  # not needed downstream — avoids shipping 1536 floats per row
        )
        return RecommendationCandidate(course=course, similarity_score=row["similarity_score"])
