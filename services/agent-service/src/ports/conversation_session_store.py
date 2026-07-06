from __future__ import annotations

from typing import Protocol


class ConversationSessionStore(Protocol):
    """PATTERN-20 (nfr-design logical-components.md): resolves which Foundry
    service_session_id to resume for a given conversation_id — needed when the client
    only knows the conversation_id (e.g. picking a past conversation from the real
    history list) but not its Foundry session id, since the browser only ever keeps the
    single most-recent one in localStorage."""

    async def get_service_session_id(self, conversation_id: str) -> str | None: ...

    async def set_service_session_id(self, conversation_id: str, service_session_id: str) -> None: ...
