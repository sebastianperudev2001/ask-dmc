"""PATTERN-01 (NFR Design): retry with exponential backoff + jitter, max 3 attempts by
default. No circuit breaker in this increment (explicit user decision)."""
from __future__ import annotations

import asyncio
import logging
import random
from typing import Awaitable, Callable, TypeVar

T = TypeVar("T")

logger = logging.getLogger("agent_service.retry_policy")


class RetryPolicy:
    def __init__(self, max_attempts: int = 3, base_delay_seconds: float = 0.5) -> None:
        self._max_attempts = max_attempts
        self._base_delay_seconds = base_delay_seconds

    async def run(self, operation: Callable[[], Awaitable[T]]) -> T:
        last_error: Exception | None = None
        for attempt in range(1, self._max_attempts + 1):
            try:
                return await operation()
            except Exception as exc:  # noqa: BLE001 - re-raised after exhausting retries
                last_error = exc
                if attempt == self._max_attempts:
                    break
                delay = self._base_delay_seconds * (2 ** (attempt - 1))
                delay += random.uniform(0, delay * 0.1)  # jitter
                logger.warning(
                    "retry_attempt_failed",
                    extra={"attempt": attempt, "delay_seconds": delay},
                )
                await asyncio.sleep(delay)
        assert last_error is not None
        raise last_error
