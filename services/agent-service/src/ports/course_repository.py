from __future__ import annotations

from decimal import Decimal
from typing import Protocol

from src.domain.models import Course, RecommendationCandidate


class CourseRepository(Protocol):
    """Port for the courses catalog. Filtering (BR-01/02) and ranking (BR-04/BR-11) happen
    together in a single query — see business-logic-model.md step 6."""

    async def find_ranked_candidates(
        self,
        query_embedding: tuple[float, ...],
        *,
        max_price: Decimal | None,
        max_duration_weeks: int | None,
        limit: int | None,
    ) -> list[RecommendationCandidate]:
        """Return courses ranked by similarity to query_embedding.

        max_price / max_duration_weeks = None means no hard filter on that dimension
        (used for the BR-11 full-catalog branch). limit = None means no LIMIT (BR-11);
        limit = 3 implements the top-K bound of BR-05.

        similarity_score and filters_relaxed/from_full_catalog on the returned
        candidates are NOT set by this port — the caller (orchestrator) fills those in
        based on which branch of BR-03/BR-11 it is executing.
        """
        ...

    async def catalog_is_empty(self) -> bool:
        """True when the courses table has zero rows (BR-11 empty-catalog edge case)."""
        ...

    # ── Incremento 3 — BackOffice ──

    async def find_by_id(self, course_id: str) -> Course | None:
        """Usado por GetCourseDetailsTool (BR-26) para resolver name/description/
        curriculum al redactar un draft de outreach."""
        ...
