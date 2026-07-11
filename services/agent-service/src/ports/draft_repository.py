from __future__ import annotations

from typing import Protocol

from src.domain.models import OutreachDraft


class DraftRepository(Protocol):
    async def save(self, draft: OutreachDraft) -> None: ...

    async def find_active_by_lead_id(self, lead_id: str) -> OutreachDraft | None:
        """BR-22/BR-23: 'activo' = status == PENDING. Usado tanto por el dedupe de
        generate_draft como por DraftPanel al abrir el popup de un lead."""
        ...

    async def find_by_id(self, draft_id: str) -> OutreachDraft | None: ...

    async def mark_sent(self, draft_id: str) -> OutreachDraft | None:
        """PATTERN-28: UPDATE atómico condicionado a status == PENDING. Retorna el
        draft actualizado si la fila estaba pending, o None si ya no lo estaba (envío
        duplicado/concurrente — no-op, no se reintenta el envío)."""
        ...

    async def mark_discarded(self, draft_id: str) -> OutreachDraft | None: ...
