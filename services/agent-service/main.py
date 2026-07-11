from __future__ import annotations

from contextlib import asynccontextmanager

from azure.identity import DefaultAzureCredential
from fastapi import FastAPI, HTTPException, Request, Response, WebSocket
from fastapi.middleware.cors import CORSMiddleware

from src.adapters.acs_email_sender import AzureCommunicationServicesEmailSender
from src.adapters.azure_openai_embedding import AzureOpenAIEmbeddingService
from src.adapters.chat_agent_client import ChatAgentClient
from src.adapters.connection_pool import ConnectionPool
from src.adapters.mercadopago_client import MercadoPagoPaymentClient
from src.adapters.mercadopago_signature import SignatureVerifier
from src.adapters.outreach_agent_service import OutreachAgentService, OutreachError
from src.adapters.postgres_conversation_message_repository import (
    PostgresConversationMessageRepository,
)
from src.adapters.postgres_conversation_session_store import PostgresConversationSessionStore
from src.adapters.postgres_course_repository import PostgresCourseRepository
from src.adapters.postgres_draft_repository import PostgresDraftRepository
from src.adapters.postgres_lead_repository import PostgresLeadRepository
from src.adapters.retry_policy import RetryPolicy
from src.api.chat_websocket_handler import ChatWebSocketHandler
from src.api.lead_broadcaster import LeadBroadcaster
from src.api.schemas import ConversationMessageOut, ConversationSummaryOut, LeadOut, OutreachDraftOut
from src.api.webhook_handler import MercadoPagoWebhookHandler
from src.config import ENV, load_config
from src.domain.lead_event_publisher import LeadEventPublisher
from src.domain.lead_query_service import LeadQueryService
from src.domain.models import DraftTrigger
from src.domain.orchestrator import RecommendationOrchestrator
from src.logging_config import configure_logging

logger = configure_logging()
config = load_config()
credential = DefaultAzureCredential()
connection_pool = ConnectionPool(config.database_url, require_ssl=(config.env == ENV.PRODUCTION))

