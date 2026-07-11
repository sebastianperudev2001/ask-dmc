"""LeadQueryService — orquesta el read path de FR-7. Sin lógica propia más allá del
paso a través: no hay `get_lead(id)` a nivel de API pública (Application Design, Q5 = B)."""
from __future__ import annotations

from src.domain.models import Lead
from src.ports.lead_repository import LeadRepository


class LeadQueryService:
    def __init__(self, lead_repository: LeadRepository) -> None:
        self._lead_repository = lead_repository

    async def list_leads(self) -> list[Lead]:
        return await self._lead_repository.list_leads()
