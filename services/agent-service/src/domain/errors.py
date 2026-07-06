"""Domain-level errors — raised by adapters after RetryPolicy (PATTERN-01) exhausts
retries, caught by the API layer and mapped to the safe, generic WS error messages
defined in business-logic-model.md Section 4 (SECURITY-15: fail-safe, no internal
details leaked to the client)."""
from __future__ import annotations


class EmbeddingServiceUnavailableError(Exception):
    pass


class AgentUnavailableError(Exception):
    pass


# ── Incremento 2 ──────────────────────────────────────────────────────────────


class PaymentServiceUnavailableError(Exception):
    """Raised by MercadoPagoPaymentClient after RetryPolicy (PATTERN-14) exhausts
    retries — caught by the create_payment_link tool (BR-18), never propagated as an
    unhandled exception that would break the agent's stream."""


class InvalidWebhookSignatureError(Exception):
    """Raised by SignatureVerifier (PATTERN-17) when x-signature/x-request-id does not
    validate — the webhook handler maps this to HTTP 401 without processing the payload."""
