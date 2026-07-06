from __future__ import annotations

from typing import Protocol

from src.domain.models import Lead


class LeadRepository(Protocol):
    async def save(self, lead: Lead) -> None: ...

    async def find_by_service_session_id(self, service_session_id: str) -> Lead | None: ...

    async def mark_payment_confirmed(self, lead_id: str, *, payment_id: str) -> None: ...
