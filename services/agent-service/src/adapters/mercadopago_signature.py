"""SignatureVerifier — PATTERN-17 (nfr-design-patterns.md Incremento 2): validates
Mercado Pago's `x-signature` header (HMAC-SHA256) before any webhook payload is
processed. Manifest format per Mercado Pago's documented webhook signature algorithm:
"id:{data_id};request-id:{x_request_id};ts:{ts};", HMAC-SHA256 hex digest compared
against the `v1` component of `x-signature` (format: "ts=<unix>,v1=<hex>")."""
from __future__ import annotations

import hashlib
import hmac


class SignatureVerifier:
    def __init__(self, secret: str) -> None:
        self._secret = secret

    def verify(self, *, data_id: str, x_signature: str, x_request_id: str) -> bool:
        parts = dict(part.split("=", 1) for part in x_signature.split(",") if "=" in part)
        ts = parts.get("ts")
        v1 = parts.get("v1")
        if not ts or not v1:
            return False

        manifest = f"id:{data_id};request-id:{x_request_id};ts:{ts};"
        computed = hmac.new(
            self._secret.encode("utf-8"), manifest.encode("utf-8"), hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(computed, v1)
