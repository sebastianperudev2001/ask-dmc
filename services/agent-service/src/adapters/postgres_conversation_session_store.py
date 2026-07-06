"""PostgresConversationSessionStore — first real use of `conversation_sessions`
(migrations/002; the table existed since incremento 2's original design but no code
ever wrote to it until this feature). `session_id` here holds our stable
`conversation_id` (see ChatAgentClient.__init__ docstring) — the table's original
`session_id`/`service_session_id` split matches exactly what's needed to resolve a
past conversation's Foundry thread when only its conversation_id is known."""
from __future__ import annotations

from src.adapters.connection_pool import ConnectionPool

_UPSERT_QUERY = """
    INSERT INTO conversation_sessions (session_id, service_session_id)
    VALUES ($1, $2)
    ON CONFLICT (session_id) DO UPDATE SET service_session_id = EXCLUDED.service_session_id
"""

_GET_QUERY = "SELECT service_session_id FROM conversation_sessions WHERE session_id = $1"


class PostgresConversationSessionStore:
    def __init__(self, connection_pool: ConnectionPool) -> None:
        self._connection_pool = connection_pool

    async def get_service_session_id(self, conversation_id: str) -> str | None:
        return await self._connection_pool.pool.fetchval(_GET_QUERY, conversation_id)

    async def set_service_session_id(self, conversation_id: str, service_session_id: str) -> None:
        await self._connection_pool.pool.execute(_UPSERT_QUERY, conversation_id, service_session_id)
