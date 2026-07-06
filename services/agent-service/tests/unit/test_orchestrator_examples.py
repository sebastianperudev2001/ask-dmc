"""Example-based tests (PBT-10) pinning the critical BR-03/BR-11 branch scenarios —
complements the property tests in test_orchestrator_properties.py, does not replace them."""
from __future__ import annotations

from decimal import Decimal

import pytest

from src.domain.models import Course, RecommendationBranch, RecommendationRequest
from src.domain.orchestrator import RecommendationOrchestrator
from tests.unit.fakes import InMemoryCourseRepository

QUERY_EMBEDDING = (1.0, 0.0, 0.0)

AFFORDABLE_COURSE = Course(
    course_id="diploma-data-science",
    name="Diploma en Data Science",
    description="Programa integral de Data Science",
    category="Data Science",
    curriculum=("Python", "Machine Learning", "Estadística"),
    price=Decimal("3000"),
    duration_weeks=10,
    embedding=(1.0, 0.0, 0.0),
)

SLIGHTLY_OVER_BUDGET_COURSE = Course(
    course_id="maestria-data-science",
    name="Maestría en Data Science",
    description="Programa avanzado",
    category="Data Science",
    curriculum=("Deep Learning", "MLOps"),
    # Fuera del filtro estricto (budget=3500, max_duration=12) pero DENTRO del relajado
    # (relaxed_budget=4200, relaxed_duration=18) — para de verdad ejercitar la rama de
    # oferta de relajación (BR-03), a diferencia de un curso tan caro/largo que quede
    # fuera incluso del criterio ampliado (ver test_relaxed_criteria_also_empty_...).
    price=Decimal("4000"),
    duration_weeks=15,
    embedding=(1.0, 0.0, 0.0),
)

BASE_REQUEST = RecommendationRequest(
    budget=Decimal("3500"),
    max_duration_weeks=12,
    professional_background="Data Engineer en Yape",
    desired_stack="Data Science",
)


@pytest.mark.asyncio
async def test_exact_match_found_no_confirmation_needed():
    repo = InMemoryCourseRepository([AFFORDABLE_COURSE, SLIGHTLY_OVER_BUDGET_COURSE])
    orchestrator = RecommendationOrchestrator(repo)

    result = await orchestrator.start(BASE_REQUEST, QUERY_EMBEDDING)

    assert result.needs_confirmation is False
    assert result.branch == RecommendationBranch.EXACT_MATCH
    assert [c.course.course_id for c in result.candidates] == ["diploma-data-science"]
    assert all(c.filters_relaxed == () for c in result.candidates)


@pytest.mark.asyncio
async def test_relaxation_offered_then_confirmed():
    repo = InMemoryCourseRepository([SLIGHTLY_OVER_BUDGET_COURSE])
    orchestrator = RecommendationOrchestrator(repo)

    start_result = await orchestrator.start(BASE_REQUEST, QUERY_EMBEDDING)
    assert start_result.needs_confirmation is True
    assert start_result.relaxed_budget == Decimal("3500") * Decimal("1.2")
    assert start_result.relaxed_duration_weeks == 18  # ceil(12 * 1.5)
    assert [c.course.course_id for c in start_result.candidates] == ["maestria-data-science"]

    final_result = await orchestrator.resolve_after_confirmation(
        start_result.candidates, confirmed=True, query_embedding=QUERY_EMBEDDING
    )
    assert final_result.needs_confirmation is False
    assert final_result.branch == RecommendationBranch.RELAXED_MATCH
    assert final_result.candidates[0].filters_relaxed == ("budget", "duration")


@pytest.mark.asyncio
async def test_relaxation_offered_then_declined_falls_back_to_full_catalog():
    repo = InMemoryCourseRepository([SLIGHTLY_OVER_BUDGET_COURSE])
    orchestrator = RecommendationOrchestrator(repo)

    start_result = await orchestrator.start(BASE_REQUEST, QUERY_EMBEDDING)
    assert start_result.needs_confirmation is True

    final_result = await orchestrator.resolve_after_confirmation(
        start_result.candidates, confirmed=False, query_embedding=QUERY_EMBEDDING
    )
    assert final_result.branch == RecommendationBranch.FULL_CATALOG
    assert all(c.from_full_catalog for c in final_result.candidates)
    assert [c.course.course_id for c in final_result.candidates] == ["maestria-data-science"]


@pytest.mark.asyncio
async def test_relaxed_criteria_also_empty_skips_straight_to_full_catalog():
    way_too_expensive = Course(
        course_id="programa-ejecutivo",
        name="Programa Ejecutivo",
        description="Programa premium",
        category="Data Science",
        curriculum=("Estrategia de Datos",),
        price=Decimal("20000"),
        duration_weeks=52,
        embedding=(1.0, 0.0, 0.0),
    )
    repo = InMemoryCourseRepository([way_too_expensive])
    orchestrator = RecommendationOrchestrator(repo)

    result = await orchestrator.start(BASE_REQUEST, QUERY_EMBEDDING)

    assert result.needs_confirmation is False
    assert result.branch == RecommendationBranch.FULL_CATALOG
    assert [c.course.course_id for c in result.candidates] == ["programa-ejecutivo"]


@pytest.mark.asyncio
async def test_empty_catalog_returns_empty_full_catalog_result():
    repo = InMemoryCourseRepository([])
    orchestrator = RecommendationOrchestrator(repo)

    result = await orchestrator.start(BASE_REQUEST, QUERY_EMBEDDING)

    assert result.needs_confirmation is False
    assert result.branch == RecommendationBranch.FULL_CATALOG
    assert result.candidates == []


def test_recommendation_request_rejects_incomplete_fields():
    with pytest.raises(ValueError):
        RecommendationRequest(
            budget=Decimal("0"),
            max_duration_weeks=10,
            professional_background="algo",
            desired_stack="algo",
        )
    with pytest.raises(ValueError):
        RecommendationRequest(
            budget=Decimal("1000"),
            max_duration_weeks=10,
            professional_background="   ",
            desired_stack="algo",
        )
