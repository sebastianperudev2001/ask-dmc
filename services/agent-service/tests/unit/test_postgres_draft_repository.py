"""Tests against a REAL Postgres instance (migrations/002_create_leads_and_sessions.sql
and 004_create_outreach_drafts.sql must already be applied — see README.md). Requires
TEST_DATABASE_URL env var; skipped otherwise — same pattern as
test_postgres_lead_repository.py."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.adapters.postgres_draft_repository import PostgresDraftRepository
from src.adapters.postgres_lead_repository import PostgresLeadRepository
from src.domain.models import DraftStatus, DraftTrigger, Lead, OutreachDraft
from tests.conftest import requires_postgres

pytestmark = [requires_postgres, pytest.mark.asyncio]


def _draft(draft_id: str, lead_id: str, *, status: DraftStatus = DraftStatus.PENDING) -> OutreachDraft:
    return OutreachDraft(
        draft_id=draft_id,
        lead_id=lead_id,
        subject="Sigamos conversando sobre tu programa ideal",
        body="Hola! Vi que te interesa el diploma de Data Analyst...",
        created_at=datetime.now(timezone.utc),
        status=status,
        trigger=DraftTrigger.AUTO,
    )


async def _seed_lead(connection_pool, lead_id: str) -> None:
    lead_repo = PostgresLeadRepository(connection_pool)
    await lead_repo.save(
        Lead(id=lead_id, created_at=datetime.now(timezone.utc), service_session_id=f"session-{lead_id}")
    )


async def test_save_and_find_by_id(connection_pool):
    await connection_pool.pool.execute("TRUNCATE TABLE outreach_drafts, conversation_sessions, leads")
    await _seed_lead(connection_pool, "lead-1")
    repo = PostgresDraftRepository(connection_pool)
    draft = _draft("draft-1", "lead-1")

    await repo.save(draft)
    found = await repo.find_by_id("draft-1")

    assert found is not None
    assert found.subject == draft.subject
    assert found.status == DraftStatus.PENDING
    assert found.trigger == DraftTrigger.AUTO


async def test_find_active_by_lead_id_returns_only_pending_drafts(connection_pool):
    await connection_pool.pool.execute("TRUNCATE TABLE outreach_drafts, conversation_sessions, leads")
    await _seed_lead(connection_pool, "lead-2")
    repo = PostgresDraftRepository(connection_pool)
    await repo.save(_draft("draft-2", "lead-2", status=DraftStatus.DISCARDED))

    assert await repo.find_active_by_lead_id("lead-2") is None

    await repo.save(_draft("draft-3", "lead-2", status=DraftStatus.PENDING))
    active = await repo.find_active_by_lead_id("lead-2")

    assert active is not None
    assert active.draft_id == "draft-3"


async def test_mark_sent_updates_a_pending_draft(connection_pool):
    await connection_pool.pool.execute("TRUNCATE TABLE outreach_drafts, conversation_sessions, leads")
    await _seed_lead(connection_pool, "lead-3")
    repo = PostgresDraftRepository(connection_pool)
    await repo.save(_draft("draft-4", "lead-3"))

    sent = await repo.mark_sent("draft-4")

    assert sent is not None
    assert sent.status == DraftStatus.SENT
    assert sent.sent_at is not None


async def test_mark_sent_is_a_no_op_when_draft_is_not_pending(connection_pool):
    """PATTERN-28 — the atomic guard: a second mark_sent call (duplicate/concurrent
    send) must not re-send or overwrite sent_at."""
    await connection_pool.pool.execute("TRUNCATE TABLE outreach_drafts, conversation_sessions, leads")
    await _seed_lead(connection_pool, "lead-4")
    repo = PostgresDraftRepository(connection_pool)
    await repo.save(_draft("draft-5", "lead-4"))
    first = await repo.mark_sent("draft-5")

    second = await repo.mark_sent("draft-5")

    assert second is None
    unchanged = await repo.find_by_id("draft-5")
    assert unchanged.sent_at == first.sent_at


async def test_mark_discarded_updates_status(connection_pool):
    await connection_pool.pool.execute("TRUNCATE TABLE outreach_drafts, conversation_sessions, leads")
    await _seed_lead(connection_pool, "lead-5")
    repo = PostgresDraftRepository(connection_pool)
    await repo.save(_draft("draft-6", "lead-5"))

    discarded = await repo.mark_discarded("draft-6")

    assert discarded is not None
    assert discarded.status == DraftStatus.DISCARDED
