"""Property tests against a REAL Postgres+pgvector instance (migrations/001_create_courses.sql
must already be applied — see README.md). Requires TEST_DATABASE_URL env var; skipped
otherwise. This is the only place P6 (oracle: pgvector vs NumPy cosine similarity) can be
meaningfully verified — see business-logic-model.md Section 6."""
from __future__ import annotations

from decimal import Decimal

import numpy as np
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from src.adapters.postgres_course_repository import PostgresCourseRepository
from src.domain.models import Course
from tests.conftest import requires_postgres
from tests.unit.generators import courses, embeddings

pytestmark = [requires_postgres, pytest.mark.asyncio]


def real_courses(**kwargs):
    """The real `courses` table column is vector(1536) — unlike InMemoryCourseRepository
    (which accepts any equal-length vectors), Postgres/pgvector rejects any other
    dimension. Must use the full-size `embeddings()` strategy, not `small_embeddings()`."""
    return courses(embedding_strategy=embeddings(), **kwargs)


async def _seed_courses(connection_pool, course_list) -> None:
    pool = connection_pool.pool
    await pool.execute("TRUNCATE TABLE courses")
    for course in course_list:
        embedding_literal = "[" + ",".join(repr(v) for v in course.embedding) + "]"
        await pool.execute(
            """
            INSERT INTO courses (course_id, name, description, category, curriculum,
                                  price, duration_weeks, embedding)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8::vector)
            """,
            course.course_id,
            course.name,
            course.description,
            course.category,
            list(course.curriculum),
            course.price,
            course.duration_weeks,
            embedding_literal,
        )


def _numpy_cosine_similarity(a, b) -> float:
    va, vb = np.array(a), np.array(b)
    denom = np.linalg.norm(va) * np.linalg.norm(vb)
    return float(np.dot(va, vb) / denom) if denom else 0.0


# Real DB I/O per example is inherently slower than the in-memory fake — a small
# collection (<=4 courses) and few examples is enough to exercise the oracle without
# fighting Hypothesis's large-example health check on 1536-float vectors.
@given(
    course_list=st.lists(real_courses(), min_size=1, max_size=4, unique_by=lambda c: c.course_id),
    query_embedding=embeddings(),
)
@settings(
    max_examples=8,
    deadline=None,
    suppress_health_check=[
        HealthCheck.function_scoped_fixture,
        HealthCheck.large_base_example,
        HealthCheck.data_too_large,
    ],
)
async def test_p6_pgvector_ranking_matches_numpy_oracle(connection_pool, course_list, query_embedding):
    repo = PostgresCourseRepository(connection_pool)
    await _seed_courses(connection_pool, course_list)

    candidates = await repo.find_ranked_candidates(
        query_embedding, max_price=None, max_duration_weeks=None, limit=None
    )

    expected_order = sorted(
        course_list,
        key=lambda c: _numpy_cosine_similarity(c.embedding, query_embedding),
        reverse=True,
    )
    assert [c.course.course_id for c in candidates] == [c.course_id for c in expected_order]
    for candidate, expected_course in zip(candidates, expected_order):
        expected_score = _numpy_cosine_similarity(expected_course.embedding, query_embedding)
        assert candidate.similarity_score == pytest.approx(expected_score, abs=1e-4)


# Not a property test (no @given) — a single concrete, hand-built Course is the right
# tool here, not Hypothesis's .example() (which has its own restrictive generation
# settings not meant for 1536-dim vectors, and produced "Unsatisfiable" errors here).
_FIXED_COURSE = Course(
    course_id="test-p1-p2-course",
    name="Curso de Prueba",
    description="Curso usado solo para verificar el filtro duro contra Postgres real.",
    category="Data Science",
    curriculum=("Tema A", "Tema B"),
    price=Decimal("3000.00"),
    duration_weeks=10,
    embedding=tuple([1.0] + [0.0] * 1535),
)


async def test_p1_p2_filter_and_relaxation_against_real_db(connection_pool):
    repo = PostgresCourseRepository(connection_pool)
    await _seed_courses(connection_pool, [_FIXED_COURSE])

    query_embedding = _FIXED_COURSE.embedding
    strict = await repo.find_ranked_candidates(
        query_embedding,
        max_price=_FIXED_COURSE.price - Decimal("1"),
        max_duration_weeks=_FIXED_COURSE.duration_weeks,
        limit=None,
    )
    assert strict == []  # P1: price filter excludes it correctly

    relaxed = await repo.find_ranked_candidates(
        query_embedding,
        max_price=_FIXED_COURSE.price,
        max_duration_weeks=_FIXED_COURSE.duration_weeks,
        limit=None,
    )
    assert len(relaxed) == 1  # P2: relaxing the budget by $1 recovers the candidate


# ── Incremento 3 — BackOffice: GetCourseDetailsTool (BR-26) ──


async def test_find_by_id_returns_the_matching_course(connection_pool):
    await connection_pool.pool.execute("TRUNCATE TABLE courses")
    repo = PostgresCourseRepository(connection_pool)
    await _seed_courses(connection_pool, [_FIXED_COURSE])

    found = await repo.find_by_id(_FIXED_COURSE.course_id)

    assert found is not None
    assert found.name == _FIXED_COURSE.name
    assert found.curriculum == _FIXED_COURSE.curriculum


async def test_find_by_id_returns_none_when_not_found(connection_pool):
    await connection_pool.pool.execute("TRUNCATE TABLE courses")
    repo = PostgresCourseRepository(connection_pool)

    assert await repo.find_by_id("nonexistent") is None
