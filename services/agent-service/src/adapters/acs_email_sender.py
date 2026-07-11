"""AzureCommunicationServicesEmailSender — EmailSender adapter (NFR Requirements Sección
14, Tech Stack Decisions Incremento 3). Envuelto en RetryPolicy (PATTERN-21) antes de
propagar un fallo definitivo — a diferencia deliberada de la llamada LLM de
OutreachAgentService (PATTERN-22, sin retry). Exact SDK surface (`begin_send`/poller
shape) should be re-verified against the installed `azure-communication-email` version
at integration time — same caveat already left for FOUNDRY_PROJECT_ENDPOINT in main.tf,
Azure SDK surfaces sometimes shift between versions."""
from __future__ import annotations

from azure.communication.email.aio import EmailClient

from src.adapters.retry_policy import RetryPolicy


class AzureCommunicationServicesEmailSender:
    def __init__(
        self, connection_string: str, *, sender_address: str, retry_policy: RetryPolicy
    ) -> None:
        self._client = EmailClient.from_connection_string(connection_string)
        self._sender_address = sender_address
        self._retry_policy = retry_policy

    async def send(self, to_email: str, subject: str, body: str) -> None:
        message = {
            "senderAddress": self._sender_address,
            "recipients": {"to": [{"address": to_email}]},
            "content": {"subject": subject, "plainText": body},
        }

        async def _send() -> None:
            poller = await self._client.begin_send(message)
            await poller.result()

        await self._retry_policy.run(_send)
