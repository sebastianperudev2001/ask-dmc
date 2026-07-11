"""Integration tests for LeadBroadcaster/LeadEventPublisher — snapshot-then-stream over
a real FastAPI TestClient WebSocket connection (FR-6/FR-8, Story 3)."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from fastapi import FastAPI, WebSocket
from fastapi.testclient import TestClient

from src.api.lead_broadcaster import LeadBroadcaster
from src.domain.lead_event_publisher import LeadEventPublisher
from src.domain.lead_query_service import LeadQueryService
from src.domain.models import Lead, LeadEvent
from tests.integration.fakes import FakeLeadRepository


def build_test_app(lead_repository, lead_event_publisher) -> FastAPI:
    app = FastAPI()
    broadcaster = LeadBroadcaster(LeadQueryService(lead_repository))
    lead_event_publisher.subscribe(broadcaster.broadcast)

    @app.websocket("/ws/leads")
    async def ws_route(websocket: WebSocket) -> None:
        await broadcaster.handle_connection(websocket)

    return app


def _lead(lead_id: str = "lead-1") -> Lead:
    return Lead(id=lead_id, created_at=datetime.now(timezone.utc), service_session_id=lead_id)


def test_connect_receives_a_snapshot_of_existing_leads():
    lead_repository = FakeLeadRepository([_lead("lead-1")])
    publisher = LeadEventPublisher()
    app = build_test_app(lead_repository, publisher)

    with TestClient(app).websocket_connect("/ws/leads") as ws:
        snapshot = ws.receive_json()

    assert snapshot["type"] == "snapshot"
    assert snapshot["leads"][0]["id"] == "lead-1"


def test_new_connection_gets_an_empty_snapshot_when_no_leads_exist():
    lead_repository = FakeLeadRepository([])
    publisher = LeadEventPublisher()
    app = build_test_app(lead_repository, publisher)

    with TestClient(app).websocket_connect("/ws/leads") as ws:
        snapshot = ws.receive_json()

    assert snapshot == {"type": "snapshot", "leads": []}


def test_a_published_event_is_broadcast_to_a_connected_client():
    lead_repository = FakeLeadRepository([])
    publisher = LeadEventPublisher()
    app = build_test_app(lead_repository, publisher)

    with TestClient(app).websocket_connect("/ws/leads") as ws:
        ws.receive_json()  # initial (empty) snapshot

        asyncio.run(publisher.publish(LeadEvent(event_type="created", lead=_lead("lead-2"))))

        event = ws.receive_json()

    assert event["type"] == "lead_event"
    assert event["event_type"] == "created"
    assert event["lead"]["id"] == "lead-2"


def test_disconnecting_one_client_does_not_break_broadcast_to_others():
    lead_repository = FakeLeadRepository([])
    publisher = LeadEventPublisher()
    app = build_test_app(lead_repository, publisher)
    client = TestClient(app)

    with client.websocket_connect("/ws/leads") as ws_a:
        ws_a.receive_json()
        with client.websocket_connect("/ws/leads") as ws_b:
            ws_b.receive_json()
            # ws_a disconnects here (context manager exit is deferred to outer scope,
            # but TestClient's close happens synchronously on `__exit__` — simulate by
            # closing explicitly before publishing).

        asyncio.run(publisher.publish(LeadEvent(event_type="created", lead=_lead("lead-3"))))
        event = ws_a.receive_json()

    assert event["type"] == "lead_event"
    assert event["lead"]["id"] == "lead-3"
