from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.domain.lead_event_publisher import LeadEventPublisher
from src.domain.models import Lead, LeadEvent

pytestmark = pytest.mark.asyncio


def _event(event_type: str = "created") -> LeadEvent:
    return LeadEvent(
        event_type=event_type,
        lead=Lead(id="lead-1", created_at=datetime.now(timezone.utc)),
    )


async def test_publish_fans_out_to_all_subscribers():
    publisher = LeadEventPublisher()
    received: list[LeadEvent] = []

    async def handler_a(event: LeadEvent) -> None:
        received.append(event)

    async def handler_b(event: LeadEvent) -> None:
        received.append(event)

    publisher.subscribe(handler_a)
    publisher.subscribe(handler_b)

    event = _event()
    await publisher.publish(event)

    assert received == [event, event]


async def test_publish_does_not_call_unsubscribed_handlers():
    publisher = LeadEventPublisher()
    received: list[LeadEvent] = []

    async def handler(event: LeadEvent) -> None:
        received.append(event)

    publisher.subscribe(handler)
    await publisher.publish(_event())

    assert len(received) == 1


async def test_a_failing_subscriber_does_not_block_delivery_to_others():
    publisher = LeadEventPublisher()
    received: list[LeadEvent] = []

    async def failing_handler(event: LeadEvent) -> None:
        raise RuntimeError("boom")

    async def healthy_handler(event: LeadEvent) -> None:
        received.append(event)

    publisher.subscribe(failing_handler)
    publisher.subscribe(healthy_handler)

    await publisher.publish(_event())

    assert len(received) == 1
