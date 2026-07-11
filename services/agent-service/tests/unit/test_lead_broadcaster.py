"""LeadBroadcaster tests — FakeWebSocket gives deterministic control over disconnect
timing without a real ASGI transport, same technique already used for
test_chat_websocket_flow.py's FakeWebSocket."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi import WebSocketDisconnect

from src.api.lead_broadcaster import LeadBroadcaster
from src.domain.lead_query_service import LeadQueryService
from src.domain.models import Lead, LeadEvent

pytestmark = pytest.mark.asyncio


class FakeWebSocket:
    def __init__(self, *, fail_on_send: bool = False) -> None:
        self.sent: list[dict] = []
        self._fail_on_send = fail_on_send

    async def accept(self) -> None:
        pass

    async def receive_text(self) -> str:
        raise WebSocketDisconnect()

    async def send_json(self, data: dict) -> None:
        if self._fail_on_send:
            raise RuntimeError("connection closed")
        self.sent.append(data)


class FakeLeadRepository:
    def __init__(self, leads: list[Lead]) -> None:
        self._leads = leads

    async def list_leads(self) -> list[Lead]:
        return self._leads


def _lead(lead_id: str = "lead-1") -> Lead:
    return Lead(id=lead_id, created_at=datetime.now(timezone.utc))


async def test_handle_connection_sends_a_snapshot_on_connect():
    broadcaster = LeadBroadcaster(LeadQueryService(FakeLeadRepository([_lead()])))
    websocket = FakeWebSocket()

    await broadcaster.handle_connection(websocket)

    assert websocket.sent[0]["type"] == "snapshot"
    assert websocket.sent[0]["leads"][0]["id"] == "lead-1"


async def test_broadcast_sends_lead_event_to_connected_clients():
    broadcaster = LeadBroadcaster(LeadQueryService(FakeLeadRepository([])))
    websocket = FakeWebSocket()
    broadcaster._connections.append(websocket)  # bypass handle_connection's blocking loop

    await broadcaster.broadcast(LeadEvent(event_type="created", lead=_lead()))

    assert websocket.sent[0]["type"] == "lead_event"
    assert websocket.sent[0]["event_type"] == "created"


async def test_broadcast_drops_a_connection_whose_send_fails():
    broadcaster = LeadBroadcaster(LeadQueryService(FakeLeadRepository([])))
    dead = FakeWebSocket(fail_on_send=True)
    alive = FakeWebSocket()
    broadcaster._connections.extend([dead, alive])

    await broadcaster.broadcast(LeadEvent(event_type="created", lead=_lead()))

    assert dead not in broadcaster._connections
    assert alive in broadcaster._connections
    assert len(alive.sent) == 1
