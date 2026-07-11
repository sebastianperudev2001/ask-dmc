"""PostgresDraftRepository — persiste OutreachDraft en la misma instancia Postgres ya
usada por CourseRepository/LeadRepository (sin servidor nuevo). `mark_sent` es el guard
atómico de PATTERN-28: solo actualiza (y retorna) la fila si seguía en `pending` en el
momento del UPDATE — una segunda llamada concurrente/duplicada es un no-op."""
from __future__ import annotations

from datetime import datetime, timezone

from src.adapters.connection_pool import ConnectionPool
from src.domain.models import DraftStatus, DraftTrigger, OutreachDraft

_INSERT_DRAFT_QUERY = """
    INSERT INTO outreach_drafts (
        draft_id, lead_id, subject, body, status, trigger, created_at, sent_at
    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
    ON CONFLICT (draft_id) DO UPDATE SET
        subject = EXCLUDED.subject,
        body = EXCLUDED.body,
        status = EXCLUDED.status,
        sent_at = EXCLUDED.sent_at
"""

_FIND_ACTIVE_BY_LEAD_ID_QUERY = (
    "SELECT * FROM outreach_drafts WHERE lead_id = $1 AND status = 'pending' LIMIT 1"
)

_FIND_BY_ID_QUERY = "SELECT * FROM outreach_drafts WHERE draft_id = $1"

_MARK_SENT_QUERY = """
    UPDATE outreach_drafts SET status = 'sent', sent_at = $2
    WHERE draft_id = $1 AND status = 'pending'
    RETURNING *
"""

_MARK_DISCARDED_QUERY = """
    UPDATE outreach_drafts SET status = 'discarded'
    WHERE draft_id = $1
    RETURNING *
"""


class PostgresDraftRepository:
    def __init__(self, connection_pool: ConnectionPool) -> None:
        self._connection_pool = connection_pool

    async def save(self, draft: OutreachDraft) -> None:
        await self._connection_pool.pool.execute(
            _INSERT_DRAFT_QUERY,
            draft.draft_id,
            draft.lead_id,
            draft.subject,
            draft.body,
            draft.status.value,
            draft.trigger.value,
            draft.created_at,
            draft.sent_at,
        )

    async def find_active_by_lead_id(self, lead_id: str) -> OutreachDraft | None:
        row = await self._connection_pool.pool.fetchrow(_FIND_ACTIVE_BY_LEAD_ID_QUERY, lead_id)
        if row is None:
            return None
        return self._row_to_draft(row)

    async def find_by_id(self, draft_id: str) -> OutreachDraft | None:
        row = await self._connection_pool.pool.fetchrow(_FIND_BY_ID_QUERY, draft_id)
        if row is None:
            return None
        return self._row_to_draft(row)

    async def mark_sent(self, draft_id: str) -> OutreachDraft | None:
        row = await self._connection_pool.pool.fetchrow(
            _MARK_SENT_QUERY, draft_id, datetime.now(timezone.utc)
        )
        if row is None:
            return None
        return self._row_to_draft(row)

    async def mark_discarded(self, draft_id: str) -> OutreachDraft | None:
        row = await self._connection_pool.pool.fetchrow(_MARK_DISCARDED_QUERY, draft_id)
        if row is None:
            return None
        return self._row_to_draft(row)

    @staticmethod
    def _row_to_draft(row) -> OutreachDraft:
        return OutreachDraft(
            draft_id=row["draft_id"],
            lead_id=row["lead_id"],
            subject=row["subject"],
            body=row["body"],
            status=DraftStatus(row["status"]),
            trigger=DraftTrigger(row["trigger"]),
            created_at=row["created_at"],
            sent_at=row["sent_at"],
        )
