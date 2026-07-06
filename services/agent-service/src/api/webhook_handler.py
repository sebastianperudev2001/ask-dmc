"""MercadoPagoWebhookHandler — `POST /webhooks/mercadopago` (business-logic-model.md
Section 10). Verifies signature (PATTERN-17) before touching any business logic,
re-queries the payment as the authoritative source of truth (BR-20/PATTERN-18) rather
than trusting the webhook payload, and is idempotent against repeated deliveries
(PATTERN-16). Not exposed publicly in this incremento (NFR Requirements) — exercised
via scripts/simulate_mercadopago_webhook.py against localhost."""
from __future__ import annotations

import logging

from fastapi import Request, Response

from src.adapters.mercadopago_client import MercadoPagoPaymentClient
from src.adapters.mercadopago_signature import SignatureVerifier
from src.api.schemas import MercadoPagoWebhookPayload
from src.domain.errors import PaymentServiceUnavailableError
from src.domain.models import PaymentStatus
from src.ports.lead_repository import LeadRepository

logger = logging.getLogger("agent_service.webhook")


class MercadoPagoWebhookHandler:
    def __init__(
        self,
        signature_verifier: SignatureVerifier,
        payment_client: MercadoPagoPaymentClient,
        lead_repository: LeadRepository,
    ) -> None:
        self._signature_verifier = signature_verifier
        self._payment_client = payment_client
        self._lead_repository = lead_repository

    async def handle(self, request: Request) -> Response:
        body = await request.json()

        try:
            payload = MercadoPagoWebhookPayload.model_validate(body)
        except Exception:
            logger.warning("malformed_webhook_payload_rejected")
            return Response(status_code=400)

        if payload.type != "payment":
            return Response(status_code=200)  # not a payment event — ack, nothing to do

        x_signature = request.headers.get("x-signature", "")
        x_request_id = request.headers.get("x-request-id", "")
        if not self._signature_verifier.verify(
            data_id=payload.data.id, x_signature=x_signature, x_request_id=x_request_id
        ):
            logger.warning("invalid_webhook_signature_rejected")
            return Response(status_code=401)

        try:
            details = await self._payment_client.get_payment(payload.data.id)
        except PaymentServiceUnavailableError:
            logger.warning("payment_lookup_failed_returning_502_for_retry")
            return Response(status_code=502)  # Mercado Pago will retry the delivery

        if details.external_reference is None:
            logger.warning("webhook_payment_missing_external_reference")
            return Response(status_code=200)

        lead = await self._lead_repository.find_by_service_session_id(details.external_reference)
        if lead is None:
            logger.warning("webhook_payment_lead_not_found")
            return Response(status_code=200)

        if lead.payment_confirmed:
            return Response(status_code=200)  # PATTERN-16: idempotent, already processed

        if details.status == PaymentStatus.APPROVED:
            await self._lead_repository.mark_payment_confirmed(lead.id, payment_id=payload.data.id)

        return Response(status_code=200)
