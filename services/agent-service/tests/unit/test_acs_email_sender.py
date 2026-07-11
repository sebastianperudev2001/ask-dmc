"""AzureCommunicationServicesEmailSender — EmailClient is patched at construction time
(no real network calls); only the RetryPolicy wiring (PATTERN-21) is under test."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.adapters.acs_email_sender import AzureCommunicationServicesEmailSender
from src.adapters.retry_policy import RetryPolicy

pytestmark = pytest.mark.asyncio


def _build_sender(client: MagicMock) -> AzureCommunicationServicesEmailSender:
    with patch(
        "src.adapters.acs_email_sender.EmailClient.from_connection_string", return_value=client
    ):
        return AzureCommunicationServicesEmailSender(
            "endpoint=https://fake;accesskey=fake",
            sender_address="DoNotReply@fake.azurecomm.net",
            retry_policy=RetryPolicy(max_attempts=3, base_delay_seconds=0.001),
        )


async def test_send_calls_begin_send_with_the_expected_message():
    poller = AsyncMock()
    poller.result = AsyncMock(return_value=None)
    client = MagicMock()
    client.begin_send = AsyncMock(return_value=poller)
    sender = _build_sender(client)

    await sender.send("lead@example.com", "Asunto", "Cuerpo")

    client.begin_send.assert_awaited_once()
    message = client.begin_send.await_args.args[0]
    assert message["recipients"]["to"][0]["address"] == "lead@example.com"
    assert message["content"]["subject"] == "Asunto"


async def test_send_retries_on_failure_then_succeeds():
    poller = AsyncMock()
    poller.result = AsyncMock(return_value=None)
    client = MagicMock()
    client.begin_send = AsyncMock(side_effect=[RuntimeError("transient"), poller])
    sender = _build_sender(client)

    await sender.send("lead@example.com", "Asunto", "Cuerpo")

    assert client.begin_send.await_count == 2


async def test_send_raises_after_exhausting_retries():
    client = MagicMock()
    client.begin_send = AsyncMock(side_effect=RuntimeError("provider down"))
    sender = _build_sender(client)

    with pytest.raises(RuntimeError):
        await sender.send("lead@example.com", "Asunto", "Cuerpo")

    assert client.begin_send.await_count == 3  # RetryPolicy max_attempts
