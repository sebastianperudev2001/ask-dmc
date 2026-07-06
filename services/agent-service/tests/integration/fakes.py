from __future__ import annotations

from typing import AsyncIterator

from src.domain.models import RecommendationBranch, RecommendationCandidate


class FakeEmbeddingService:
    def __init__(self, embedding: tuple[float, ...] = (1.0, 0.0, 0.0)) -> None:
        self._embedding = embedding

    async def embed(self, text: str) -> tuple[float, ...]:
        return self._embedding


class FakeRecommendationAgentClient:
    def __init__(self, deltas: list[str] | None = None) -> None:
        self._deltas = deltas or ["Basado en tu perfil, ", "te recomiendo este programa."]

    async def stream_recommendation(
        self,
        candidates: list[RecommendationCandidate],
        profile_text: str,
        branch: RecommendationBranch,
    ) -> AsyncIterator[str]:
        for delta in self._deltas:
            yield delta


# ── Incremento 2 — chat conversacional + tool-calling + pago ────────────────────────


class _FakeAgentSession:
    def __init__(self, service_session_id: str | None) -> None:
        self.service_session_id = service_session_id


class FakeChatAgentClient:
    """Drives ChatWebSocketHandler's tool-call pause/resume and session logic without a
    real Foundry Agent. Crucially, the collect_profile_data pause is exercised through
    the REAL PendingToolCallRegistry the handler passes in — only the LLM/agent
    decision-making is faked, not the pause mechanism itself (business-logic-model.md
    Section 8.1)."""

    def __init__(self, on_profile_data_requested, pending_tool_calls, conversation_id=None) -> None:
        self._on_profile_data_requested = on_profile_data_requested
        self._pending_tool_calls = pending_tool_calls
        self._conversation_id = conversation_id
        self._session_counter = 0
        self.record_user_message_calls = 0

    def set_conversation_id(self, conversation_id: str) -> None:
        self._conversation_id = conversation_id

    async def record_user_message(self) -> None:
        """BR-17b: ChatWebSocketHandler calls this once per received user message —
        tracked here so tests can assert the wiring without a real ChatAgentClient."""
        self.record_user_message_calls += 1

    def create_session(self) -> _FakeAgentSession:
        self._session_counter += 1
        return _FakeAgentSession(service_session_id=f"fake-session-{self._session_counter}")

    def get_session(self, service_session_id: str) -> _FakeAgentSession:
        return _FakeAgentSession(service_session_id=service_session_id)

    async def stream(self, user_text: str, session: _FakeAgentSession):
        from decimal import Decimal

        from src.adapters.chat_agent_client import PaymentLinkCreated, ProfileDataRequested, TextDelta

        if user_text == "quiero un curso":
            call_id = "call_fake_1"
            future = self._pending_tool_calls.create(call_id)
            await self._on_profile_data_requested(
                ProfileDataRequested(
                    call_id=call_id,
                    prefill={
                        "budget": 500.0,
                        "max_duration_weeks": 8,
                        "professional_background": "analista",
                        "desired_stack": "data",
                    },
                )
            )
            result = await future
            yield TextDelta(text=f"Gracias, confirmado presupuesto {result['budget']}")
        elif user_text == "quiero pagar":
            yield PaymentLinkCreated(
                checkout_url="https://www.mercadopago.com/checkout/fake",
                preference_id="pref_1",
                amount=Decimal("500"),
            )
            yield TextDelta(text="Aqui tienes tu link de pago")
        else:
            yield TextDelta(text=f"Eco: {user_text}")


class FakeLeadRepository:
    """In-memory LeadRepository fake for webhook flow tests (test_webhook_flow.py)."""

    def __init__(self, leads: list) -> None:
        self._leads = {lead.service_session_id: lead for lead in leads}

    async def save(self, lead) -> None:
        self._leads[lead.service_session_id] = lead

    async def find_by_service_session_id(self, service_session_id: str):
        return self._leads.get(service_session_id)

    async def mark_payment_confirmed(self, lead_id: str, *, payment_id: str) -> None:
        for lead in self._leads.values():
            if lead.id == lead_id:
                lead.payment_confirmed = True
                lead.mercadopago_payment_id = payment_id


class FakeConversationMessageRepository:
    """In-memory ConversationMessageRepository fake — verifies the transcript persisted
    for rehydration after a page reload (test_chat_websocket_flow.py)."""

    def __init__(self) -> None:
        self.messages: list[tuple[str, str, str]] = []  # (conversation_id, role, content)

    async def append(self, conversation_id: str, role, content: str) -> None:
        role_value = role.value if hasattr(role, "value") else role
        self.messages.append((conversation_id, role_value, content))

    async def get_messages(self, conversation_id: str):
        return [(role, content) for conv_id, role, content in self.messages if conv_id == conversation_id]


class FakeConversationSessionStore:
    """In-memory ConversationSessionStore fake — verifies resuming a past conversation
    by conversation_id alone (no client-known service_session_id), the case that
    switching to it from the real history list hits (test_chat_websocket_flow.py)."""

    def __init__(self, initial: dict[str, str] | None = None) -> None:
        self._by_conversation_id: dict[str, str] = dict(initial or {})

    async def get_service_session_id(self, conversation_id: str) -> str | None:
        return self._by_conversation_id.get(conversation_id)

    async def set_service_session_id(self, conversation_id: str, service_session_id: str) -> None:
        self._by_conversation_id[conversation_id] = service_session_id


class FakePaymentClient:
    """In-memory MercadoPagoPaymentClient fake — get_payment returns a scripted result
    keyed by payment_id (test_webhook_flow.py)."""

    def __init__(self, responses: dict) -> None:
        self._responses = responses

    async def get_payment(self, payment_id: str):
        return self._responses[payment_id]
