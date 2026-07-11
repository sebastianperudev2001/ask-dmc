from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Literal


class RecommendationBranch(str, Enum):
    """Which BR-03/BR-11 branch produced the candidates — told to the agent (step 8)
    so it communicates transparently what it is showing."""

    EXACT_MATCH = "exact_match"
    RELAXED_MATCH = "relaxed_match"
    FULL_CATALOG = "full_catalog"


@dataclass(frozen=True)
class Course:
    """A DMC Institute program/course. See domain-entities.md."""

    course_id: str
    name: str
    description: str
    category: str
    curriculum: tuple[str, ...]
    price: Decimal
    duration_weeks: int
    embedding: tuple[float, ...] | None = None

    def embedding_text(self) -> str:
        """Text used to generate Course.embedding. See business-logic-model.md Section 1."""
        topics = ", ".join(self.curriculum)
        return f"{self.name}. {self.category}. {self.description}. Temas: {topics}"


@dataclass(frozen=True)
class RecommendationRequest:
    """The structured mini-form submitted by the visitor. See BR-09: all fields required."""

    budget: Decimal
    max_duration_weeks: int
    professional_background: str
    desired_stack: str

    def __post_init__(self) -> None:
        if self.budget <= 0:
            raise ValueError("budget must be positive")
        if self.max_duration_weeks <= 0:
            raise ValueError("max_duration_weeks must be positive")
        if not self.professional_background.strip():
            raise ValueError("professional_background must not be empty")
        if not self.desired_stack.strip():
            raise ValueError("desired_stack must not be empty")


@dataclass(frozen=True)
class ProfileQuery:
    """Ephemeral synthesized query text + embedding for a single request. Never persisted (BR-08)."""

    query_text: str
    query_embedding: tuple[float, ...]

    @staticmethod
    def build_query_text(request: RecommendationRequest) -> str:
        return f"{request.professional_background} {request.desired_stack}"


@dataclass(frozen=True)
class RecommendationCandidate:
    """A course that survived filtering, with its semantic similarity score. See BR-04/BR-05/BR-11."""

    course: Course
    similarity_score: float
    filters_relaxed: tuple[str, ...] = field(default_factory=tuple)
    from_full_catalog: bool = False


# ── Incremento 2 — chat conversacional + tool-calling + pago (domain-entities.md) ──


class Motivation(str, Enum):
    """Same 5 categories as requirements.md Section 5.2 (RF-06)."""

    GROWTH = "growth"
    SALARY = "salary"
    COMPANY_REQUIREMENT = "company_requirement"
    ACADEMIC = "academic"
    UNDEFINED = "undefined"


class LeadScore(str, Enum):
    """BR-17."""

    HOT = "hot"
    WARM = "warm"
    COLD = "cold"


class PaymentStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


@dataclass(frozen=True)
class PaymentOrder:
    """Result of invoking create_payment_link (Mercado Pago Checkout Pro preference).
    See domain-entities.md Incremento 2."""

    preference_id: str
    checkout_url: str
    amount: Decimal
    description: str
    status: PaymentStatus = PaymentStatus.PENDING


@dataclass
class Lead:
    """Replaces the original DynamoDB `dmc-leads` design (DIV-13) — same conceptual
    fields, persisted in Postgres. Mutable (unlike the incremento 1 dataclasses):
    updated incrementally as the conversation progresses (BR-21)."""

    id: str
    created_at: datetime
    name: str | None = None
    email: str | None = None
    profile_summary: str = ""
    motivation: Motivation = Motivation.UNDEFINED
    motivation_detail: str = ""
    recommended_programs: list[str] = field(default_factory=list)
    payment_link_sent: bool = False
    payment_checkout_url: str | None = None
    payment_preference_id: str | None = None
    payment_confirmed: bool = False
    payment_confirmed_at: datetime | None = None
    mercadopago_payment_id: str | None = None
    score: LeadScore = LeadScore.COLD
    score_justification: str = ""
    escalated_to_human: bool = False
    service_session_id: str = ""


@dataclass(frozen=True)
class ConversationSession:
    """Local reference to a Foundry Agent Memory-managed conversation (PATTERN-20) —
    does not duplicate the message transcript, which lives in Foundry Memory."""

    session_id: str
    service_session_id: str | None
    lead_id: str | None
    created_at: datetime


class MessageRole(str, Enum):
    USER = "user"
    BOT = "bot"


@dataclass(frozen=True)
class ConversationMessage:
    """A single transcript entry, persisted only so the frontend can rehydrate visible
    messages after a page reload — added after Build and Test (real user feedback:
    a reload showed a blank chat even though the Foundry thread itself resumed
    correctly). Keyed by `conversation_id` (stable per WS connection), not by Foundry's
    rotating service_session_id. Not the agent's source of truth (PATTERN-20 still
    holds for the agent's own reasoning/context) — purely a UI-rehydration cache."""

    role: MessageRole
    content: str
    created_at: datetime


@dataclass(frozen=True)
class ConversationSummary:
    """One entry in the real conversation history list (replaces the frontend's
    hardcoded mock Sidebar history — added after user feedback). `preview` is the
    first user message, truncated for display."""

    conversation_id: str
    preview: str
    started_at: datetime
    last_activity_at: datetime


# ── Incremento 3 — BackOffice: read path + broadcast + agente de outreach ──


class DraftStatus(str, Enum):
    """BR-22: solo `PENDING` cuenta como draft activo para efectos de dedupe."""

    PENDING = "pending"
    SENT = "sent"
    DISCARDED = "discarded"


class DraftTrigger(str, Enum):
    AUTO = "auto"
    ON_DEMAND = "on_demand"


@dataclass
class OutreachDraft:
    """Ciclo de vida independiente de `Lead` (BR-22). Mutable, igual que `Lead` — el
    status cambia in-place (pending -> sent/discarded)."""

    draft_id: str
    lead_id: str
    subject: str
    body: str
    created_at: datetime
    status: DraftStatus = DraftStatus.PENDING
    trigger: DraftTrigger = DraftTrigger.ON_DEMAND
    sent_at: datetime | None = None


@dataclass(frozen=True)
class LeadEvent:
    """Efímero, nunca persistido — solo en memoria (`LeadEventPublisher`). Lleva el
    `Lead` completo (BR-29), no solo `lead_id`/score, para que `LeadBroadcaster` y el
    frontend no necesiten un lookup adicional."""

    event_type: Literal["created", "score_changed"]
    lead: Lead