# Incremento 3 (BackOffice) — instancias únicas de proceso, no reconstruidas por
# conexión/request (a diferencia de ChatAgentClient): LeadEventPublisher/LeadBroadcaster
# deben ser compartidas por todas las conexiones /ws/leads y por cada ChatAgentClient
# que publique un evento (PATTERN-25 — instancia única de agent-service, ver
# nfr-design-patterns.md). OutreachAgentService también es un singleton: su suscripción
# al publisher debe registrarse una sola vez al arrancar el proceso, no por request.
lead_event_publisher = LeadEventPublisher()
lead_query_service = LeadQueryService(PostgresLeadRepository(connection_pool))
lead_broadcaster = LeadBroadcaster(lead_query_service)
lead_event_publisher.subscribe(lead_broadcaster.broadcast)
outreach_agent_service = OutreachAgentService(
    project_endpoint=config.foundry_project_endpoint,
    model_deployment=config.foundry_agent_model_deployment,
    credential=credential,
    lead_repository=PostgresLeadRepository(connection_pool),
    course_repository=PostgresCourseRepository(connection_pool),
    draft_repository=PostgresDraftRepository(connection_pool),
    email_sender=AzureCommunicationServicesEmailSender(
        config.acs_connection_string,
        sender_address=config.acs_sender_address,
        retry_policy=RetryPolicy(
            max_attempts=config.retry_max_attempts,
            base_delay_seconds=config.retry_base_delay_seconds,
        ),
    ),
    lead_event_publisher=lead_event_publisher,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await connection_pool.start()
    logger.info("agent_service_started")
    yield
    await connection_pool.close()
    logger.info("agent_service_stopped")


app = FastAPI(lifespan=lifespan)

# Added for GET /conversations/{id}/messages (rehydration after a page reload) — the
# browser calls this via fetch() from a different origin (localhost:3000), unlike the
# WS endpoint which isn't subject to CORS. Alcance local (NFR Requirements) — allows
# only the local dev frontend origin, not a wildcard.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


def _build_retry_policy() -> RetryPolicy:
    return RetryPolicy(
        max_attempts=config.retry_max_attempts,
        base_delay_seconds=config.retry_base_delay_seconds,
    )


def build_chat_websocket_handler() -> ChatWebSocketHandler:
    """RecommendationOrchestrator/CourseRepository (incremento 1) are reused unchanged
    — exposed to the agent as the get_course_recommendations tool."""

    def agent_client_factory(on_profile_data_requested, pending_tool_calls, conversation_id) -> ChatAgentClient:
        retry_policy = _build_retry_policy()
        payment_client = MercadoPagoPaymentClient(
            access_token=config.mercadopago_access_token,
            retry_policy=retry_policy,
            base_url=config.mercadopago_base_url,
        )
        orchestrator = RecommendationOrchestrator(PostgresCourseRepository(connection_pool))
        embedding_service = AzureOpenAIEmbeddingService(
            endpoint=config.azure_openai_endpoint,
            deployment=config.azure_openai_embedding_deployment,
            credential=credential,
            retry_policy=retry_policy,
        )
        return ChatAgentClient(
            project_endpoint=config.foundry_project_endpoint,
            model_deployment=config.foundry_agent_model_deployment,
            credential=credential,
            retry_policy=retry_policy,
            conversation_id=conversation_id,
            payment_client=payment_client,
            pending_tool_calls=pending_tool_calls,
            on_profile_data_requested=on_profile_data_requested,
            orchestrator=orchestrator,
            embedding_service=embedding_service,
            lead_repository=PostgresLeadRepository(connection_pool),
            profile_data_timeout_seconds=config.profile_data_timeout_seconds,
            lead_event_publisher=lead_event_publisher,
        )

    return ChatWebSocketHandler(
        agent_client_factory=agent_client_factory,
        conversation_message_repository=PostgresConversationMessageRepository(connection_pool),
        conversation_session_store=PostgresConversationSessionStore(connection_pool),
    )


def build_webhook_handler() -> MercadoPagoWebhookHandler:
    retry_policy = _build_retry_policy()
    return MercadoPagoWebhookHandler(
        signature_verifier=SignatureVerifier(config.mercadopago_webhook_secret),
        payment_client=MercadoPagoPaymentClient(
            access_token=config.mercadopago_access_token,
            retry_policy=retry_policy,
            base_url=config.mercadopago_base_url,
        ),
        lead_repository=PostgresLeadRepository(connection_pool),
    )


@app.websocket("/ws/chat")
async def chat_websocket(websocket: WebSocket) -> None:
    handler = build_chat_websocket_handler()
    await handler.handle_connection(websocket)


@app.post("/webhooks/mercadopago")
async def mercadopago_webhook(request: Request) -> Response:
    # NFR Requirements (Incremento 2): not exposed publicly in this increment — reached
    # only via scripts/simulate_mercadopago_webhook.py against localhost.
    handler = build_webhook_handler()
    return await handler.handle(request)


@app.get("/conversations/{conversation_id}/messages")
async def conversation_messages(conversation_id: str) -> list[ConversationMessageOut]:
    """Rehydration endpoint (added after Build and Test): lets the frontend restore
    visible messages after a page reload, since the Foundry thread itself resumes
    correctly but React state does not survive a reload on its own."""
    repository = PostgresConversationMessageRepository(connection_pool)
    messages = await repository.get_messages(conversation_id)
    return [ConversationMessageOut(role=m.role.value, content=m.content) for m in messages]


@app.get("/conversations")
async def conversations() -> list[ConversationSummaryOut]:
    """Real conversation history list (added after user feedback: the Sidebar's history
    was hardcoded mock data, unrelated to any real conversation)."""
    repository = PostgresConversationMessageRepository(connection_pool)
    summaries = await repository.list_conversations()
    return [
        ConversationSummaryOut(
            conversation_id=s.conversation_id,
            preview=s.preview,
            last_activity_at=s.last_activity_at,
        )
        for s in summaries
    ]


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


# ── Incremento 3 — BackOffice: read path + broadcast + agente de outreach ──


@app.get("/leads")
async def list_leads() -> list[LeadOut]:
    """FR-7. Sin filtros/paginación (NFR-4, escala demo). No hay GET /leads/{id} —
    la vista de detalle se sirve desde este mismo payload (Application Design, Q5 = B)."""
    leads = await lead_query_service.list_leads()
    return [LeadOut.from_lead(lead) for lead in leads]


@app.websocket("/ws/leads")
async def leads_websocket(websocket: WebSocket) -> None:
    # NFR-1 (issue #18): sin auth en esta iteración, mismo alcance ya aceptado para
    # /ws/chat — riesgo ya conocido, no re-decidido aquí.
    await lead_broadcaster.handle_connection(websocket)


@app.post("/leads/{lead_id}/drafts")
async def generate_draft(lead_id: str) -> OutreachDraftOut | None:
    """FR-11 — on-demand, cualquier score tier. None si el trigger fuera automático y
    faltara el email (BR-25) — no aplica aquí, esta ruta siempre es on_demand."""
    try:
        draft = await outreach_agent_service.generate_draft(lead_id, DraftTrigger.ON_DEMAND)
    except OutreachError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return OutreachDraftOut.from_draft(draft) if draft else None


@app.get("/leads/{lead_id}/drafts/active")
async def get_active_draft(lead_id: str) -> OutreachDraftOut | None:
    """Usado por DraftPanel al abrir el detail popup de un lead (FR-4/Story 4/5)."""
    draft = await outreach_agent_service.get_active_draft(lead_id)
    return OutreachDraftOut.from_draft(draft) if draft else None


@app.post("/drafts/{draft_id}/send")
async def send_draft(draft_id: str) -> OutreachDraftOut:
    """FR-12 — human-in-the-loop gate: solo alcanzable por una acción explícita de
    staff, nunca automático."""
    try:
        draft = await outreach_agent_service.send_draft(draft_id)
    except OutreachError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return OutreachDraftOut.from_draft(draft)


@app.post("/drafts/{draft_id}/discard")
async def discard_draft(draft_id: str) -> OutreachDraftOut:
    try:
        draft = await outreach_agent_service.discard_draft(draft_id)
    except OutreachError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return OutreachDraftOut.from_draft(draft)
