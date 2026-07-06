"""Domain-appropriate Hypothesis generators (PBT-07) — reusable across property tests."""
from __future__ import annotations

from decimal import Decimal

from hypothesis import strategies as st

from src.domain.models import Course, RecommendationRequest

EMBEDDING_DIMS = 1536

# Postgres `text` columns reject embedded NUL bytes and other control characters outright
# (CharacterNotInRepertoireError) — real course names/descriptions, written by humans,
# never contain them. Excluding Cc (control) and Cs (surrogates) reflects that domain
# constraint (PBT-07), it isn't just a Postgres workaround.
_TEXT_ALPHABET = st.characters(blacklist_categories=("Cs", "Cc"))


def embeddings(active_dims: int = 8) -> st.SearchStrategy[tuple[float, ...]]:
    """Real 1536-dim vector, but generating 1536 independent random floats per Hypothesis
    example is prohibitively expensive (triggers Unsatisfiable/data_too_large even with
    health checks suppressed — verified against a real Postgres in this session). Instead,
    draw a small number of "active" components and zero-pad to the required width: cosine
    similarity behaves identically since the padding is the same shape across all vectors,
    while generation stays cheap enough for property tests against a real database."""
    active = st.lists(
        st.floats(min_value=-1.0, max_value=1.0, allow_nan=False, allow_infinity=False),
        min_size=active_dims,
        max_size=active_dims,
    ).filter(lambda values: any(v != 0.0 for v in values))  # real embeddings are never the zero vector
    return active.map(lambda values: tuple(values) + (0.0,) * (EMBEDDING_DIMS - active_dims))


def small_embeddings(dims: int = 8) -> st.SearchStrategy[tuple[float, ...]]:
    """Lower-dimensional embeddings for fast property tests that only care about
    relative ranking, not the real 1536-dim shape."""
    return st.lists(
        st.floats(min_value=-1.0, max_value=1.0, allow_nan=False, allow_infinity=False),
        min_size=dims,
        max_size=dims,
    ).map(tuple)


def courses(
    min_price: str = "100",
    max_price: str = "10000",
    embedding_strategy: st.SearchStrategy[tuple[float, ...]] | None = None,
) -> st.SearchStrategy[Course]:
    """`embedding_strategy` defaults to `small_embeddings()` (fast, fine for the
    InMemoryCourseRepository fake). Tests against a REAL Postgres `courses` table
    (vector(1536) column) must pass `embeddings()` instead — the schema rejects any
    other dimension (see test_postgres_repository.py)."""
    return st.builds(
        Course,
        course_id=st.uuids().map(str),
        name=st.text(min_size=1, max_size=60, alphabet=_TEXT_ALPHABET),
        description=st.text(min_size=1, max_size=300, alphabet=_TEXT_ALPHABET),
        category=st.sampled_from(
            ["Data Science", "Data Engineering", "Marketing Digital", "IA & Automatización"]
        ),
        curriculum=st.lists(
            st.text(min_size=1, max_size=40, alphabet=_TEXT_ALPHABET), min_size=1, max_size=8
        ).map(tuple),
        price=st.decimals(
            min_value=Decimal(min_price), max_value=Decimal(max_price), places=2
        ),
        duration_weeks=st.integers(min_value=1, max_value=52),
        embedding=embedding_strategy if embedding_strategy is not None else small_embeddings(),
    )


def recommendation_requests() -> st.SearchStrategy[RecommendationRequest]:
    return st.builds(
        RecommendationRequest,
        budget=st.decimals(min_value=Decimal("100"), max_value=Decimal("10000"), places=2),
        max_duration_weeks=st.integers(min_value=1, max_value=52),
        professional_background=st.text(min_size=1, max_size=200),
        desired_stack=st.text(min_size=1, max_size=100),
    )
