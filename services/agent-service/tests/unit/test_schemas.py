"""Found via user report: a ParseError in the browser (`JSON.parse` rejecting a literal
`NaN`) after submitting the profile-data widget. Root cause: a course with a zero-vector
embedding makes pgvector's cosine distance (`<=>`) undefined, so `similarity_score`
becomes `float('nan')` — and Python's `json.dumps` happily emits the invalid `NaN`
literal (not valid per the JSON spec), which every browser's `JSON.parse` rejects."""
from __future__ import annotations

import math
from decimal import Decimal

from src.api.schemas import CandidateSummary
from src.domain.models import Course, RecommendationCandidate


def _course(course_id: str = "course-1") -> Course:
    return Course(
        course_id=course_id,
        name="Curso de prueba",
        description="desc",
        category="Data Science",
        curriculum=("tema 1",),
        price=Decimal("100"),
        duration_weeks=4,
        embedding=(0.0,) * 8,
    )


def test_from_candidate_sanitizes_nan_similarity_score_to_zero():
    candidate = RecommendationCandidate(course=_course(), similarity_score=float("nan"))

    summary = CandidateSummary.from_candidate(candidate)

    assert summary.similarity_score == 0.0
    assert not math.isnan(summary.similarity_score)


def test_from_candidate_keeps_a_real_similarity_score_unchanged():
    candidate = RecommendationCandidate(course=_course(), similarity_score=0.87)

    summary = CandidateSummary.from_candidate(candidate)

    assert summary.similarity_score == 0.87
