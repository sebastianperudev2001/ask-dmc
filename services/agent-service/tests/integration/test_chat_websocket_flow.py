"""Integration tests for ChatWebSocketHandler — exercises the free-chat + tool-calling
protocol (business-logic-model.md Section 9) against FakeChatAgentClient (no real
Foundry Agent/Mercado Pago). The collect_profile_data pause/resume goes through the
real PendingToolCallRegistry (only the LLM decision is faked)."""
from __future__ import annotations

import asyncio

import pytest
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.testclient import TestClient

from src.api.chat_websocket_handler import ChatWebSocketHandler
from tests.integration.fakes import (
    FakeChatAgentClient,
    FakeConversationMessageRepository,
    FakeConversationSessionStore,
)


class FakeWebSocket:
    """Minimal WebSocket double giving direct, deterministic control over disconnect
    timing — used to prove `handle_connection` itself doesn't raise, without relying on
    TestClient's background-thread transport (which doesn't surface the crash the same
    way real uvicorn does).

    The "disconnect" (raising WebSocketDisconnect on the next receive) is deferred until
    AFTER a `profile_data_requested` event has actually been sent — matching the real
    scenario (user sees the widget, then abandons it by navigating away) and, crucially,
    guaranteeing the pending tool-call future already exists in the registry by the time
    the disconnect is processed. Without this synchronization, an unrelated race (the
    disconnect being processed before the future is even created) dominates instead and
    the call just hangs — a real but different bug, not the one being reproduced here."""

    def __init__(self, incoming: list[dict]) -> None:
        self._incoming = list(incoming)
        self.sent: list[dict] = []
        self._profile_data_requested = asyncio.Event()

    async def accept(self) -> None:
        pass

    async def receive_json(self) -> dict:
        if self._incoming:
            return self._incoming.pop(0)
        await self._profile_data_requested.wait()
        raise WebSocketDisconnect()

    async def send_json(self, data: dict) -> None:
        self.sent.append(data)
        if data.get("type") == "profile_data_requested":
            self._profile_data_requested.set()


def build_test_app(conversation_message_repository=None, conversation_session_store=None) -> FastAPI:
    app = FastAPI()
    handler = ChatWebSocketHandler(
        agent_client_factory=FakeChatAgentClient,
        conversation_message_repository=conversation_message_repository,
        conversation_session_store=conversation_session_store,
    )

    @app.websocket("/ws")
    async def ws_route(websocket: WebSocket) -> None:
        await handler.handle_connection(websocket)

    return app


def test_plain_chat_message_streams_text_and_creates_session():
    app = build_test_app()
    with TestClient(app).websocket_connect("/ws") as ws:
        ws.send_json({"type": "user_message", "text": "hola"})
        delta = ws.receive_json()
        assert delta == {"type": "recommendation_delta", "delta": "Eco: hola"}
        turn_done = ws.receive_json()
        assert turn_done == {"type": "turn_done"}
        session_created = ws.receive_json()
        assert session_created["type"] == "session_created"
        assert session_created["service_session_id"] == "fake-session-1"


def test_collect_profile_data_pauses_and_resumes_on_submission():
    app = build_test_app()
    with TestClient(app).websocket_connect("/ws") as ws:
        ws.send_json({"type": "user_message", "text": "quiero un curso"})

        requested = ws.receive_json()
        assert requested["type"] == "profile_data_requested"
        assert requested["call_id"] == "call_fake_1"
        assert requested["prefill"]["budget"] == 500.0

        ws.send_json(
            {
                "type": "profile_data_submitted",
                "call_id": "call_fake_1",
                "budget": "650.00",
                "max_duration_weeks": 10,
                "professional_background": "analista de datos",
                "desired_stack": "azure",
            }
        )

        delta = ws.receive_json()
        assert delta == {"type": "recommendation_delta", "delta": "Gracias, confirmado presupuesto 650.0"}
        turn_done = ws.receive_json()
        assert turn_done == {"type": "turn_done"}
        session_created = ws.receive_json()
        assert session_created["type"] == "session_created"


