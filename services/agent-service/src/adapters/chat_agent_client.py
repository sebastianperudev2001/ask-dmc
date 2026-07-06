"""ChatAgentClient — wraps Microsoft Agent Framework's Agent with the 2 tools of
Incremento 2 (collect_profile_data, create_payment_link) plus session persistence via
Foundry Memory (PATTERN-20).

Verified with a real spike against the actual installed SDK and the live Foundry agent
(see aidlc-docs/construction/plans/agent-service-increment2-functional-design-plan.md):
the framework auto-executes attached Python callables with already-parsed arguments and
continues its own conversational loop, all inside a single `agent.run(stream=True)`.
`collect_profile_data` exploits this: it sends `profile_data_requested` immediately
(with the agent's own inferred values as prefill) and then `await`s an `asyncio.Future`
that the WS handler's concurrent receiver resolves once `profile_data_submitted` arrives
— the "human in the loop" pause from business-logic-model.md Section 8.1, achieved with
no special framework support, just an async function that doesn't return immediately.
`create_payment_link` needs no pause — it performs the real network call inline."""
from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from agent_framework import Agent, AgentSession, tool
from agent_framework.foundry import FoundryChatClient
from azure.identity import DefaultAzureCredential

from datetime import datetime, timezone

from src.adapters.mercadopago_client import MercadoPagoPaymentClient
from src.adapters.retry_policy import RetryPolicy
from src.domain.errors import AgentUnavailableError, PaymentServiceUnavailableError
from src.domain.lead_scoring import apply_score_floor
from src.domain.models import Lead, LeadScore, ProfileQuery, RecommendationCandidate, RecommendationRequest
from src.domain.orchestrator import RecommendationOrchestrator
from src.domain.pending_tool_calls import PendingToolCallRegistry
from src.ports.embedding_service import EmbeddingService
from src.ports.lead_repository import LeadRepository

_AGENT_NAME = "dmc-sales-advisor"
_AGENT_INSTRUCTIONS = (
    "Eres el asesor de ventas de DMC Institute, un asistente de IA (identificate como "
    "tal si te preguntan). Conversa libremente con el visitante para entender su "
    "background profesional, motivacion y que quiere aprender — nunca presentes "
    "formularios ni hagas varias preguntas en el mismo turno. Cuando necesites datos "
    "estructurados de calificacion (presupuesto, duracion maxima disponible en semanas, "
    "background profesional, stack deseado) que aun no tengas, invoca la tool "
    "collect_profile_data con los valores que ya infieras de la conversacion (o valores "
    "razonables si no los tienes) — el usuario los confirmara o corregira en un widget. "
    "Una vez tengas esos 4 datos confirmados, invoca get_course_recommendations con "
    "ellos para buscar programas reales del catalogo — nunca inventes cursos, precios "
    "ni mallas curriculares fuera de lo que esa tool te devuelva. Si esa tool te dice "
    "que no hay match exacto y te sugiere un rango ampliado, ofrece esa alternativa al "
    "usuario en tus propias palabras y, si acepta, vuelve a llamar a "
    "get_course_recommendations con accept_relaxed_filters=true. Cuando el usuario "
    "exprese intencion de compra de un programa, invoca create_payment_link con el "
    "monto y la descripcion del programa. Si el usuario pide hablar con una persona, "
    "dile que alguien del equipo se pondra en contacto, sin dar telefono ni WhatsApp."
)


@dataclass(frozen=True)
class TextDelta:
    text: str


@dataclass(frozen=True)
class ProfileDataRequested:
    call_id: str
    prefill: dict[str, Any]


@dataclass(frozen=True)
class PaymentLinkCreated:
    checkout_url: str
    preference_id: str
    amount: Decimal


@dataclass(frozen=True)
class RecommendationsReady:
    candidates: list[RecommendationCandidate]


