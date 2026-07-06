"""In-memory CourseRepository fake used to test RecommendationOrchestrator's control
flow (BR-03/BR-11 branching) without a real Postgres instance. Ranking here uses NumPy
cosine similarity directly — the real pgvector-vs-NumPy equivalence (P6) is verified
separately against a real database in tests/unit/test_postgres_repository.py."""
from __future__ import annotations

from decimal import Decimal

import numpy as np

from src.domain.models import Course, RecommendationCandidate


def cosine_similarity(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    va, vb = np.array(a), np.array(b)
    denom = np.linalg.norm(va) * np.linalg.norm(vb)
    if denom == 0:
        return 0.0
    return float(np.dot(va, vb) / denom)


class InMemoryCourseRepository:
    def __init__(self, courses: list[Course]) -> None:
        self._courses = courses

    async def find_ranked_candidates(
        self,
        query_embedding: tuple[float, ...],
        *,
        max_price: Decimal | None,
        max_duration_weeks: int | None,
        limit: int | None,
    ) -> list[RecommendationCandidate]:
        filtered = [
            c
            for c in self._courses
            if (max_price is None or c.price <= max_price)
            and (max_duration_weeks is None or c.duration_weeks <= max_duration_weeks)
        ]
        scored = [
            RecommendationCandidate(course=c, similarity_score=cosine_similarity(c.embedding, query_embedding))
            for c in filtered
        ]
        scored.sort(key=lambda candidate: candidate.similarity_score, reverse=True)
        return scored[:limit] if limit is not None else scored

    async def catalog_is_empty(self) -> bool:
        return len(self._courses) == 0
