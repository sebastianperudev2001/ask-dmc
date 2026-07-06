"""MercadoPagoPaymentClient — Checkout Pro integration (PATTERN-14: retry via
RetryPolicy, same policy as PATTERN-01). `create_preference` returns a ready-to-use
hosted checkout URL (`init_point`/`sandbox_init_point`) — no custom checkout page
needed (DIV-11, replaces the Culqi Orders-API approach evaluated and discarded).
`get_payment` is the authoritative source of truth after a webhook (BR-20/PATTERN-18)
— the webhook payload itself is never trusted alone."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

import httpx

from src.adapters.retry_policy import RetryPolicy
from src.domain.errors import PaymentServiceUnavailableError
from src.domain.models import PaymentOrder, PaymentStatus

_DEFAULT_BASE_URL = "https://api.mercadopago.com"

_STATUS_MAP: dict[str, PaymentStatus] = {
    "approved": PaymentStatus.APPROVED,
    "rejected": PaymentStatus.REJECTED,
}


@dataclass(frozen=True)
class PaymentDetails:
    """Result of get_payment — `external_reference` (set to the ConversationSession's
    service_session_id when the preference was created) is how the webhook handler
    correlates a payment notification back to a Lead, since Mercado Pago's payment id
    is not the same as our preference_id."""

    status: PaymentStatus
    external_reference: str | None


class MercadoPagoPaymentClient:
    def __init__(
        self,
        access_token: str,
        retry_policy: RetryPolicy,
        base_url: str = _DEFAULT_BASE_URL,
    ) -> None:
        self._access_token = access_token
        self._retry_policy = retry_policy
        self._base_url = base_url

    async def create_preference(
        self,
        amount: Decimal,
        description: str,
        client_details: dict | None = None,
        external_reference: str | None = None,
    ) -> PaymentOrder:
        async def _create() -> PaymentOrder:
            async with httpx.AsyncClient(base_url=self._base_url, timeout=10.0) as client:
                payload: dict = {
                    "items": [
                        {
                            "title": description,
                            "quantity": 1,
                            "unit_price": float(amount),
                            "currency_id": "PEN",
                        }
                    ],
                }
                if client_details:
                    payload["payer"] = client_details
                if external_reference:
                    payload["external_reference"] = external_reference
                response = await client.post(
                    "/checkout/preferences",
                    headers={"Authorization": f"Bearer {self._access_token}"},
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()

            checkout_url = data.get("sandbox_init_point") or data["init_point"]
            return PaymentOrder(
                preference_id=data["id"],
                checkout_url=checkout_url,
                amount=amount,
                description=description,
            )

        try:
            return await self._retry_policy.run(_create)
        except Exception as exc:  # noqa: BLE001 - mapped to a domain error (BR-18)
            raise PaymentServiceUnavailableError(str(exc)) from exc

    async def get_payment(self, payment_id: str) -> PaymentDetails:
        async def _get() -> PaymentDetails:
            async with httpx.AsyncClient(base_url=self._base_url, timeout=10.0) as client:
                response = await client.get(
                    f"/v1/payments/{payment_id}",
                    headers={"Authorization": f"Bearer {self._access_token}"},
                )
                response.raise_for_status()
                data = response.json()
            status = _STATUS_MAP.get(data.get("status", ""), PaymentStatus.PENDING)
            return PaymentDetails(status=status, external_reference=data.get("external_reference"))

        try:
            return await self._retry_policy.run(_get)
        except Exception as exc:  # noqa: BLE001
            raise PaymentServiceUnavailableError(str(exc)) from exc
