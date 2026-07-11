"""LeadEventPublisher — bus pub/sub en memoria, de un solo proceso (PATTERN-25 exige
instancia única para que esto funcione correctamente). `publish` es async y espera a
cada subscriber en secuencia — los subscribers que no deben bloquear al publisher (ej.
OutreachAgentService, PATTERN-23) son responsables de agendar su propio trabajo pesado
como una tarea en background y retornar rápido."""
from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

from src.domain.models import LeadEvent

logger = logging.getLogger("agent_service.lead_event_publisher")

LeadEventHandler = Callable[[LeadEvent], Awaitable[None]]


class LeadEventPublisher:
    def __init__(self) -> None:
        self._subscribers: list[LeadEventHandler] = []

    def subscribe(self, handler: LeadEventHandler) -> None:
        self._subscribers.append(handler)

    async def publish(self, event: LeadEvent) -> None:
        for handler in self._subscribers:
            try:
                await handler(event)
            except Exception:  # noqa: BLE001 - one subscriber's failure must not block others
                logger.exception("lead_event_subscriber_failed", extra={"event_type": event.event_type})
