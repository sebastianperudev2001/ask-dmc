"""LeadBroadcaster — gestiona las conexiones `/ws/leads` activas. A diferencia de
`/ws/chat` (bidireccional), este canal es solo de push: el servidor transmite
snapshots/eventos, el cliente no envía mensajes de aplicación. PATTERN-24: detección
perezosa de conexiones muertas (sin heartbeat) — una conexión caída se descubre recién
en el próximo intento de `broadcast()` fallido. Instancia única de proceso (PATTERN-25 lo
exige — un evento publicado en una réplica nunca llegaría a un cliente de otra)."""
from __future__ import annotations

import logging

from fastapi import WebSocket, WebSocketDisconnect

from src.api.schemas import LeadEventOut, LeadOut, LeadsSnapshotOut
from src.domain.lead_query_service import LeadQueryService
from src.domain.models import LeadEvent

logger = logging.getLogger("agent_service.lead_broadcaster")


class LeadBroadcaster:
    def __init__(self, lead_query_service: LeadQueryService) -> None:
        self._lead_query_service = lead_query_service
        self._connections: list[WebSocket] = []

    async def handle_connection(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.append(websocket)
        try:
            leads = await self._lead_query_service.list_leads()
            snapshot = LeadsSnapshotOut(leads=[LeadOut.from_lead(lead) for lead in leads])
            await websocket.send_json(snapshot.model_dump(mode="json"))

            # Push-only channel (no user_message-style input expected) — still need to
            # block on something to notice a disconnect; receive_text() raises
            # WebSocketDisconnect when the client closes the connection.
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            logger.info("leads_websocket_disconnected")
        finally:
            if websocket in self._connections:
                self._connections.remove(websocket)

    async def broadcast(self, event: LeadEvent) -> None:
        message = LeadEventOut(
            event_type=event.event_type, lead=LeadOut.from_lead(event.lead)
        ).model_dump(mode="json")
        dead: list[WebSocket] = []
        for connection in self._connections:
            try:
                await connection.send_json(message)
            except Exception:  # noqa: BLE001 - PATTERN-24: lazy dead-connection detection
                dead.append(connection)
        for connection in dead:
            if connection in self._connections:
                self._connections.remove(connection)
