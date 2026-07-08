"""Integration tests for MercadoPagoWebhookHandler — signature verification (PATTERN-17),
re-query as source of truth (BR-20/PATTERN-18), and idempotency (PATTERN-16)."""
from __future__ import annotations

import hashlib
import hmac
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from src.adapters.mercadopago_client import PaymentDetails
from src.adapters.mercadopago_signature import SignatureVerifier
from src.api.webhook_handler import MercadoPagoWebhookHandler
from src.domain.models import Lead, LeadScore, Motivation, PaymentStatus
from tests.integration.fakes import FakeLeadRepository, FakePaymentClient

SECRET = "test-webhook-secret"


def _sign(data_id: str, x_request_id: str, ts: str) -> str:
    manifest = f"id:{data_id};request-id:{x_request_id};ts:{ts};"
    v1 = hmac.new(SECRET.encode(), manifest.encode(), hashlib.sha256).hexdigest()
    return f"ts={ts},v1={v1}"


def _lead(service_session_id: str, payment_confirmed: bool = False) -> Lead:
    return Lead(
        id=f"lead-{service_session_id}",
        created_at=datetime.now(timezone.utc),
        motivation=Motivation.GROWTH,
        score=LeadScore.WARM,
        service_session_id=service_session_id,
        payment_confirmed=payment_confirmed,
    )


def build_test_app(lead_repository, payment_client) -> FastAPI:
    app = FastAPI()
    handler = MercadoPagoWebhookHandler(
        signature_verifier=SignatureVerifier(SECRET),
        payment_client=payment_client,
        lead_repository=lead_repository,
    )

    @app.post("/webhooks/mercadopago")
    async def webhook_route(request: Request):
        return await handler.handle(request)

    return app


def test_valid_webhook_confirms_approved_payment():
    lead_repo = FakeLeadRepository([_lead("sess-1")])
    payment_client = FakePaymentClient(
        {"pay-1": PaymentDetails(status=PaymentStatus.APPROVED, external_reference="sess-1")}
    )
    app = build_test_app(lead_repo, payment_client)

    body = {"type": "payment", "data": {"id": "pay-1"}}
    x_signature = _sign("pay-1", "req-1", "1700000000")

    response = TestClient(app).post(
        "/webhooks/mercadopago",
        json=body,
        headers={"x-signature": x_signature, "x-request-id": "req-1"},
    )

    assert response.status_code == 200
    lead = lead_repo._leads["sess-1"]
    assert lead.payment_confirmed is True
    assert lead.mercadopago_payment_id == "pay-1"


def test_invalid_signature_is_rejected():
    lead_repo = FakeLeadRepository([_lead("sess-1")])
    payment_client = FakePaymentClient({})
    app = build_test_app(lead_repo, payment_client)

    body = {"type": "payment", "data": {"id": "pay-1"}}

    response = TestClient(app).post(
        "/webhooks/mercadopago",
        json=body,
        headers={"x-signature": "ts=1,v1=deadbeef", "x-request-id": "req-1"},
    )

    assert response.status_code == 401
    assert lead_repo._leads["sess-1"].payment_confirmed is False


def test_repeated_webhook_for_already_confirmed_payment_is_idempotent():
    lead_repo = FakeLeadRepository([_lead("sess-1", payment_confirmed=True)])
    payment_client = FakePaymentClient(
        {"pay-1": PaymentDetails(status=PaymentStatus.APPROVED, external_reference="sess-1")}
    )
    app = build_test_app(lead_repo, payment_client)

    body = {"type": "payment", "data": {"id": "pay-1"}}
    x_signature = _sign("pay-1", "req-1", "1700000000")

    response = TestClient(app).post(
        "/webhooks/mercadopago",
        json=body,
        headers={"x-signature": x_signature, "x-request-id": "req-1"},
    )

    assert response.status_code == 200  # PATTERN-16: acked without reprocessing


def test_non_payment_event_type_is_acknowledged_without_processing():
    lead_repo = FakeLeadRepository([_lead("sess-1")])
    payment_client = FakePaymentClient({})
    app = build_test_app(lead_repo, payment_client)

    response = TestClient(app).post(
        "/webhooks/mercadopago",
        json={"type": "subscription_preapproval", "data": {"id": "sub-1"}},
        headers={"x-signature": "ts=1,v1=irrelevant", "x-request-id": "req-1"},
    )

    assert response.status_code == 200
    assert lead_repo._leads["sess-1"].payment_confirmed is False
