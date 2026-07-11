"""Integration tests for OutreachAgentService wired behind real HTTP routes (FastAPI
TestClient) — Agent/FoundryChatClient patched (no real Foundry calls, same technique as
test_chat_agent_client_scoring.py), everything else (dedupe across the auto-trigger and
the on-demand HTTP path, send/discard) exercised through the real objects."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from fastapi import FastAPI, HTTPException

from fastapi.testclient import TestClient

from src.adapters.outreach_agent_service import OutreachAgentService, OutreachError
from src.api.schemas import OutreachDraftOut
from src.domain.lead_event_publisher import LeadEventPublisher
from src.domain.models import DraftTrigger, Lead, LeadEvent, LeadScore
from tests.integration.fakes import FakeCourseRepository, FakeDraftRepository, FakeEmailSender, FakeLeadRepository


class _FakeUpdate:
    def __init__(self, text: str) -> None:
        self.text = text


def _build_service(lead_repository, draft_repository, email_sender, lead_event_publisher) -> OutreachAgentService:
    with patch("src.adapters.outreach_agent_service.FoundryChatClient"), patch(
        "src.adapters.outreach_agent_service.Agent"
    ):
        service = OutreachAgentService(
            project_endpoint="https://fake.example",
            model_deployment="fake-model",
            credential=MagicMock(),
            lead_repository=lead_repository,
            course_repository=FakeCourseRepository(),
            draft_repository=draft_repository,
            email_sender=email_sender,
            lead_event_publisher=lead_event_publisher,
        )

    async def _fake_run(*args, **kwargs):
        yield _FakeUpdate("Asunto generado\nCuerpo generado.")

    service._agent.run = MagicMock(side_effect=lambda *a, **kw: _fake_run(*a, **kw))
    return service


def build_test_app(outreach_agent_service: OutreachAgentService) -> FastAPI:
    app = FastAPI()

    @app.post("/leads/{lead_id}/drafts")
    async def generate_draft(lead_id: str):
        try:
            draft = await outreach_agent_service.generate_draft(lead_id, DraftTrigger.ON_DEMAND)
        except OutreachError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return OutreachDraftOut.from_draft(draft).model_dump(mode="json") if draft else None

    @app.get("/leads/{lead_id}/drafts/active")
    async def get_active_draft(lead_id: str):
        draft = await outreach_agent_service.get_active_draft(lead_id)
        return OutreachDraftOut.from_draft(draft).model_dump(mode="json") if draft else None

    @app.post("/drafts/{draft_id}/send")
    async def send_draft(draft_id: str):
        try:
            draft = await outreach_agent_service.send_draft(draft_id)
        except OutreachError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return OutreachDraftOut.from_draft(draft).model_dump(mode="json")

    @app.post("/drafts/{draft_id}/discard")
    async def discard_draft(draft_id: str):
        try:
            draft = await outreach_agent_service.discard_draft(draft_id)
        except OutreachError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return OutreachDraftOut.from_draft(draft).model_dump(mode="json")

    return app


def _lead(lead_id: str = "lead-1", *, email: str | None = "ana@example.com", score=LeadScore.HOT) -> Lead:
    return Lead(
        id=lead_id, created_at=datetime.now(timezone.utc), email=email, score=score,
        service_session_id=lead_id,
    )


def test_on_demand_generate_then_send_via_http():
    lead = _lead()
    lead_repository = FakeLeadRepository([lead])
    draft_repository = FakeDraftRepository()
    email_sender = FakeEmailSender()
    service = _build_service(lead_repository, draft_repository, email_sender, LeadEventPublisher())
    client = TestClient(build_test_app(service))

    generated = client.post(f"/leads/{lead.id}/drafts")
    assert generated.status_code == 200
    draft_id = generated.json()["draft_id"]

    sent = client.post(f"/drafts/{draft_id}/send")
    assert sent.status_code == 200
    assert sent.json()["status"] == "sent"
    assert email_sender.sent == [(lead.email, "Asunto generado", "Cuerpo generado.")]


def test_generate_twice_returns_the_same_pending_draft():
    lead = _lead()
    lead_repository = FakeLeadRepository([lead])
    draft_repository = FakeDraftRepository()
    service = _build_service(lead_repository, draft_repository, FakeEmailSender(), LeadEventPublisher())
    client = TestClient(build_test_app(service))

    first = client.post(f"/leads/{lead.id}/drafts").json()
    second = client.post(f"/leads/{lead.id}/drafts").json()

    assert first["draft_id"] == second["draft_id"]


def test_discard_then_generate_produces_a_new_draft():
    lead = _lead()
    lead_repository = FakeLeadRepository([lead])
    draft_repository = FakeDraftRepository()
    service = _build_service(lead_repository, draft_repository, FakeEmailSender(), LeadEventPublisher())
    client = TestClient(build_test_app(service))

    first = client.post(f"/leads/{lead.id}/drafts").json()
    client.post(f"/drafts/{first['draft_id']}/discard")

    second = client.post(f"/leads/{lead.id}/drafts").json()

    assert second["draft_id"] != first["draft_id"]


def test_repeated_hot_score_events_generate_only_one_active_draft():
    """Story 4 AC: 'a lead is already Hot and a draft already exists for it... a
    duplicate draft is not generated' — exercised through the real LeadEventPublisher
    subscription, not by calling generate_draft directly."""
    lead = _lead()
    lead_repository = FakeLeadRepository([lead])
    draft_repository = FakeDraftRepository()
    publisher = LeadEventPublisher()
    _build_service(lead_repository, draft_repository, FakeEmailSender(), publisher)

    async def _fire_twice():
        await publisher.publish(LeadEvent(event_type="score_changed", lead=lead))
        await publisher.publish(LeadEvent(event_type="score_changed", lead=lead))
        await asyncio.sleep(0.02)

    asyncio.run(_fire_twice())

    active_drafts = [d for d in draft_repository._drafts.values() if d.lead_id == lead.id]
    assert len(active_drafts) == 1


def test_get_active_draft_returns_none_when_no_draft_exists():
    lead = _lead()
    service = _build_service(
        FakeLeadRepository([lead]), FakeDraftRepository(), FakeEmailSender(), LeadEventPublisher()
    )
    client = TestClient(build_test_app(service))

    response = client.get(f"/leads/{lead.id}/drafts/active")

    assert response.status_code == 200
    assert response.json() is None
