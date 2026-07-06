"""Tests for SignatureVerifier (PATTERN-17) — valid/invalid webhook signatures."""
from __future__ import annotations

import hashlib
import hmac

from src.adapters.mercadopago_signature import SignatureVerifier

SECRET = "test-secret"


def _sign(data_id: str, x_request_id: str, ts: str, secret: str = SECRET) -> str:
    manifest = f"id:{data_id};request-id:{x_request_id};ts:{ts};"
    v1 = hmac.new(secret.encode(), manifest.encode(), hashlib.sha256).hexdigest()
    return f"ts={ts},v1={v1}"


def test_valid_signature_is_accepted():
    verifier = SignatureVerifier(SECRET)
    x_signature = _sign("12345", "req-1", "1700000000")
    assert verifier.verify(data_id="12345", x_signature=x_signature, x_request_id="req-1") is True


def test_tampered_data_id_is_rejected():
    verifier = SignatureVerifier(SECRET)
    x_signature = _sign("12345", "req-1", "1700000000")
    assert verifier.verify(data_id="99999", x_signature=x_signature, x_request_id="req-1") is False


def test_wrong_secret_is_rejected():
    verifier = SignatureVerifier("different-secret")
    x_signature = _sign("12345", "req-1", "1700000000")
    assert verifier.verify(data_id="12345", x_signature=x_signature, x_request_id="req-1") is False


def test_malformed_signature_header_is_rejected():
    verifier = SignatureVerifier(SECRET)
    assert verifier.verify(data_id="12345", x_signature="garbage", x_request_id="req-1") is False


def test_missing_v1_component_is_rejected():
    verifier = SignatureVerifier(SECRET)
    assert verifier.verify(data_id="12345", x_signature="ts=1700000000", x_request_id="req-1") is False