def test_payment_link_created_event_is_sent():
    app = build_test_app()
    with TestClient(app).websocket_connect("/ws") as ws:
        ws.send_json({"type": "user_message", "text": "quiero pagar"})

        payment_event = ws.receive_json()
        assert payment_event["type"] == "payment_link_created"
        assert payment_event["checkout_url"] == "https://www.mercadopago.com/checkout/fake"

        delta = ws.receive_json()
        assert delta["type"] == "recommendation_delta"
        turn_done = ws.receive_json()
        assert turn_done == {"type": "turn_done"}
        session_created = ws.receive_json()
        assert session_created["type"] == "session_created"


def test_session_created_is_resent_every_turn_since_foundry_id_rotates():
    """Found via real E2E verification: Foundry's service_session_id is a per-turn
    response id, not a stable thread id — the client must get the latest value after
    EVERY turn to correctly resume the conversation (business-logic-model.md Section 11)."""
    app = build_test_app()
    with TestClient(app).websocket_connect("/ws") as ws:
        ws.send_json({"type": "user_message", "text": "hola", "service_session_id": "existing-session"})
        ws.receive_json()  # recommendation_delta
        ws.receive_json()  # turn_done
        first_session_created = ws.receive_json()
        assert first_session_created["service_session_id"] == "existing-session"

        ws.send_json({"type": "user_message", "text": "de nuevo"})
        delta = ws.receive_json()
        assert delta["delta"] == "Eco: de nuevo"
        turn_done = ws.receive_json()
        assert turn_done == {"type": "turn_done"}
        second_session_created = ws.receive_json()
        assert second_session_created["type"] == "session_created"


def test_conversation_transcript_is_persisted_for_rehydration():
    repo = FakeConversationMessageRepository()
    app = build_test_app(conversation_message_repository=repo)
    with TestClient(app).websocket_connect("/ws") as ws:
        ws.send_json({"type": "user_message", "text": "hola"})
        ws.receive_json()  # recommendation_delta
        ws.receive_json()  # turn_done
        ws.receive_json()  # session_created

    assert len(repo.messages) == 2
    assert repo.messages[0][1:] == ("user", "hola")
    assert repo.messages[1][1:] == ("bot", "Eco: hola")
    # Both rows share the same (server-generated) conversation_id.
    assert repo.messages[0][0] == repo.messages[1][0]


def test_conversation_id_sent_by_client_is_resumed_not_regenerated():
    repo = FakeConversationMessageRepository()
    app = build_test_app(conversation_message_repository=repo)
    with TestClient(app).websocket_connect("/ws") as ws:
        ws.send_json({"type": "user_message", "text": "hola", "conversation_id": "existing-conv-1"})
        ws.receive_json()  # recommendation_delta
        turn_done = ws.receive_json()
        assert turn_done == {"type": "turn_done"}
        session_created = ws.receive_json()
        assert session_created["conversation_id"] == "existing-conv-1"

    assert all(conv_id == "existing-conv-1" for conv_id, _, _ in repo.messages)


def test_switching_to_a_past_conversation_resumes_its_session_via_store_lookup():
    """The real scenario a "switch conversation" click hits: the client only knows
    conversation_id (no service_session_id — the browser only ever keeps the single
    most-recent one in localStorage), so the server must look up the right Foundry
    thread by conversation_id instead."""
    store = FakeConversationSessionStore({"past-conv-1": "resumed-fake-session"})
    app = build_test_app(conversation_session_store=store)
    with TestClient(app).websocket_connect("/ws") as ws:
        ws.send_json({"type": "user_message", "text": "hola", "conversation_id": "past-conv-1"})
        ws.receive_json()  # recommendation_delta
        ws.receive_json()  # turn_done
        session_created = ws.receive_json()
        assert session_created["service_session_id"] == "resumed-fake-session"
        assert session_created["conversation_id"] == "past-conv-1"


