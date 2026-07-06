"""WebSocket message schemas. See business-logic-model.md Section 3 for the contract.

Every incoming field is bounded (SECURITY-05: type checking, length/size bounds) —
Pydantic rejects malformed input before it reaches RecommendationOrchestrator."""
from __future__ import annotations

import math
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from src.domain.models import RecommendationCandidate, RecommendationRequest

MAX_TEXT_FIELD_LENGTH = 2000
MAX_BUDGET = Decimal("1000000")
MAX_DURATION_WEEKS = 104  # 2 years


class RecommendationRequestMessage(BaseModel):
    type: Literal["recommendation_request"]
    budget: Decimal = Field(gt=0, le=MAX_BUDGET)
    max_duration_weeks: int = Field(gt=0, le=MAX_DURATION_WEEKS)
    professional_background: str = Field(min_length=1, max_length=MAX_TEXT_FIELD_LENGTH)
    desired_stack: str = Field(min_length=1, max_length=MAX_TEXT_FIELD_LENGTH)

    def to_domain(self) -> RecommendationRequest:
        return RecommendationRequest(
            budget=self.budget,
            max_duration_weeks=self.max_duration_weeks,
            professional_background=self.professional_background,
            desired_stack=self.desired_stack,
        )


class RelaxFiltersResponseMessage(BaseModel):
    type: Literal["relax_filters_response"]
    confirm: bool


class CandidateSummary(BaseModel):
    course_id: str
    name: str
    similarity_score: float

    @staticmethod
    def from_candidate(candidate: RecommendationCandidate) -> "CandidateSummary":
        # SECURITY-15-style fail-safe: pgvector's cosine distance (`<=>`) is undefined
        # for a zero-magnitude embedding, producing `float('nan')` — and `json.dumps`
        # emits the literal `NaN`, which is not valid JSON per spec and every browser's
        # `JSON.parse` rejects it, breaking the whole turn. Found via user report.
        similarity_score = candidate.similarity_score
        if math.isnan(similarity_score):
            similarity_score = 0.0
        return CandidateSummary(
            course_id=candidate.course.course_id,
            name=candidate.course.name,
            similarity_score=similarity_score,
        )


class RecommendationDeltaMessage(BaseModel):
    type: Literal["recommendation_delta"] = "recommendation_delta"
    delta: str


class RecommendationDoneMessage(BaseModel):
    type: Literal["recommendation_done"] = "recommendation_done"
    candidates: list[CandidateSummary]


class RelaxFiltersOfferMessage(BaseModel):
    type: Literal["relax_filters_offer"] = "relax_filters_offer"
    message: str
    relaxed_max_duration_weeks: int
    relaxed_budget: Decimal


class NoExactMatchShowingAllMessage(BaseModel):
    type: Literal["no_exact_match_showing_all"] = "no_exact_match_showing_all"
    reason: str = "no_courses_match_criteria"


class NoRecommendationMessage(BaseModel):
    type: Literal["no_recommendation"] = "no_recommendation"
    reason: str


# ── Incremento 2 — chat conversacional + tool-calling + pago (business-logic-model.md Sección 9) ──


class UserMessageIn(BaseModel):
    type: Literal["user_message"]
    text: str = Field(min_length=1, max_length=MAX_TEXT_FIELD_LENGTH)
    # Ambos presentes únicamente en el primer mensaje de una conexión que retoma una
    # sesión previa (RF-I05) — ignorados en mensajes subsecuentes de la misma conexión.
    service_session_id: str | None = None
    # Agregado tras Build and Test (rehidratación de mensajes al recargar): permite que
    # el Lead y la transcripción persistida (conversation_messages) sigan bajo el mismo
    # conversation_id en vez de fragmentarse en uno nuevo por cada reload.
    conversation_id: str | None = None


class ProfileDataSubmittedIn(BaseModel):
    type: Literal["profile_data_submitted"]
    call_id: str
    budget: Decimal = Field(gt=0, le=MAX_BUDGET)
    max_duration_weeks: int = Field(gt=0, le=MAX_DURATION_WEEKS)
    professional_background: str = Field(min_length=1, max_length=MAX_TEXT_FIELD_LENGTH)
    desired_stack: str = Field(min_length=1, max_length=MAX_TEXT_FIELD_LENGTH)


class ProfileDataPrefill(BaseModel):
    """Values the agent already inferred from the conversation — the widget prefills
    with these, the user corrects/completes rather than starting from a blank form."""

    budget: float | None = None
    max_duration_weeks: int | None = None
    professional_background: str | None = None
    desired_stack: str | None = None


class ProfileDataRequestedOut(BaseModel):
    type: Literal["profile_data_requested"] = "profile_data_requested"
    call_id: str
    prefill: ProfileDataPrefill


class PaymentLinkCreatedOut(BaseModel):
    type: Literal["payment_link_created"] = "payment_link_created"
    checkout_url: str


class SessionCreatedOut(BaseModel):
    type: Literal["session_created"] = "session_created"
    service_session_id: str
    # Added after Build and Test (user feedback: reload showed a blank chat) — the
    # frontend persists this alongside service_session_id to fetch the transcript from
    # GET /conversations/{conversation_id}/messages and rehydrate on load.
    conversation_id: str


class ConversationMessageOut(BaseModel):
    role: str
    content: str


class ConversationSummaryOut(BaseModel):
    """Real conversation history entry — replaces the frontend's hardcoded mock
    Sidebar list (added after user feedback)."""

    conversation_id: str
    preview: str
    last_activity_at: datetime


class TurnDoneOut(BaseModel):
    """Signals the end of one agent turn (business-logic-model.md Section 9) — added
    during Code Generation: free-form chat has no other reliable way for the frontend
    to know the agent finished responding to a given user_message (unlike incremento 1's
    recommendation_done/no_recommendation, which were single-purpose terminators)."""

    type: Literal["turn_done"] = "turn_done"


class MercadoPagoWebhookData(BaseModel):
    id: str


class MercadoPagoWebhookPayload(BaseModel):
    """See business-logic-model.md Section 10 — only `type` and `data.id` are used;
    the rest of the payload is never trusted as the source of truth (BR-20)."""

    type: str
    data: MercadoPagoWebhookData
