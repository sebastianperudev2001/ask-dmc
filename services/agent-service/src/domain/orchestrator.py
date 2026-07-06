from __future__ import annotations

import math
from dataclasses import dataclass, replace
from decimal import Decimal

from src.domain.models import (
    Course,
    RecommendationBranch,
    RecommendationCandidate,
    RecommendationRequest,
)
from src.ports.course_repository import CourseRepository

TOP_K = 3  # BR-05
RELAXED_BUDGET_MULTIPLIER = Decimal("1.2")  # BR-03
RELAXED_DURATION_MULTIPLIER = 1.5  # BR-03


@dataclass(frozen=True)
class RecommendationStart:
    """Result of RecommendationOrchestrator.start() — either ready to hand to the agent,
    or awaiting the user's relax_filters_response (BR-03, rama 3c)."""

    needs_confirmation: bool
    candidates: list[RecommendationCandidate]
    branch: RecommendationBranch | None = None
    relaxed_budget: Decimal | None = None
    relaxed_duration_weeks: int | None = None

    @staticmethod
    def ready(
        candidates: list[RecommendationCandidate], branch: RecommendationBranch
    ) -> "RecommendationStart":
        return RecommendationStart(needs_confirmation=False, candidates=candidates, branch=branch)

    @staticmethod
    def awaiting_confirmation(
        candidates: list[RecommendationCandidate],
        relaxed_budget: Decimal,
        relaxed_duration_weeks: int,
    ) -> "RecommendationStart":
        return RecommendationStart(
            needs_confirmation=True,
            candidates=candidates,
            relaxed_budget=relaxed_budget,
            relaxed_duration_weeks=relaxed_duration_weeks,
        )


class RecommendationOrchestrator:
    """Implements business-logic-model.md Section 2 (steps 2-7): hard filter, BR-03
    relaxation-with-confirmation branch, BR-11 full-catalog fallback. Depends only on
    the CourseRepository port — no direct infrastructure dependency (testable with a
    fake repository, per PBT-01)."""

    def __init__(self, course_repository: CourseRepository) -> None:
        self._course_repository = course_repository

    @staticmethod
    def compute_relaxed_criteria(
        budget: Decimal, max_duration_weeks: int
    ) -> tuple[Decimal, int]:
        """Pure, deterministic (P3 — idempotence/determinism, no DB dependency)."""
        relaxed_budget = budget * RELAXED_BUDGET_MULTIPLIER
        relaxed_duration_weeks = math.ceil(max_duration_weeks * RELAXED_DURATION_MULTIPLIER)
        return relaxed_budget, relaxed_duration_weeks

    async def start(
        self, request: RecommendationRequest, query_embedding: tuple[float, ...]
    ) -> RecommendationStart:
        # Step 2: strict hard filter (BR-01/02) + ranking (BR-04), delegated to the repository.
        exact_candidates = await self._course_repository.find_ranked_candidates(
            query_embedding,
            max_price=request.budget,
            max_duration_weeks=request.max_duration_weeks,
            limit=TOP_K,
        )
        if exact_candidates:
            return RecommendationStart.ready(exact_candidates, RecommendationBranch.EXACT_MATCH)

        # Step 3a: compute relaxed criteria internally, without exposing yet.
        relaxed_budget, relaxed_duration_weeks = self.compute_relaxed_criteria(
            request.budget, request.max_duration_weeks
        )
        relaxed_candidates = await self._course_repository.find_ranked_candidates(
            query_embedding,
            max_price=relaxed_budget,
            max_duration_weeks=relaxed_duration_weeks,
            limit=TOP_K,
        )

        # Step 3b: relaxed also empty -> straight to full catalog (BR-11), no point asking.
        if not relaxed_candidates:
            full_catalog_candidates = await self._full_catalog(query_embedding)
            return RecommendationStart.ready(
                full_catalog_candidates, RecommendationBranch.FULL_CATALOG
            )

        # Step 3c: relaxed has candidates -> mark which filters they only pass under
        # relaxation, and pause for user confirmation.
        marked = [
            replace(
                candidate,
                filters_relaxed=self._relaxed_fields(candidate.course, request),
            )
            for candidate in relaxed_candidates
        ]
        return RecommendationStart.awaiting_confirmation(
            marked, relaxed_budget, relaxed_duration_weeks
        )

    async def resolve_after_confirmation(
        self,
        pending_relaxed_candidates: list[RecommendationCandidate],
        confirmed: bool,
        query_embedding: tuple[float, ...],
    ) -> RecommendationStart:
        """Step 3d: user's relax_filters_response."""
        if confirmed:
            return RecommendationStart.ready(
                pending_relaxed_candidates, RecommendationBranch.RELAXED_MATCH
            )
        full_catalog_candidates = await self._full_catalog(query_embedding)
        return RecommendationStart.ready(full_catalog_candidates, RecommendationBranch.FULL_CATALOG)

    async def _full_catalog(
        self, query_embedding: tuple[float, ...]
    ) -> list[RecommendationCandidate]:
        """Step 3e / BR-11: no hard filter, no LIMIT, ranked by similarity only."""
        candidates = await self._course_repository.find_ranked_candidates(
            query_embedding, max_price=None, max_duration_weeks=None, limit=None
        )
        return [replace(candidate, from_full_catalog=True) for candidate in candidates]

    @staticmethod
    def _relaxed_fields(course: Course, request: RecommendationRequest) -> tuple[str, ...]:
        fields: list[str] = []
        if course.price > request.budget:
            fields.append("budget")
        if course.duration_weeks > request.max_duration_weeks:
            fields.append("duration")
        return tuple(fields)
