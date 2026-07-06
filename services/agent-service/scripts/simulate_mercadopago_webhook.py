"""Simulates a Mercado Pago webhook delivery against localhost — NFR Requirements
(Incremento 2) decided against exposing the webhook publicly in this increment.

Pass a REAL sandbox payment_id (obtained by completing a test payment via a
checkout_url printed by manual_chat_check.py) to exercise the full
signature-verification + re-query + lead-confirmation flow end-to-end. Without a real
payment_id, this still verifies that a correctly-signed request reaches the handler
(the re-query to Mercado Pago will then fail for a nonexistent id — that failure path
is expected, not a bug in the script).

Usage: uv run python -m scripts.simulate_mercadopago_webhook [payment_id]
"""
import hashlib
import hmac
import os
import sys
import time

import httpx
from dotenv import load_dotenv

load_dotenv()

WEBHOOK_URL = "http://localhost:8000/webhooks/mercadopago"


def sign(secret: str, data_id: str, x_request_id: str, ts: str) -> str:
    manifest = f"id:{data_id};request-id:{x_request_id};ts:{ts};"
    v1 = hmac.new(secret.encode(), manifest.encode(), hashlib.sha256).hexdigest()
    return f"ts={ts},v1={v1}"


def main() -> None:
    payment_id = sys.argv[1] if len(sys.argv) > 1 else "123456789"
    secret = os.environ["MERCADOPAGO_WEBHOOK_SECRET"]
    x_request_id = "manual-simulation"
    ts = str(int(time.time()))
    x_signature = sign(secret, payment_id, x_request_id, ts)

    body = {"type": "payment", "data": {"id": payment_id}}
    response = httpx.post(
        WEBHOOK_URL,
        json=body,
        headers={"x-signature": x_signature, "x-request-id": x_request_id},
        timeout=15.0,
    )
    print(f"status={response.status_code}")
    print(response.text)


if __name__ == "__main__":
    main()
