"""OutreachAgentService — Agent/FoundryChatClient patched at construction time (no real
Foundry/network calls, same technique as test_chat_agent_client_scoring.py); only
dedupe (BR-22/BR-23), the missing-email skip (BR-25), send/discard lifecycle
(PATTERN-26/28), and the fire-and-forget auto-trigger wiring (BR-24) are under test."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.adapters.outreach_agent_service import OutreachAgentService, OutreachError
from src.domain.lead_event_publisher import LeadEventPublisher
from src.domain.models import (
    Course,
    DraftStatus,
    DraftTrigger,
    Lead,
    LeadEvent,
    LeadScore,
    OutreachDraft,
)

pytestmark = pytest.mark.asyncio


class _FakeUpdate:
    def __init__(self, text: str) -> None:
        self.text = text


class FakeLeadRepository:
    def __init__(self, leads: list[Lead] | None = None) -> None:
        self._leads = {lead.id: lead for lead in (leads or [])}

    async def find_by_id(self, lead_id: str) -> Lead | None:
        return self._leads.get(lead_id)

    async def save(self, lead: Lead) -> None:
        self._leads[lead.id] = lead


class FakeCourseRepository:
    def __init__(self, courses: list[Course] | None = None) -> None:
        self._courses = {c.course_id: c for c in (courses or [])}

    async def find_by_id(self, course_id: str) -> Course | None:
        return self._courses.get(course_id)


class FakeDraftRepository:
    def __init__(self) -> None:
        self._drafts: dict[str, OutreachDraft] = {}

    async def save(self, draft: OutreachDraft) -> None:
        self._drafts[draft.draft_id] = draft

    async def find_active_by_lead_id(self, lead_id: str) -> OutreachDraft | None:
        for draft in self._drafts.values():
            if draft.lead_id == lead_id and draft.status == DraftStatus.PENDING:
                return draft
        return None

    async def find_by_id(self, draft_id: str) -> OutreachDraft | None:
        return self._drafts.get(draft_id)

    async def mark_sent(self, draft_id: str) -> OutreachDraft | None:
        draft = self._drafts.get(draft_id)
        if draft is None or draft.status != DraftStatus.PENDING:
            return None
        draft.status = DraftStatus.SENT
        draft.sent_at = datetime.now(timezone.utc)
        return draft

    async def mark_discarded(self, draft_id: str) -> OutreachDraft | None:
        draft = self._drafts.get(draft_id)
        if draft is None:
            return None
        draft.status = DraftStatus.DISCARDED
        return draft


class FakeEmailSender:
    def __init__(self, *, fail: bool = False) -> None:
        self.sent: list[tuple[str, str, str]] = []
        self._fail = fail

    async def send(self, to_email: str, subject: str, body: str) -> None:
        if self._fail:
            raise RuntimeError("email provider unavailable")
        self.sent.append((to_email, subject, body))


def _lead(lead_id: str = "lead-1", *, email: str | None = "ana@example.com", score=LeadScore.HOT) -> Lead:
    return Lead(id=lead_id, created_at=datetime.now(timezone.utc), email=email, score=score)


def _build_service(
    *,
    lead_repository=None,
    course_repository=None,
    draft_repository=None,
    email_sender=None,
    lead_event_publisher=None,
) -> OutreachAgentService:
    with patch("src.adapters.outreach_agent_service.FoundryChatClient"), patch(
        "src.adapters.outreach_agent_service.Agent"
    ):
        service = OutreachAgentService(
            project_endpoint="https://fake.example",
            model_deployment="fake-model",
            credential=MagicMock(),
            lead_repository=lead_repository or FakeLeadRepository(),
            course_repository=course_repository or FakeCourseRepository(),
            draft_repository=draft_repository or FakeDraftRepository(),
            email_sender=email_sender or FakeEmailSender(),
            lead_event_publisher=lead_event_publisher or LeadEventPublisher(),
        )

    async def _fake_run(*args, **kwargs):
        yield _FakeUpdate("Asunto de prueba\nCuerpo del email de prueba.")

    service._agent.run = MagicMock(side_effect=lambda *a, **kw: _fake_run(*a, **kw))
    return service


async def test_generate_draft_creates_a_new_pending_draft():
    lead = _lead()
    service = _build_service(lead_repository=FakeLeadRepository([lead]))

    draft = await service.generate_draft(lead.id, DraftTrigger.ON_DEMAND)

    assert draft is not None
    assert draft.status == DraftStatus.PENDING
    assert draft.subject == "Asunto de prueba"
    assert draft.body == "Cuerpo del email de prueba."


async def test_generate_draft_returns_existing_pending_draft_without_regenerating():
    lead = _lead()
    draft_repository = FakeDraftRepository()
    existing = OutreachDraft(
        draft_id="draft-existing",
        lead_id=lead.id,
        subject="Ya existe",
        body="...",
        created_at=datetime.now(timezone.utc),
    )
    await draft_repository.save(existing)
    service = _build_service(
        lead_repository=FakeLeadRepository([lead]), draft_repository=draft_repository
    )

    result = await service.generate_draft(lead.id, DraftTrigger.ON_DEMAND)

    assert result is existing
    assert result.subject == "Ya existe"


async def test_generate_draft_skips_auto_trigger_when_email_missing():
    lead = _lead(email=None)
    service = _build_service(lead_repository=FakeLeadRepository([lead]))

    result = await service.generate_draft(lead.id, DraftTrigger.AUTO)

    assert result is None


async def test_generate_draft_on_demand_works_even_without_email():
    lead = _lead(email=None)
    service = _build_service(lead_repository=FakeLeadRepository([lead]))

    result = await service.generate_draft(lead.id, DraftTrigger.ON_DEMAND)

    assert result is not None


async def test_generate_draft_raises_when_lead_not_found():
    service = _build_service()

    with pytest.raises(OutreachError):
        await service.generate_draft("nonexistent", DraftTrigger.ON_DEMAND)


async def test_send_draft_rejects_when_lead_has_no_email():
    lead = _lead(email=None)
    draft_repository = FakeDraftRepository()
    draft = OutreachDraft(
        draft_id="draft-1",
        lead_id=lead.id,
        subject="s",
        body="b",
        created_at=datetime.now(timezone.utc),
    )
    await draft_repository.save(draft)
    service = _build_service(
        lead_repository=FakeLeadRepository([lead]), draft_repository=draft_repository
    )

    with pytest.raises(OutreachError):
        await service.send_draft("draft-1")


async def test_send_draft_marks_sent_and_calls_email_sender():
    lead = _lead()
    draft_repository = FakeDraftRepository()
    draft = OutreachDraft(
        draft_id="draft-1",
        lead_id=lead.id,
        subject="s",
        body="b",
        created_at=datetime.now(timezone.utc),
    )
    await draft_repository.save(draft)
    email_sender = FakeEmailSender()
    service = _build_service(
        lead_repository=FakeLeadRepository([lead]),
        draft_repository=draft_repository,
        email_sender=email_sender,
    )

    sent = await service.send_draft("draft-1")

    assert sent.status == DraftStatus.SENT
    assert email_sender.sent == [(lead.email, "s", "b")]


async def test_send_draft_stays_pending_on_email_failure():
    lead = _lead()
    draft_repository = FakeDraftRepository()
    draft = OutreachDraft(
        draft_id="draft-1",
        lead_id=lead.id,
        subject="s",
        body="b",
        created_at=datetime.now(timezone.utc),
    )
    await draft_repository.save(draft)
    email_sender = FakeEmailSender(fail=True)
    service = _build_service(
        lead_repository=FakeLeadRepository([lead]),
        draft_repository=draft_repository,
        email_sender=email_sender,
    )

    with pytest.raises(RuntimeError):
        await service.send_draft("draft-1")

    unchanged = await draft_repository.find_by_id("draft-1")
    assert unchanged.status == DraftStatus.PENDING


async def test_send_draft_is_idempotent_when_already_sent():
    lead = _lead()
    draft_repository = FakeDraftRepository()
    draft = OutreachDraft(
        draft_id="draft-1",
        lead_id=lead.id,
        subject="s",
        body="b",
        created_at=datetime.now(timezone.utc),
        status=DraftStatus.SENT,
    )
    await draft_repository.save(draft)
    email_sender = FakeEmailSender()
    service = _build_service(
        lead_repository=FakeLeadRepository([lead]),
        draft_repository=draft_repository,
        email_sender=email_sender,
    )

    result = await service.send_draft("draft-1")

    assert result.status == DraftStatus.SENT
    assert email_sender.sent == []  # never re-sent


async def test_discard_draft_marks_discarded():
    draft_repository = FakeDraftRepository()
    draft = OutreachDraft(
        draft_id="draft-1",
        lead_id="lead-1",
        subject="s",
        body="b",
        created_at=datetime.now(timezone.utc),
    )
    await draft_repository.save(draft)
    service = _build_service(draft_repository=draft_repository)

    discarded = await service.discard_draft("draft-1")

    assert discarded.status == DraftStatus.DISCARDED


async def test_score_changed_to_hot_triggers_auto_draft_generation():
    lead = _lead()
    publisher = LeadEventPublisher()
    draft_repository = FakeDraftRepository()
    _build_service(
        lead_repository=FakeLeadRepository([lead]),
        draft_repository=draft_repository,
        lead_event_publisher=publisher,
    )

    await publisher.publish(LeadEvent(event_type="score_changed", lead=lead))
    # BR-24: fire-and-forget — the handler schedules a background task; give the event
    # loop a moment to let it actually run and complete.
    await asyncio.sleep(0.01)

    active = await draft_repository.find_active_by_lead_id(lead.id)
    assert active is not None


async def test_score_changed_to_warm_does_not_trigger_auto_draft():
    lead = _lead(score=LeadScore.WARM)
    publisher = LeadEventPublisher()
    draft_repository = FakeDraftRepository()
    _build_service(
        lead_repository=FakeLeadRepository([lead]),
        draft_repository=draft_repository,
        lead_event_publisher=publisher,
    )

    await publisher.publish(LeadEvent(event_type="score_changed", lead=lead))
    await asyncio.sleep(0.01)

    assert await draft_repository.find_active_by_lead_id(lead.id) is None


async def test_lead_created_event_does_not_trigger_auto_draft():
    lead = _lead()
    publisher = LeadEventPublisher()
    draft_repository = FakeDraftRepository()
    _build_service(
        lead_repository=FakeLeadRepository([lead]),
        draft_repository=draft_repository,
        lead_event_publisher=publisher,
    )

    await publisher.publish(LeadEvent(event_type="created", lead=lead))
    await asyncio.sleep(0.01)

    assert await draft_repository.find_active_by_lead_id(lead.id) is None


async def test_motivation_set_event_regenerates_a_stale_auto_draft():
    lead = _lead()
    draft_repository = FakeDraftRepository()
    stale = OutreachDraft(
        draft_id="draft-stale",
        lead_id=lead.id,
        subject="Asunto viejo",
        body="Cuerpo viejo sin motivacion.",
        created_at=datetime.now(timezone.utc),
        trigger=DraftTrigger.AUTO,
    )
    await draft_repository.save(stale)
    publisher = LeadEventPublisher()
    _build_service(
        lead_repository=FakeLeadRepository([lead]),
        draft_repository=draft_repository,
        lead_event_publisher=publisher,
    )

    await publisher.publish(LeadEvent(event_type="motivation_set", lead=lead))
    await asyncio.sleep(0.01)

    active = await draft_repository.find_active_by_lead_id(lead.id)
    assert active is not None
    assert active.draft_id != "draft-stale"
    stale_reloaded = await draft_repository.find_by_id("draft-stale")
    assert stale_reloaded.status == DraftStatus.DISCARDED


async def test_motivation_set_event_does_nothing_when_no_draft_exists_yet():
    lead = _lead()
    draft_repository = FakeDraftRepository()
    publisher = LeadEventPublisher()
    _build_service(
        lead_repository=FakeLeadRepository([lead]),
        draft_repository=draft_repository,
        lead_event_publisher=publisher,
    )

    await publisher.publish(LeadEvent(event_type="motivation_set", lead=lead))
    await asyncio.sleep(0.01)

    assert await draft_repository.find_active_by_lead_id(lead.id) is None


async def test_motivation_set_event_leaves_an_on_demand_draft_alone():
    lead = _lead()
    draft_repository = FakeDraftRepository()
    on_demand = OutreachDraft(
        draft_id="draft-on-demand",
        lead_id=lead.id,
        subject="Generado por staff",
        body="...",
        created_at=datetime.now(timezone.utc),
        trigger=DraftTrigger.ON_DEMAND,
    )
    await draft_repository.save(on_demand)
    publisher = LeadEventPublisher()
    _build_service(
        lead_repository=FakeLeadRepository([lead]),
        draft_repository=draft_repository,
        lead_event_publisher=publisher,
    )

    await publisher.publish(LeadEvent(event_type="motivation_set", lead=lead))
    await asyncio.sleep(0.01)

    active = await draft_repository.find_active_by_lead_id(lead.id)
    assert active is not None
    assert active.draft_id == "draft-on-demand"
