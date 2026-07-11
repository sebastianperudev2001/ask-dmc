from __future__ import annotations

from typing import Protocol


class EmailSender(Protocol):
    async def send(self, to_email: str, subject: str, body: str) -> None:
        """Proveedor concreto: Azure Communication Services (NFR Requirements Sección 14).
        Envuelto en RetryPolicy por el adaptador (PATTERN-21) — este puerto en sí no
        reintenta."""
        ...
