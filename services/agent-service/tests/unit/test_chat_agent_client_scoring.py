"""BR-17b — lead scoring wired into ChatAgentClient. `Agent` and `FoundryChatClient`
are patched at construction time (no real Foundry/network calls); only the scoring
wiring (record_user_message, _raise_score_floor, _flag_purchase_intent,
_collect_profile_data's form-completion floor) is under test."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.adapters.chat_agent_client import ChatAgentClient
from src.domain.lead_event_publisher import LeadEventPublisher
from src.domain.models import Lead, LeadScore, Motivation
from src.domain.pending_tool_calls import PendingToolCallRegistry


class FakeLeadRepository:
    def __init__(self, leads: list[Lead] | None = None) -> None:
        self._leads: dict[str, Lead] = {lead.service_session_id: lead for lead in (leads or [])}

    async def save(self, lead: Lead) -> None:
        self._leads[lead.service_session_id] = lead

    async def find_by_service_session_id(self, service_session_id: str) -> Lead | None:
        return self._leads.get(service_session_id)


def _build_client(
    lead_repository: FakeLeadRepository,
    conversation_id: str = "conv-1",
    lead_event_publisher: LeadEventPublisher | None = None,
    on_profile_data_requested=None,
    pending_tool_calls: PendingToolCallRegistry | None = None,
) -> ChatAgentClient:
    with patch("src.adapters.chat_agent_client.FoundryChatClient"), patch(
        "src.adapters.chat_agent_client.Agent"
    ):
        return ChatAgentClient(
            project_endpoint="https://fake.example",
            model_deployment="fake-model",
            credential=MagicMock(),
            retry_policy=MagicMock(),
            payment_client=MagicMock(),
            pending_tool_calls=pending_tool_calls or PendingToolCallRegistry(),
            on_profile_data_requested=on_profile_data_requested or MagicMock(),
            orchestrator=MagicMock(),
            embedding_service=MagicMock(),
            lead_repository=lead_repository,
            conversation_id=conversation_id,
            lead_event_publisher=lead_event_publisher,
        )


@pytest.mark.asyncio
async def test_record_user_message_does_not_create_a_lead_below_5_messages():
    repo = FakeLeadRepository()
    client = _build_client(repo)

    for _ in range(4):
        await client.record_user_message()

    assert await repo.find_by_service_session_id("conv-1") is None


@pytest.mark.asyncio
async def test_record_user_message_raises_score_to_warm_at_5_messages():
    lead = Lead(id="lead-1", created_at=datetime.now(timezone.utc), service_session_id="conv-1")
    repo = FakeLeadRepository([lead])
    client = _build_client(repo)

    for _ in range(5):
        await client.record_user_message()

    stored = await repo.find_by_service_session_id("conv-1")
    assert stored.score == LeadScore.WARM


@pytest.mark.asyncio
async def test_record_user_message_raises_score_to_hot_at_10_messages():
    lead = Lead(id="lead-1", created_at=datetime.now(timezone.utc), service_session_id="conv-1")
    repo = FakeLeadRepository([lead])
    client = _build_client(repo)

    for _ in range(10):
        await client.record_user_message()

    stored = await repo.find_by_service_session_id("conv-1")
    assert stored.score == LeadScore.HOT


@pytest.mark.asyncio
async def test_record_user_message_never_downgrades_an_already_hot_lead():
    lead = Lead(
        id="lead-1",
        created_at=datetime.now(timezone.utc),
        service_session_id="conv-1",
        score=LeadScore.HOT,
        score_justification="Expresó intención de compra con datos de contacto completos.",
    )
    repo = FakeLeadRepository([lead])
    client = _build_client(repo)

    await client.record_user_message()  # count=1, well below any floor

    stored = await repo.find_by_service_session_id("conv-1")
    assert stored.score == LeadScore.HOT
    assert stored.score_justification == "Expresó intención de compra con datos de contacto completos."


@pytest.mark.asyncio
async def test_flag_purchase_intent_raises_score_to_warm():
    lead = Lead(id="lead-1", created_at=datetime.now(timezone.utc), service_session_id="conv-1")
    repo = FakeLeadRepository([lead])
    client = _build_client(repo)

    await client._flag_purchase_intent("Dijo que quiere inscribirse ya mismo")

    stored = await repo.find_by_service_session_id("conv-1")
    assert stored.score == LeadScore.WARM
    assert "Dijo que quiere inscribirse ya mismo" in stored.score_justification


@pytest.mark.asyncio
async def test_flag_purchase_intent_creates_a_lead_when_none_exists_yet():
    repo = FakeLeadRepository()
    client = _build_client(repo)

    await client._flag_purchase_intent("Primer mensaje: quiere comprar de inmediato")

    stored = await repo.find_by_service_session_id("conv-1")
    assert stored is not None
    assert stored.score == LeadScore.WARM


@pytest.mark.asyncio
async def test_flag_purchase_intent_never_downgrades_an_already_hot_lead():
    lead = Lead(
        id="lead-1",
        created_at=datetime.now(timezone.utc),
        service_session_id="conv-1",
        score=LeadScore.HOT,
        score_justification="ya hot",
    )
    repo = FakeLeadRepository([lead])
    client = _build_client(repo)

    await client._flag_purchase_intent("mensaje temprano")

    stored = await repo.find_by_service_session_id("conv-1")
    assert stored.score == LeadScore.HOT
    assert stored.score_justification == "ya hot"


@pytest.mark.asyncio
async def test_set_lead_motivation_persists_a_valid_category():
    lead = Lead(id="lead-1", created_at=datetime.now(timezone.utc), service_session_id="conv-1")
    repo = FakeLeadRepository([lead])
    client = _build_client(repo)

    await client._set_lead_motivation("salary", "Quiere un aumento de sueldo")

    stored = await repo.find_by_service_session_id("conv-1")
    assert stored.motivation == Motivation.SALARY
    assert stored.motivation_detail == "Quiere un aumento de sueldo"


@pytest.mark.asyncio
async def test_set_lead_motivation_falls_back_to_undefined_on_an_invalid_value():
    lead = Lead(id="lead-1", created_at=datetime.now(timezone.utc), service_session_id="conv-1")
    repo = FakeLeadRepository([lead])
    client = _build_client(repo)

    await client._set_lead_motivation("not-a-real-category")

    stored = await repo.find_by_service_session_id("conv-1")
    assert stored.motivation == Motivation.UNDEFINED


# ── Incremento 3 — BackOffice: LeadEvent publishing (BR-29) ──


@pytest.mark.asyncio
async def test_upsert_lead_does_not_publish_below_the_first_score_floor():
    repo = FakeLeadRepository()
    publisher = LeadEventPublisher()
    received = []

    async def handler(event) -> None:
        received.append(event)

    publisher.subscribe(handler)
    client = _build_client(repo, lead_event_publisher=publisher)

    await client.record_user_message()

    assert received == []  # below the 5-message floor — no Lead created/saved yet


@pytest.mark.asyncio
async def test_upsert_lead_publishes_created_then_score_changed():
    repo = FakeLeadRepository()
    publisher = LeadEventPublisher()
    received = []

    async def handler(event) -> None:
        received.append(event)

    publisher.subscribe(handler)
    client = _build_client(repo, lead_event_publisher=publisher)

    for _ in range(5):  # reaches the warm floor -> first Lead save
        await client.record_user_message()
    for _ in range(5):  # reaches the hot floor -> second Lead save
        await client.record_user_message()

    assert [event.event_type for event in received] == ["created", "score_changed"]
    assert received[-1].lead.score == LeadScore.HOT


@pytest.mark.asyncio
async def test_collect_profile_data_resolution_raises_score_to_hot():
    lead = Lead(id="lead-1", created_at=datetime.now(timezone.utc), service_session_id="conv-1")
    repo = FakeLeadRepository([lead])
    requested = []

    async def on_requested(event):
        requested.append(event)

    pending = PendingToolCallRegistry()
    client = _build_client(repo, on_profile_data_requested=on_requested, pending_tool_calls=pending)

    task = asyncio.create_task(
        client._collect_profile_data(
            budget=500.0,
            max_duration_weeks=8,
            professional_background="analista",
            desired_stack="data",
        )
    )
    await asyncio.sleep(0)  # let it reach the pause point
    call_id = requested[0].call_id
    pending.resolve(
        call_id,
        {
            "budget": 500.0,
            "max_duration_weeks": 8,
            "professional_background": "analista",
            "desired_stack": "data",
            "name": "Juan Pérez",
            "email": "juan@example.com",
        },
    )
    await task

    stored = await repo.find_by_service_session_id("conv-1")
    assert stored.score == LeadScore.HOT
    assert stored.score_justification == "Completó el formulario de perfil con datos de contacto confirmados."
