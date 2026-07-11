"""AzureCommunicationServicesEmailSender — the underlying EmailClient is lazily built
(see acs_email_sender.py docstring: ACS_CONNECTION_STRING is empty until the real
resource is provisioned, so eager construction would break local dev entirely). Tests
bypass that lazy-init by injecting a fake client directly via `_get_client`, rather than
patching the real `EmailClient.from_connection_string` — only the RetryPolicy wiring
(PATTERN-21) is under test, never real network calls."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.adapters.acs_email_sender import AzureCommunicationServicesEmailSender
from src.adapters.retry_policy import RetryPolicy

pytestmark = pytest.mark.asyncio


def _build_sender(client: MagicMock) -> AzureCommunicationServicesEmailSender:
    sender = AzureCommunicationServicesEmailSender(
        "endpoint=https://fake;accesskey=fake",
        sender_address="DoNotReply@fake.azurecomm.net",
        retry_policy=RetryPolicy(max_attempts=3, base_delay_seconds=0.001),
    )
    sender._get_client = lambda: client
    return sender


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