def test_service_session_id_is_saved_to_the_store_after_each_turn():
    store = FakeConversationSessionStore()
    app = build_test_app(conversation_session_store=store)
    with TestClient(app).websocket_connect("/ws") as ws:
        ws.send_json({"type": "user_message", "text": "hola", "conversation_id": "new-conv-1"})
        ws.receive_json()  # recommendation_delta
        ws.receive_json()  # turn_done
        ws.receive_json()  # session_created

    assert store._by_conversation_id["new-conv-1"] == "fake-session-1"


def test_abandoning_widget_then_disconnecting_does_not_crash_and_persists_only_the_user_message():
    """Found via user report: past conversations were left with only the user's message
    and no bot reply. Root cause: disconnecting while collect_profile_data is pending
    (PATTERN-15) cancels its future — asyncio.CancelledError is a BaseException (Python
    3.8+), so it escaped both `except Exception` and the outer
    `except (WebSocketDisconnect, RuntimeError)` as an unhandled ASGI exception."""
    repo = FakeConversationMessageRepository()
    app = build_test_app(conversation_message_repository=repo)
    with TestClient(app).websocket_connect("/ws") as ws:
        ws.send_json({"type": "user_message", "text": "quiero un curso", "conversation_id": "abandoned-1"})
        requested = ws.receive_json()
        assert requested["type"] == "profile_data_requested"
        # Disconnect without ever submitting the widget.

    assert repo.messages == [("abandoned-1", "user", "quiero un curso")]


@pytest.mark.asyncio
async def test_handle_connection_does_not_raise_when_widget_is_abandoned_and_disconnected():
    """Direct reproduction (bypassing TestClient's transport, which doesn't surface the
    crash): cancel_all() cancels the collect_profile_data future while the main loop is
    awaiting it inside agent_client.stream(). asyncio.CancelledError is a BaseException
    (Python 3.8+), so — before the fix — it escaped both `except Exception` and the
    outer `except (WebSocketDisconnect, RuntimeError)`, propagating out of
    handle_connection itself (matches the real "Exception in ASGI application" crash
    seen in production logs)."""
    repo = FakeConversationMessageRepository()
    handler = ChatWebSocketHandler(
        agent_client_factory=FakeChatAgentClient, conversation_message_repository=repo
    )
    ws = FakeWebSocket(
        incoming=[{"type": "user_message", "text": "quiero un curso", "conversation_id": "abandoned-2"}]
    )

    await asyncio.wait_for(handler.handle_connection(ws), timeout=5)

    assert repo.messages == [("abandoned-2", "user", "quiero un curso")]


def test_ws_handler_calls_record_user_message_once_per_user_turn():
    """BR-17b: the engagement floor (5+ user messages -> warm, 10+ -> hot) needs
    ChatAgentClient.record_user_message() invoked once per received user message."""
    created: list[FakeChatAgentClient] = []

    def factory(on_profile_data_requested, pending_tool_calls, conversation_id):
        client = FakeChatAgentClient(on_profile_data_requested, pending_tool_calls, conversation_id)
        created.append(client)
        return client

    app = FastAPI()
    handler = ChatWebSocketHandler(agent_client_factory=factory)

    @app.websocket("/ws")
    async def ws_route(websocket: WebSocket) -> None:
        await handler.handle_connection(websocket)

    with TestClient(app).websocket_connect("/ws") as ws:
        ws.send_json({"type": "user_message", "text": "hola"})
        ws.receive_json()  # recommendation_delta
        ws.receive_json()  # turn_done
        ws.receive_json()  # session_created

        ws.send_json({"type": "user_message", "text": "de nuevo"})
        ws.receive_json()  # recommendation_delta
        ws.receive_json()  # turn_done
        ws.receive_json()  # session_created

    assert len(created) == 1
    assert created[0].record_user_message_calls == 2
