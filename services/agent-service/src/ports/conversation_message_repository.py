from __future__ import annotations

from typing import Protocol

from src.domain.models import ConversationMessage, ConversationSummary, MessageRole


class ConversationMessageRepository(Protocol):
    async def append(self, conversation_id: str, role: MessageRole, content: str) -> None: ...

    async def get_messages(self, conversation_id: str) -> list[ConversationMessage]: ...

    async def list_conversations(self) -> list[ConversationSummary]:
        """Real conversation history — replaces the frontend's hardcoded mock Sidebar
        list. Ordered most-recent-first."""
        ...
