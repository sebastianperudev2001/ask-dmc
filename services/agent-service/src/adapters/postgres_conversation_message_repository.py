"""PostgresConversationMessageRepository — persists the chat transcript so the frontend
can rehydrate visible messages after a page reload (see migrations/003). Same Postgres
instance already used by CourseRepository/LeadRepository — no new server."""
from __future__ import annotations

from src.adapters.connection_pool import ConnectionPool
from src.domain.models import ConversationMessage, ConversationSummary, MessageRole

_APPEND_QUERY = """
    INSERT INTO conversation_messages (conversation_id, role, content) VALUES ($1, $2, $3)
"""

_GET_MESSAGES_QUERY = """
    SELECT role, content, created_at FROM conversation_messages
    WHERE conversation_id = $1
    ORDER BY created_at ASC, id ASC
"""

_LIST_CONVERSATIONS_QUERY = """
    WITH firsts AS (
        SELECT DISTINCT ON (conversation_id) conversation_id, content AS preview, created_at AS started_at
        FROM conversation_messages
        WHERE role = 'user'
        ORDER BY conversation_id, created_at ASC
    ),
    activity AS (
        SELECT conversation_id, MAX(created_at) AS last_activity_at
        FROM conversation_messages
        GROUP BY conversation_id
    )
    SELECT f.conversation_id, f.preview, f.started_at, a.last_activity_at
    FROM firsts f
    JOIN activity a USING (conversation_id)
    ORDER BY a.last_activity_at DESC
"""


class PostgresConversationMessageRepository:
    def __init__(self, connection_pool: ConnectionPool) -> None:
        self._connection_pool = connection_pool

    async def append(self, conversation_id: str, role: MessageRole, content: str) -> None:
        await self._connection_pool.pool.execute(
            _APPEND_QUERY, conversation_id, role.value, content
        )

    async def get_messages(self, conversation_id: str) -> list[ConversationMessage]:
        rows = await self._connection_pool.pool.fetch(_GET_MESSAGES_QUERY, conversation_id)
        return [
            ConversationMessage(
                role=MessageRole(row["role"]), content=row["content"], created_at=row["created_at"]
            )
            for row in rows
        ]

    async def list_conversations(self) -> list[ConversationSummary]:
        rows = await self._connection_pool.pool.fetch(_LIST_CONVERSATIONS_QUERY)
        return [
            ConversationSummary(
                conversation_id=row["conversation_id"],
                preview=row["preview"],
                started_at=row["started_at"],
                last_activity_at=row["last_activity_at"],
            )
            for row in rows
        ]