ChatEvent = TextDelta | ProfileDataRequested | PaymentLinkCreated | RecommendationsReady
SendProfileDataRequestedFn = Callable[[ProfileDataRequested], Awaitable[None]]


class ChatAgentClient:
    def __init__(
        self,
        project_endpoint: str,
        model_deployment: str,
        credential: DefaultAzureCredential,
        retry_policy: RetryPolicy,
        payment_client: MercadoPagoPaymentClient,
        pending_tool_calls: PendingToolCallRegistry,
        on_profile_data_requested: SendProfileDataRequestedFn,
        orchestrator: RecommendationOrchestrator,
        embedding_service: EmbeddingService,
        lead_repository: LeadRepository,
        conversation_id: str,
        profile_data_timeout_seconds: float = 300.0,
    ) -> None:
        self._retry_policy = retry_policy
        self._payment_client = payment_client
        self._pending_tool_calls = pending_tool_calls
        self._on_profile_data_requested = on_profile_data_requested
        self._orchestrator = orchestrator
        self._embedding_service = embedding_service
        self._lead_repository = lead_repository
        self._profile_data_timeout_seconds = profile_data_timeout_seconds
        # Found via real E2E verification (Build and Test): AgentSession.service_session_id
        # is Foundry's *response id* for the last turn (prefix "resp_") — it rotates on
        # every agent.run() call, it is NOT a stable thread identifier. Using it as the
        # Lead correlation key fragmented one conversation into N rows (one per turn).
        # `conversation_id` is generated once per WS connection (ChatWebSocketHandler) and
        # used instead for anything that must stay stable across turns of the same
        # connection (Lead upsert key, Mercado Pago external_reference). Known limitation:
        # a reconnect (page refresh) still starts a new Lead row, even though the Foundry
        # conversation itself resumes correctly via service_session_id — acceptable for
        # this demo's scope.
        self._conversation_id = conversation_id
        self._payment_link_created: PaymentLinkCreated | None = None
        self._recommendations_ready: RecommendationsReady | None = None
        self._current_session: AgentSession | None = None
        self._user_message_count = 0

        client = FoundryChatClient(
            project_endpoint=project_endpoint, model=model_deployment, credential=credential
        )
        self._agent = Agent(
            client=client,
            name=_AGENT_NAME,
            instructions=_AGENT_INSTRUCTIONS,
            tools=[
                tool(
                    self._collect_profile_data,
                    name="collect_profile_data",
                    description=(
                        "Recolecta datos de perfil del usuario cuando aun no los tienes: "
                        "presupuesto, duracion maxima en semanas, background profesional y "
                        "stack deseado. Pasa tus mejores estimaciones basadas en la "
                        "conversacion — el usuario las confirmara o corregira."
                    ),
                ),
                tool(
                    self._get_course_recommendations,
                    name="get_course_recommendations",
                    description=(
                        "Busca programas reales del catalogo que calcen con el perfil "
                        "confirmado. Usa accept_relaxed_filters=true solo si ya ofreciste "
                        "un rango ampliado en un turno anterior y el usuario acepto."
                    ),
                ),
                tool(
                    self._create_payment_link,
                    name="create_payment_link",
                    description=(
                        "Genera un link de pago real cuando el usuario expresa intencion de "
                        "compra de un programa especifico."
                    ),
                ),
            ],
        )

    def create_session(self) -> AgentSession:
        return self._agent.create_session()

    def get_session(self, service_session_id: str) -> AgentSession:
        return self._agent.get_session(service_session_id)

    def set_conversation_id(self, conversation_id: str) -> None:
        """Lets ChatWebSocketHandler resume the client's own conversation_id (sent back
        on reconnect) instead of the provisional one generated at connection start —
        keeps Lead correlation and the persisted transcript (conversation_messages)
        continuous across a page reload."""
        self._conversation_id = conversation_id

    async def record_user_message(self) -> None:
        """BR-17b: called once per user turn (ChatWebSocketHandler) so the engagement
        floor (5+ user messages -> warm, 10+ -> hot) re-evaluates after every message."""
        self._user_message_count += 1
        await self._apply_engagement_floor()

    async def _apply_engagement_floor(self, *, form_completed: bool = False) -> None:
        """BR-17b: raises Lead.score to the engagement floor if it exceeds the current
        score — monotonic (never downgrades), see apply_score_floor()."""
        lead = await self._lead_repository.find_by_service_session_id(self._conversation_id)
        current_score = lead.score if lead is not None else LeadScore.COLD
        current_justification = lead.score_justification if lead is not None else ""
        result = apply_score_floor(
            current_score, current_justification, self._user_message_count, form_completed
        )
        if result is not None:
            score, justification = result
            await self._upsert_lead(score=score, score_justification=justification)

    async def _upsert_lead(self, **fields) -> Lead | None:
        """BR-21: incrementally persists a Lead keyed by `conversation_id` (stable per
        WS connection — see __init__ docstring for why service_session_id can't be used
        here)."""
        lead = await self._lead_repository.find_by_service_session_id(self._conversation_id)
        if lead is None:
            lead = Lead(
                id=str(uuid.uuid4()),
                created_at=datetime.now(timezone.utc),
                service_session_id=self._conversation_id,
            )
        for key, value in fields.items():
            setattr(lead, key, value)
        await self._lead_repository.save(lead)
        return lead

    async def _collect_profile_data(
        self,
        budget: float,
        max_duration_weeks: int,
        professional_background: str,
        desired_stack: str,
    ) -> str:
        """Tool (BR-16): the agent decides when to call this. Pauses (business-logic-model.md
        Section 8.1) until the WS handler resolves the matching future with the user's
        profile_data_submitted response — or until profile_data_timeout_seconds elapses.

        A timeout is required despite NFR Requirements' original decision (Clarification
        Q1 = C: "no timeout, disconnect is the natural limit") — found via real Build and
        Test verification that a user can abandon the widget WITHOUT disconnecting (e.g.
        clicking "Nueva conversación" instead of submitting it), which permanently
        deadlocks the connection: the main loop is blocked right here and never reaches a
        point where it would notice the disconnect on its own."""
        call_id = f"call_{uuid.uuid4().hex}"
        prefill = {
            "budget": budget,
            "max_duration_weeks": max_duration_weeks,
            "professional_background": professional_background,
            "desired_stack": desired_stack,
        }
        future = self._pending_tool_calls.create(call_id)
        await self._on_profile_data_requested(ProfileDataRequested(call_id=call_id, prefill=prefill))
        try:
            result = await asyncio.wait_for(future, timeout=self._profile_data_timeout_seconds)
        except asyncio.TimeoutError:
            return (
                "El usuario no respondio el formulario a tiempo. Indicale que puede "
                "escribir sus datos directamente en el chat cuando guste, o volver a "
                "pedir el formulario."
            )

        await self._upsert_lead(
            profile_summary=f"{result['professional_background']} — busca: {result['desired_stack']}",
        )
        await self._apply_engagement_floor(form_completed=True)

        return (
            f"Datos confirmados por el usuario: presupuesto={result['budget']}, "
            f"duracion_maxima_semanas={result['max_duration_weeks']}, "
            f"background={result['professional_background']}, "
            f"stack_deseado={result['desired_stack']}"
        )

    async def _get_course_recommendations(
        self,
        budget: float,
        max_duration_weeks: int,
        professional_background: str,
        desired_stack: str,
        accept_relaxed_filters: bool = False,
    ) -> str:
        """Tool: reuses RecommendationOrchestrator (incremento 1, BR-01 a BR-11)
        unchanged. If no exact match exists and the caller hasn't yet accepted relaxed
        filters, returns a text description for the agent to offer conversationally
        (Clarification 4 = A — no widget for this, just natural language) rather than
        pausing like collect_profile_data does."""
        request = RecommendationRequest(
            budget=Decimal(str(budget)),
            max_duration_weeks=max_duration_weeks,
            professional_background=professional_background,
            desired_stack=desired_stack,
        )
        profile_text = ProfileQuery.build_query_text(request)
        query_embedding = await self._embedding_service.embed(profile_text)
        start_result = await self._orchestrator.start(request, query_embedding)

        if start_result.needs_confirmation and not accept_relaxed_filters:
            return (
                f"No hay cursos que calcen exactamente con el presupuesto y duracion dados. "
                f"Ofrece al usuario ampliar el rango a un presupuesto de hasta "
                f"{start_result.relaxed_budget} y duracion de hasta "
                f"{start_result.relaxed_duration_weeks} semanas. Si el usuario acepta, "
                f"vuelve a llamar a esta tool con los mismos datos y "
                f"accept_relaxed_filters=true."
            )

        if start_result.needs_confirmation and accept_relaxed_filters:
            start_result = await self._orchestrator.resolve_after_confirmation(
                start_result.candidates, confirmed=True, query_embedding=query_embedding
            )

        if not start_result.candidates:
            return "El catalogo no tiene programas registrados en este momento."

        self._recommendations_ready = RecommendationsReady(candidates=start_result.candidates)
        await self._upsert_lead(
            recommended_programs=[c.course.course_id for c in start_result.candidates]
        )
        summary = "\n".join(
            f"- {c.course.name} (precio {c.course.price}, {c.course.duration_weeks} semanas, "
            f"similarity_score={c.similarity_score:.2f}, temas: {', '.join(c.course.curriculum)})"
            for c in start_result.candidates
        )
        return f"Candidatos encontrados en el catalogo:\n{summary}"

    async def _create_payment_link(self, amount: float, description: str) -> str:
        """Tool (BR-18): errors surface as a plain-text result, never an unhandled
        exception that would break the agent's stream. `external_reference` is set to
        `conversation_id` (stable per WS connection, see __init__ docstring) so the
        webhook can correlate the payment back to the same Lead regardless of which
        turn's Foundry service_session_id happened to be current."""
        try:
            order = await self._payment_client.create_preference(
                Decimal(str(amount)), description, external_reference=self._conversation_id
            )
        except PaymentServiceUnavailableError:
            return (
                "No se pudo generar el link de pago en este momento — informa al usuario "
                "que lo intenten de nuevo en unos minutos."
            )
        self._payment_link_created = PaymentLinkCreated(
            checkout_url=order.checkout_url,
            preference_id=order.preference_id,
            amount=Decimal(str(amount)),
        )
        await self._upsert_lead(
            payment_link_sent=True,
            payment_checkout_url=order.checkout_url,
            payment_preference_id=order.preference_id,
        )
        return f"Link de pago generado: {order.checkout_url}"

    def _drain_events(self, update: Any) -> list[ChatEvent]:
        events: list[ChatEvent] = []
        if update.text:
            events.append(TextDelta(text=update.text))
        if self._payment_link_created is not None:
            events.append(self._payment_link_created)
            self._payment_link_created = None
        if self._recommendations_ready is not None:
            events.append(self._recommendations_ready)
            self._recommendations_ready = None
        return events

    async def stream(self, user_text: str, session: AgentSession) -> AsyncIterator[ChatEvent]:
        self._current_session = session

        async def _start() -> tuple:
            stream = self._agent.run(user_text, session=session, stream=True)
            first_update = await stream.__anext__()
            return stream, first_update

        try:
            stream, first_update = await self._retry_policy.run(_start)
        except Exception as exc:  # noqa: BLE001
            raise AgentUnavailableError(str(exc)) from exc

        for event in self._drain_events(first_update):
            yield event
        try:
            async for update in stream:
                for event in self._drain_events(update):
                    yield event
        except Exception as exc:  # noqa: BLE001
            raise AgentUnavailableError(str(exc)) from exc
