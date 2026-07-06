"""PATTERN-15 (nfr-design-patterns.md Incremento 2): registry of in-flight "human in
the loop" tool calls (currently only collect_profile_data). Anchored to a single WS
connection's lifetime — no distributed state (same principle as PATTERN-05)."""
from __future__ import annotations

import asyncio
from typing import Any


class PendingToolCallRegistry:
    def __init__(self) -> None:
        self._pending: dict[str, asyncio.Future[Any]] = {}

    def create(self, call_id: str) -> asyncio.Future[Any]:
        future: asyncio.Future[Any] = asyncio.get_event_loop().create_future()
        self._pending[call_id] = future
        return future

    def resolve(self, call_id: str, result: Any) -> bool:
        """Returns False if no pending future exists for call_id (e.g. late/duplicate
        message) — caller decides whether that's worth logging."""
        future = self._pending.pop(call_id, None)
        if future is None or future.done():
            return False
        future.set_result(result)
        return True

    def cancel_all(self) -> None:
        """Called on WS disconnect — no explicit timeout (Clarification NFR Q1 = C),
        the connection closing is the only lifecycle boundary."""
        for future in self._pending.values():
            if not future.done():
                future.cancel()
        self._pending.clear()
