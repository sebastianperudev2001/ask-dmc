"""WebSocketConnectionHandler — see business-logic-model.md Section 2 (the full
recommendation flow) and Section 3 (message contract). SECURITY-08 exception: this
endpoint is intentionally public/unauthenticated (anonymous chat widget visitors)."""
from __future__ import annotations

import asyncio
import logging

from fastapi import WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from src.api.schemas import (
    CandidateSummary,
    NoExactMatchShowingAllMessage,
    NoRecommendationMessage,
    RecommendationDeltaMessage,
    RecommendationDoneMessage,
    RecommendationRequestMessage,
    RelaxFiltersOfferMessage,
    RelaxFiltersResponseMessage,
)
from src.domain.errors import AgentUnavailableError, EmbeddingServiceUnavailableError
from src.domain.models import ProfileQuery, RecommendationBranch
from src.domain.orchestrator import RecommendationOrchestrator, RecommendationStart
from src.ports.embedding_service import EmbeddingService
from src.ports.recommendation_agent_client import RecommendationAgentClient

logger = logging.getLogger("agent_service.websocket")


class WebSocketConnectionHandler:
    def __init__(
        self,
        orchestrator: RecommendationOrchestrator,
        embedding_service: EmbeddingService,
        agent_client: RecommendationAgentClient,
        relax_confirmation_timeout_seconds: float,
    ) -> None:
        self._orchestrator = orchestrator
        self._embedding_service = embedding_service
        self._agent_client = agent_client
        self._relax_confirmation_timeout_seconds = relax_confirmation_timeout_seconds

    async def handle_connection(self, websocket: WebSocket) -> None:
        await websocket.accept()
        try:
            while True:
                raw_message = await websocket.receive_json()
                await self._handle_recommendation_request(websocket, raw_message)
        except WebSocketDisconnect:
            logger.info("websocket_disconnected")
        except Exception:
            # SECURITY-15: global fail-safe — never leak internal details to the client.
            logger.exception("unhandled_error_in_websocket_connection")

    async def _handle_recommendation_request(self, websocket: WebSocket, raw_message: dict) -> None:
        try:
            request_message = RecommendationRequestMessage.model_validate(raw_message)
        except ValidationError:
            await websocket.send_json(
                NoRecommendationMessage(reason="invalid_request").model_dump(mode="json")
            )
            return

        request = request_message.to_domain()
        profile_text = ProfileQuery.build_query_text(request)

        try:
            query_embedding = await self._embedding_service.embed(profile_text)
        except EmbeddingServiceUnavailableError:
            await websocket.send_json(
                NoRecommendationMessage(reason="embedding_service_unavailable").model_dump(
                    mode="json"
                )
            )
            return

        start_result = await self._orchestrator.start(request, query_embedding)

        if start_result.needs_confirmation:
            start_result = await self._handle_relax_confirmation(
                websocket, start_result, query_embedding
            )
            if start_result is None:
                return  # timed out — next client message starts a fresh request (BR-03)

        await self._serve_candidates(websocket, start_result, profile_text)

    async def _handle_relax_confirmation(
        self,
        websocket: WebSocket,
        start_result: RecommendationStart,
        query_embedding: tuple[float, ...],
    ) -> RecommendationStart | None:
        offer = RelaxFiltersOfferMessage(
            message=(
                "No encontramos programas dentro de tu presupuesto y duración exactos. "
                "¿Quieres ver alternativas con hasta 50% más de tiempo o 20% más de presupuesto?"
            ),
            relaxed_max_duration_weeks=start_result.relaxed_duration_weeks,
            relaxed_budget=start_result.relaxed_budget,
        )
        await websocket.send_json(offer.model_dump(mode="json"))

        confirmed = await self._await_relax_confirmation(websocket)
        if confirmed is None:
            return None

        return await self._orchestrator.resolve_after_confirmation(
            start_result.candidates, confirmed=confirmed, query_embedding=query_embedding
        )

    async def _await_relax_confirmation(self, websocket: WebSocket) -> bool | None:
        try:
            raw_message = await asyncio.wait_for(
                websocket.receive_json(), timeout=self._relax_confirmation_timeout_seconds
            )
        except (asyncio.TimeoutError, WebSocketDisconnect):
            return None
        try:
            response = RelaxFiltersResponseMessage.model_validate(raw_message)
        except ValidationError:
            return None
        return response.confirm

    async def _serve_candidates(
        self, websocket: WebSocket, start_result: RecommendationStart, profile_text: str
    ) -> None:
        if start_result.branch == RecommendationBranch.FULL_CATALOG:
            await websocket.send_json(NoExactMatchShowingAllMessage().model_dump(mode="json"))

        if not start_result.candidates:
            await websocket.send_json(
                NoRecommendationMessage(reason="empty_catalog").model_dump(mode="json")
            )
            return

        try:
            async for delta in self._agent_client.stream_recommendation(
                start_result.candidates, profile_text, start_result.branch
            ):
                await websocket.send_json(
                    RecommendationDeltaMessage(delta=delta).model_dump(mode="json")
                )
        except AgentUnavailableError:
            await websocket.send_json(
                NoRecommendationMessage(reason="agent_unavailable").model_dump(mode="json")
            )
            return

        await websocket.send_json(
            RecommendationDoneMessage(
                candidates=[
                    CandidateSummary.from_candidate(candidate)
                    for candidate in start_result.candidates
                ]
            ).model_dump(mode="json")
        )
