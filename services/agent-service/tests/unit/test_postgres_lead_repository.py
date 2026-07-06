"""Tests against a REAL Postgres instance (migrations/002_create_leads_and_sessions.sql
must already be applied — see README.md). Requires TEST_DATABASE_URL env var; skipped
otherwise — same pattern as test_postgres_repository.py."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.adapters.postgres_lead_repository import PostgresLeadRepository
from src.domain.models import Lead, LeadScore, Motivation
from tests.conftest import requires_postgres

pytestmark = [requires_postgres, pytest.mark.asyncio]


def _lead(service_session_id: str) -> Lead:
    return Lead(
        id=f"lead-{service_session_id}",
        created_at=datetime.now(timezone.utc),
        name="Ana Torres",
        email="ana@example.com",
        profile_summary="Analista de datos buscando especializarse",
        motivation=Motivation.GROWTH,
        motivation_detail="Quiero avanzar en mi carrera",
        recommended_programs=["diploma-data-analyst"],
        score=LeadScore.WARM,
        score_justification="Motivación clara, sin decisión de compra aún",
        service_session_id=service_session_id,
    )


async def test_save_and_find_by_service_session_id(connection_pool):
    await connection_pool.pool.execute("TRUNCATE TABLE conversation_sessions, leads")
    repo = PostgresLeadRepository(connection_pool)
    lead = _lead("test-session-1")

    await repo.save(lead)
    found = await repo.find_by_service_session_id("test-session-1")

    assert found is not None
    assert found.id == lead.id
    assert found.name == "Ana Torres"
    assert found.motivation == Motivation.GROWTH
    assert found.score == LeadScore.WARM
    assert found.recommended_programs == ["diploma-data-analyst"]


async def test_find_by_service_session_id_returns_none_when_not_found(connection_pool):
    await connection_pool.pool.execute("TRUNCATE TABLE conversation_sessions, leads")
    repo = PostgresLeadRepository(connection_pool)

    assert await repo.find_by_service_session_id("nonexistent") is None


async def test_mark_payment_confirmed(connection_pool):
    await connection_pool.pool.execute("TRUNCATE TABLE conversation_sessions, leads")
    repo = PostgresLeadRepository(connection_pool)
    lead = _lead("test-session-2")
    await repo.save(lead)

    await repo.mark_payment_confirmed(lead.id, payment_id="pay-123")

    updated = await repo.find_by_service_session_id("test-session-2")
    assert updated.payment_confirmed is True
    assert updated.mercadopago_payment_id == "pay-123"


async def test_save_upserts_existing_lead(connection_pool):
    await connection_pool.pool.execute("TRUNCATE TABLE conversation_sessions, leads")
    repo = PostgresLeadRepository(connection_pool)
    lead = _lead("test-session-3")
    await repo.save(lead)

    lead.score = LeadScore.HOT
    lead.score_justification = "Pidió link de pago"
    await repo.save(lead)

    updated = await repo.find_by_service_session_id("test-session-3")
    assert updated.score == LeadScore.HOT
    assert updated.score_justification == "Pidió link de pago"
