"""PostgresLeadRepository — persists Lead/ConversationSession in the same Postgres
instance already used by CourseRepository (no new server, DIV-13). All queries
parameterized (SECURITY-05)."""
from __future__ import annotations

from datetime import datetime, timezone

from src.adapters.connection_pool import ConnectionPool
from src.domain.models import Lead, LeadScore, Motivation

_UPSERT_LEAD_QUERY = """
    INSERT INTO leads (
        id, created_at, name, email, profile_summary, motivation, motivation_detail,
        recommended_programs, payment_link_sent, payment_checkout_url,
        payment_preference_id, payment_confirmed, payment_confirmed_at,
        mercadopago_payment_id, score, score_justification, escalated_to_human,
        service_session_id
    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18)
    ON CONFLICT (id) DO UPDATE SET
        name = EXCLUDED.name,
        email = EXCLUDED.email,
        profile_summary = EXCLUDED.profile_summary,
        motivation = EXCLUDED.motivation,
        motivation_detail = EXCLUDED.motivation_detail,
        recommended_programs = EXCLUDED.recommended_programs,
        payment_link_sent = EXCLUDED.payment_link_sent,
        payment_checkout_url = EXCLUDED.payment_checkout_url,
        payment_preference_id = EXCLUDED.payment_preference_id,
        payment_confirmed = EXCLUDED.payment_confirmed,
        payment_confirmed_at = EXCLUDED.payment_confirmed_at,
        mercadopago_payment_id = EXCLUDED.mercadopago_payment_id,
        score = EXCLUDED.score,
        score_justification = EXCLUDED.score_justification,
        escalated_to_human = EXCLUDED.escalated_to_human,
        service_session_id = EXCLUDED.service_session_id
"""

_FIND_BY_SERVICE_SESSION_ID_QUERY = "SELECT * FROM leads WHERE service_session_id = $1"

_MARK_PAYMENT_CONFIRMED_QUERY = """
    UPDATE leads SET payment_confirmed = TRUE, payment_confirmed_at = $2, mercadopago_payment_id = $3
    WHERE id = $1
"""


class PostgresLeadRepository:
    def __init__(self, connection_pool: ConnectionPool) -> None:
        self._connection_pool = connection_pool

    async def save(self, lead: Lead) -> None:
        await self._connection_pool.pool.execute(
            _UPSERT_LEAD_QUERY,
            lead.id,
            lead.created_at,
            lead.name,
            lead.email,
            lead.profile_summary,
            lead.motivation.value,
            lead.motivation_detail,
            list(lead.recommended_programs),
            lead.payment_link_sent,
            lead.payment_checkout_url,
            lead.payment_preference_id,
            lead.payment_confirmed,
            lead.payment_confirmed_at,
            lead.mercadopago_payment_id,
            lead.score.value,
            lead.score_justification,
            lead.escalated_to_human,
            lead.service_session_id,
        )

    async def find_by_service_session_id(self, service_session_id: str) -> Lead | None:
        row = await self._connection_pool.pool.fetchrow(
            _FIND_BY_SERVICE_SESSION_ID_QUERY, service_session_id
        )
        if row is None:
            return None
        return self._row_to_lead(row)

    async def mark_payment_confirmed(self, lead_id: str, *, payment_id: str) -> None:
        await self._connection_pool.pool.execute(
            _MARK_PAYMENT_CONFIRMED_QUERY, lead_id, datetime.now(timezone.utc), payment_id
        )

    @staticmethod
    def _row_to_lead(row) -> Lead:
        return Lead(
            id=row["id"],
            created_at=row["created_at"],
            name=row["name"],
            email=row["email"],
            profile_summary=row["profile_summary"],
            motivation=Motivation(row["motivation"]),
            motivation_detail=row["motivation_detail"],
            recommended_programs=list(row["recommended_programs"] or []),
            payment_link_sent=row["payment_link_sent"],
            payment_checkout_url=row["payment_checkout_url"],
            payment_preference_id=row["payment_preference_id"],
            payment_confirmed=row["payment_confirmed"],
            payment_confirmed_at=row["payment_confirmed_at"],
            mercadopago_payment_id=row["mercadopago_payment_id"],
            score=LeadScore(row["score"]),
            score_justification=row["score_justification"],
            escalated_to_human=row["escalated_to_human"],
            service_session_id=row["service_session_id"],
        )
