"""Property-based tests (Hypothesis) for the P1-P8 properties identified in
business-logic-model.md Section 6 (PBT-01). Uses InMemoryCourseRepository (fakes.py) —
the same properties are re-verified against real Postgres+pgvector in
tests/unit/test_postgres_repository.py (P6 in particular can only be meaningfully
checked there, against the real ORDER BY embedding <=> query)."""
from __future__ import annotations

from decimal import Decimal

from hypothesis import given, settings
from hypothesis import strategies as st

from src.domain.orchestrator import RecommendationOrchestrator
from tests.unit.fakes import InMemoryCourseRepository, cosine_similarity
from tests.unit.generators import courses, small_embeddings


# P1 — Invariant: every candidate returned under a hard filter respects it.
@given(
    course_list=st.lists(courses(), min_size=0, max_size=15),
    query_embedding=small_embeddings(),
    max_price=st.decimals(min_value=Decimal("100"), max_value=Decimal("10000"), places=2),
    max_duration_weeks=st.integers(min_value=1, max_value=52),
)
@settings(max_examples=100)
async def test_p1_filter_invariant(course_list, query_embedding, max_price, max_duration_weeks):
    repo = InMemoryCourseRepository(course_list)
    candidates = await repo.find_ranked_candidates(
        query_embedding, max_price=max_price, max_duration_weeks=max_duration_weeks, limit=None
    )
    for candidate in candidates:
        assert candidate.course.price <= max_price
        assert candidate.course.duration_weeks <= max_duration_weeks


# P2 — Invariant (monotonicity): relaxing the criteria never returns fewer matches.
@given(
    course_list=st.lists(courses(), min_size=0, max_size=15),
    query_embedding=small_embeddings(),
    budget=st.decimals(min_value=Decimal("100"), max_value=Decimal("10000"), places=2),
    max_duration_weeks=st.integers(min_value=1, max_value=52),
)
@settings(max_examples=100)
async def test_p2_relaxation_is_monotonic(course_list, query_embedding, budget, max_duration_weeks):
    repo = InMemoryCourseRepository(course_list)
    relaxed_budget, relaxed_duration = RecommendationOrchestrator.compute_relaxed_criteria(
        budget, max_duration_weeks
    )
    strict = await repo.find_ranked_candidates(
        query_embedding, max_price=budget, max_duration_weeks=max_duration_weeks, limit=None
    )
    relaxed = await repo.find_ranked_candidates(
        query_embedding, max_price=relaxed_budget, max_duration_weeks=relaxed_duration, limit=None
    )
    strict_ids = {c.course.course_id for c in strict}
    relaxed_ids = {c.course.course_id for c in relaxed}
    assert strict_ids.issubset(relaxed_ids)


# P3 — Idempotence/determinism: same inputs always produce the same relaxed criteria.
@given(
    budget=st.decimals(min_value=Decimal("100"), max_value=Decimal("10000"), places=2),
    max_duration_weeks=st.integers(min_value=1, max_value=52),
)
def test_p3_relaxed_criteria_is_deterministic(budget, max_duration_weeks):
    first = RecommendationOrchestrator.compute_relaxed_criteria(budget, max_duration_weeks)
    second = RecommendationOrchestrator.compute_relaxed_criteria(budget, max_duration_weeks)
    assert first == second


# P4 — Invariant (range): `limit` always bounds the result size; None means unbounded.
@given(
    course_list=st.lists(courses(), min_size=0, max_size=15),
    query_embedding=small_embeddings(),
)
@settings(max_examples=50)
async def test_p4_limit_bounds_result_size(course_list, query_embedding):
    repo = InMemoryCourseRepository(course_list)
    top3 = await repo.find_ranked_candidates(
        query_embedding, max_price=None, max_duration_weeks=None, limit=3
    )
    assert len(top3) <= 3
    unbounded = await repo.find_ranked_candidates(
        query_embedding, max_price=None, max_duration_weeks=None, limit=None
    )
    assert len(unbounded) == len(course_list)


# P5 — Invariant (ordering): results are non-increasing by similarity_score.
@given(
    course_list=st.lists(courses(), min_size=0, max_size=15),
    query_embedding=small_embeddings(),
)
@settings(max_examples=100)
async def test_p5_results_ordered_by_similarity_descending(course_list, query_embedding):
    repo = InMemoryCourseRepository(course_list)
    candidates = await repo.find_ranked_candidates(
        query_embedding, max_price=None, max_duration_weeks=None, limit=None
    )
    scores = [c.similarity_score for c in candidates]
    assert scores == sorted(scores, reverse=True)


# P6 — Oracle: NOT applicable at this layer (fake repository IS the NumPy reference by
# construction). See test_postgres_repository.py for the real pgvector-vs-NumPy check.


# P7 — Invariant: embedding_text always contains name, category, and every curriculum topic.
@given(course=courses())
def test_p7_embedding_text_contains_all_source_fields(course):
    text = course.embedding_text()
    assert course.name in text
    assert course.category in text
    for topic in course.curriculum:
        assert topic in text


# P8 — Invariant (range): cosine similarity always falls within [-1, 1].
@given(a=small_embeddings(), b=small_embeddings())
def test_p8_similarity_score_within_range(a, b):
    score = cosine_similarity(a, b)
    assert -1.0 - 1e-9 <= score <= 1.0 + 1e-9
