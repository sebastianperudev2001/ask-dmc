"""OutreachAgentService — agente de outreach (FR-9 a FR-13), mismo patrón agentic/
tool-calling que ChatAgentClient (Agent + FoundryChatClient + tool(), verificado con el
spike original de incremento 2 — ver chat_agent_client.py). Standalone: comparte solo el
modelo de dominio Lead con ChatAgentClient (Application Design Q1 = A), no su lógica de
chat/tool-calling. Único componente que posee tanto la generación como el ciclo de vida
completo del draft (Application Design Q4 = A) — sin un DraftLifecycleService separado."""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone

from agent_framework import Agent, tool
from agent_framework.foundry import FoundryChatClient
from azure.identity import DefaultAzureCredential

from src.domain.lead_event_publisher import LeadEventPublisher
from src.domain.models import DraftStatus, DraftTrigger, LeadEvent, LeadScore, OutreachDraft
from src.ports.course_repository import CourseRepository
from src.ports.draft_repository import DraftRepository
from src.ports.email_sender import EmailSender
from src.ports.lead_repository import LeadRepository

logger = logging.getLogger("agent_service.outreach_agent_service")

_AGENT_NAME = "dmc-outreach-agent"
_AGENT_INSTRUCTIONS = (
    "Eres el redactor de correos de outreach de DMC Institute. Se te dara el resumen de "
    "perfil, motivacion y programas recomendados de un lead. Redacta un email corto, "
    "calido y personalizado invitandolo a retomar la conversacion y avanzar con su "
    "inscripcion. Usa la tool get_course_details para obtener el nombre y descripcion "
    "reales de los programas recomendados — nunca inventes nombres ni precios de cursos. "
    "Responde UNICAMENTE con el asunto en la primera linea (sin el prefijo 'Asunto:') y "
    "el cuerpo del email a partir de la segunda linea."
)


class OutreachError(Exception):
    """Propagado a callers on-demand cuando la generacion o el envio fallan (BR-27)."""


