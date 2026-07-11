from __future__ import annotations

from typing import Protocol

from src.domain.models import Lead


class LeadRepository(Protocol):
    async def save(self, lead: Lead) -> None: ...

    async def find_by_service_session_id(self, service_session_id: str) -> Lead | None: ...

    async def mark_payment_confirmed(self, lead_id: str, *, payment_id: str) -> None: ...

    # ── Incremento 3 — BackOffice ──

    async def list_leads(self) -> list[Lead]:
        """Read path for GET /leads (FR-7) — sin filtros/paginación (NFR-4, escala demo)."""
        ...

    async def find_by_id(self, lead_id: str) -> Lead | None:
        """Interno — usado por OutreachAgentService para resolver un lead individual.
        No expuesto vía API (Application Design, Q5 = B: sin GET /leads/{id} público)."""
        ...
