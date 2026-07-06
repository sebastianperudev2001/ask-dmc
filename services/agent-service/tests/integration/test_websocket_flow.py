"""Integration tests for WebSocketConnectionHandler — exercises the full WS message
contract (business-logic-model.md Section 3) against fake ports (no real Postgres/Azure)."""
from __future__ import annotations

from decimal import Decimal

from fastapi import FastAPI, WebSocket
from fastapi.testclient import TestClient

from src.api.websocket_handler import WebSocketConnectionHandler
from src.domain.models import Course
from src.domain.orchestrator import RecommendationOrchestrator
from tests.integration.fakes import FakeEmbeddingService, FakeRecommendationAgentClient
from tests.unit.fakes import InMemoryCourseRepository

AFFORDABLE_COURSE = Course(
    course_id="diploma-data-science",
    name="Diploma en Data Science",
    description="Programa integral de Data Science",
    category="Data Science",
    curriculum=("Python", "Machine Learning"),
    price=Decimal("3000"),
    duration_weeks=10,
    embedding=(1.0, 0.0, 0.0),
)

EXPENSIVE_COURSE = Course(
    course_id="maestria-data-science",
    name="Maestría en Data Science",
    description="Programa avanzado",
    category="Data Science",
    curriculum=("Deep Learning",),
    # Fuera del filtro estricto (budget=3500, max_duration=12) pero dentro del relajado
    # (relaxed_budget=4200, relaxed_duration=18) — dispara la oferta de relajación (BR-03).
    price=Decimal("4000"),
    duration_weeks=15,
    embedding=(1.0, 0.0, 0.0),
)

VALID_REQUEST = {
    "type": "recommendation_request",
    "budget": "3500.00",
    "max_duration_weeks": 12,
    "professional_background": "Data Engineer en Yape",
    "desired_stack": "Data Science",
}


def build_test_app(courses: list[Course], timeout_seconds: float = 5.0) -> FastAPI:
    app = FastAPI()
    orchestrator = RecommendationOrchestrator(InMemoryCourseRepository(courses))
    handler = WebSocketConnectionHandler(
        orchestrator=orchestrator,
        embedding_service=FakeEmbeddingService(),
        agent_client=FakeRecommendationAgentClient(),
        relax_confirmation_timeout_seconds=timeout_seconds,
    )

    @app.websocket("/ws")
    async def ws_route(websocket: WebSocket) -> None:
        await handler.handle_connection(websocket)

    return app


def test_exact_match_streams_recommendation():
    app = build_test_app([AFFORDABLE_COURSE, EXPENSIVE_COURSE])
    with TestClient(app).websocket_connect("/ws") as ws:
        ws.send_json(VALID_REQUEST)
        first_delta = ws.receive_json()
        assert first_delta["type"] == "recommendation_delta"
        second_delta = ws.receive_json()
        assert second_delta["type"] == "recommendation_delta"
        done = ws.receive_json()
        assert done["type"] == "recommendation_done"
        assert done["candidates"][0]["course_id"] == "diploma-data-science"


def test_relaxation_offered_and_confirmed():
    app = build_test_app([EXPENSIVE_COURSE])
    with TestClient(app).websocket_connect("/ws") as ws:
        ws.send_json(VALID_REQUEST)
        offer = ws.receive_json()
        assert offer["type"] == "relax_filters_offer"
        assert offer["relaxed_max_duration_weeks"] == 18

        ws.send_json({"type": "relax_filters_response", "confirm": True})
        delta = ws.receive_json()
        assert delta["type"] == "recommendation_delta"


def test_relaxation_offered_and_declined_shows_full_catalog():
    app = build_test_app([EXPENSIVE_COURSE])
    with TestClient(app).websocket_connect("/ws") as ws:
        ws.send_json(VALID_REQUEST)
        offer = ws.receive_json()
        assert offer["type"] == "relax_filters_offer"

        ws.send_json({"type": "relax_filters_response", "confirm": False})
        no_match = ws.receive_json()
        assert no_match["type"] == "no_exact_match_showing_all"
        delta = ws.receive_json()
        assert delta["type"] == "recommendation_delta"


def test_empty_catalog_skips_agent_invocation():
    app = build_test_app([])
    with TestClient(app).websocket_connect("/ws") as ws:
        ws.send_json(VALID_REQUEST)
        no_match = ws.receive_json()
        assert no_match["type"] == "no_exact_match_showing_all"
        empty = ws.receive_json()
        assert empty["type"] == "no_recommendation"
        assert empty["reason"] == "empty_catalog"


def test_invalid_request_returns_generic_error():
    app = build_test_app([AFFORDABLE_COURSE])
    with TestClient(app).websocket_connect("/ws") as ws:
        ws.send_json({"type": "recommendation_request", "budget": -1})
        error = ws.receive_json()
        assert error["type"] == "no_recommendation"
        assert error["reason"] == "invalid_request"