class OutreachAgentService:
    def __init__(
        self,
        project_endpoint: str,
        model_deployment: str,
        credential: DefaultAzureCredential,
        lead_repository: LeadRepository,
        course_repository: CourseRepository,
        draft_repository: DraftRepository,
        email_sender: EmailSender,
        lead_event_publisher: LeadEventPublisher,
    ) -> None:
        self._lead_repository = lead_repository
        self._course_repository = course_repository
        self._draft_repository = draft_repository
        self._email_sender = email_sender

        client = FoundryChatClient(
            project_endpoint=project_endpoint, model=model_deployment, credential=credential
        )
        self._agent = Agent(
            client=client,
            name=_AGENT_NAME,
            instructions=_AGENT_INSTRUCTIONS,
            tools=[
                tool(
                    self._get_course_details,
                    name="get_course_details",
                    description=(
                        "Obtiene nombre, descripcion y malla curricular de un curso real "
                        "del catalogo dado su course_id."
                    ),
                ),
            ],
        )

        # BR-24/PATTERN-23: el trigger automatico se registra en la construccion, no en
        # cada request — vive mientras dure el proceso de agent-service.
        lead_event_publisher.subscribe(self._on_lead_event)

    async def _get_course_details(self, course_id: str) -> str:
        course = await self._course_repository.find_by_id(course_id)
        if course is None:
            return f"No se encontro informacion del curso {course_id}."
        return f"{course.name}: {course.description}. Temas: {', '.join(course.curriculum)}."

    async def _on_lead_event(self, event: LeadEvent) -> None:
        """BR-24: fire-and-forget — nunca await la generacion real dentro del callback
        del publisher, para no bloquear el turno de chat que disparo el cambio de score.
        `motivation_set` handles a race the HOT floor alone can't: the agent raises the
        lead to hot (form completion) and calls set_lead_motivation as a separate, later
        tool-call — so the auto-draft can already exist, generated while motivation was
        still UNDEFINED, by the time motivation is actually known."""
        if event.event_type == "motivation_set" and event.lead.score == LeadScore.HOT:
            asyncio.create_task(self._regenerate_stale_auto_draft(event.lead.id))
            return
        if event.event_type != "score_changed" or event.lead.score != LeadScore.HOT:
            return
        asyncio.create_task(self._generate_draft_from_auto_trigger(event.lead.id))

    async def _regenerate_stale_auto_draft(self, lead_id: str) -> None:
        """Discards and regenerates the active AUTO draft if one already exists — the
        motivation_set event only ever fires once per lead, so this can't loop or
        re-fire on unrelated later saves. Leaves ON_DEMAND drafts (staff-generated)
        alone; only ever regenerates its own auto-trigger's output."""
        try:
            existing = await self._draft_repository.find_active_by_lead_id(lead_id)
            if existing is None or existing.trigger != DraftTrigger.AUTO:
                return
            await self._draft_repository.mark_discarded(existing.draft_id)
            await self.generate_draft(lead_id, DraftTrigger.AUTO)
        except Exception:  # noqa: BLE001 - BR-27: nunca debe escapar hacia el publisher
            logger.exception("auto_draft_regeneration_failed", extra={"lead_id": lead_id})

    async def _generate_draft_from_auto_trigger(self, lead_id: str) -> None:
        try:
            await self.generate_draft(lead_id, DraftTrigger.AUTO)
        except Exception:  # noqa: BLE001 - BR-27: nunca debe escapar hacia el publisher
            logger.exception("auto_draft_generation_failed", extra={"lead_id": lead_id})

    async def generate_draft(self, lead_id: str, trigger: DraftTrigger) -> OutreachDraft | None:
        """BR-23: si ya existe un draft `pending` para este lead, se retorna tal cual —
        mismo metodo para el trigger automatico y el on-demand, misma regla de dedupe
        para ambos. BR-25: el trigger automatico se omite silenciosamente (retorna None)
        si `Lead.email` esta vacio; el on-demand no tiene esa restriccion (Story 5
        permite generar para cualquier lead, en cualquier score)."""
        existing = await self._draft_repository.find_active_by_lead_id(lead_id)
        if existing is not None:
            return existing

        lead = await self._lead_repository.find_by_id(lead_id)
        if lead is None:
            raise OutreachError(f"Lead {lead_id} not found")

        if trigger == DraftTrigger.AUTO and not lead.email:
            logger.info("auto_draft_skipped_missing_email", extra={"lead_id": lead_id})
            return None

        prompt = (
            f"Resumen de perfil: {lead.profile_summary}\n"
            f"Motivacion: {lead.motivation.value} — {lead.motivation_detail}\n"
            f"Programas recomendados (course_id): "
            f"{', '.join(lead.recommended_programs) or 'ninguno'}"
        )

        try:
            # BR-27/PATTERN-22: sin RetryPolicy aqui, a diferencia de EmailSender — un
            # solo intento fallido propaga de inmediato (decision explicita, distinta de
            # PATTERN-21). stream=True (no stream=False) porque es el unico modo
            # verificado para que el framework auto-ejecute el tool get_course_details
            # mid-stream — ver chat_agent_client.py.
            session = self._agent.create_session()
            stream = self._agent.run(prompt, session=session, stream=True)
            text_parts: list[str] = []
            async for update in stream:
                if update.text:
                    text_parts.append(update.text)
            raw_text = "".join(text_parts)
        except Exception as exc:  # noqa: BLE001
            raise OutreachError(str(exc)) from exc

        subject, _, body = raw_text.partition("\n")
        draft = OutreachDraft(
            draft_id=str(uuid.uuid4()),
            lead_id=lead_id,
            subject=subject.strip(),
            body=body.strip(),
            created_at=datetime.now(timezone.utc),
            status=DraftStatus.PENDING,
            trigger=trigger,
        )
        await self._draft_repository.save(draft)
        return draft

    async def get_active_draft(self, lead_id: str) -> OutreachDraft | None:
        return await self._draft_repository.find_active_by_lead_id(lead_id)

    async def send_draft(self, draft_id: str) -> OutreachDraft:
        """PATTERN-26: valida Lead.email antes de siquiera intentar el envio — nunca se
        invoca EmailSender.send con destinatario vacio. PATTERN-28: el guard atomico
        vive en DraftRepository.mark_sent; si el draft ya no esta pending al momento de
        leerlo aqui (reintento tras un timeout, ya procesado antes), se retorna sin
        reenviar — cubre el caso realista de duplicado (reintento de red). Una carrera
        verdaderamente concurrente entre dos requests que leen "pending" casi
        simultaneamente sigue siendo posible en el borde — mitigada primero por el
        loading state del frontend (mecanismo primario, NFR Requirements Sección 16),
        no eliminada por completo aqui."""
        draft = await self._draft_repository.find_by_id(draft_id)
        if draft is None:
            raise OutreachError(f"Draft {draft_id} not found")
        if draft.status != DraftStatus.PENDING:
            return draft

        lead = await self._lead_repository.find_by_id(draft.lead_id)
        if lead is None or not lead.email:
            raise OutreachError(f"Lead {draft.lead_id} has no email on file — cannot send")

        await self._email_sender.send(lead.email, draft.subject, draft.body)

        sent = await self._draft_repository.mark_sent(draft_id)
        if sent is None:
            # Otra llamada ya lo marco sent primero — no reenviar, retornar el estado actual.
            return await self._draft_repository.find_by_id(draft_id)
        return sent

    async def discard_draft(self, draft_id: str) -> OutreachDraft:
        discarded = await self._draft_repository.mark_discarded(draft_id)
        if discarded is None:
            raise OutreachError(f"Draft {draft_id} not found")
        return discarded
