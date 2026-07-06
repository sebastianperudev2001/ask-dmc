"""BR-17b — engagement-based lead scoring wired into ChatAgentClient. `Agent` and
`FoundryChatClient` are patched at construction time (no real Foundry/network calls);
only the scoring wiring (record_user_message, _apply_engagement_floor) is under test."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.adapters.chat_agent_client import ChatAgentClient
from src.domain.models import Lead, LeadScore
from src.domain.pending_tool_calls import PendingToolCallRegistry


class FakeLeadRepository:
    def __init__(self, leads: list[Lead] | None = None) -> None:
        self._leads: dict[str, Lead] = {lead.service_session_id: lead for lead in (leads or [])}

    async def save(self, lead: Lead) -> None:
        self._leads[lead.service_session_id] = lead

    async def find_by_service_session_id(self, service_session_id: str) -> Lead | None:
        return self._leads.get(service_session_id)


def _build_client(lead_repository: FakeLeadRepository, conversation_id: str = "conv-1") -> ChatAgentClient:
    with patch("src.adapters.chat_agent_client.FoundryChatClient"), patch(
        "src.adapters.chat_agent_client.Agent"
    ):
        return ChatAgentClient(
            project_endpoint="https://fake.example",
            model_deployment="fake-model",
            credential=MagicMock(),
            retry_policy=MagicMock(),
            payment_client=MagicMock(),
            pending_tool_calls=PendingToolCallRegistry(),
            on_profile_data_requested=MagicMock(),
            orchestrator=MagicMock(),
            embedding_service=MagicMock(),
            lead_repository=lead_repository,
            conversation_id=conversation_id,
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
