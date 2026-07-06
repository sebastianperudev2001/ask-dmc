"""BR-17 (business-rules.md Incremento 2): hot/warm/cold lead scoring. Pure function —
no infrastructure dependency, deterministic (P9), so it can be property-tested with
Hypothesis without a live Postgres/agent connection."""
from __future__ import annotations

from dataclasses import dataclass

from src.domain.models import LeadScore, Motivation


@dataclass(frozen=True)
class ScoringSignals:
    """Inputs to BR-17. `has_complete_data` = name + email both present (mandatory
    signal — P10: without it, the score can never be `hot`)."""

    purchase_intent: bool
    motivation: Motivation
    profile_fits_recommendation: bool
    urgent: bool
    has_complete_data: bool


def score_lead(signals: ScoringSignals) -> tuple[LeadScore, str]:
    """Returns (score, justification). BR-17 weights: purchase intent and defined
    motivation are the strongest signals; profile fit and urgency are medium; complete
    data is mandatory for `hot` regardless of the other signals."""
    if signals.purchase_intent and signals.has_complete_data:
        return LeadScore.HOT, "Expresó intención de compra con datos de contacto completos."

    motivation_defined = signals.motivation != Motivation.UNDEFINED
    if motivation_defined and (signals.profile_fits_recommendation or signals.urgent):
        return LeadScore.WARM, "Motivación clara e interés en el programa recomendado, sin decisión de compra aún."

    if motivation_defined:
        return LeadScore.WARM, "Motivación clara, interés moderado."

    return LeadScore.COLD, "Motivación vaga o solo curiosidad exploratoria."


_SCORE_RANK: dict[LeadScore, int] = {LeadScore.COLD: 0, LeadScore.WARM: 1, LeadScore.HOT: 2}


def engagement_floor(user_message_count: int, form_completed: bool) -> tuple[LeadScore, str]:
    """BR-17b: engagement-based minimum score, standing in for the motivation/purchase-
    intent extraction score_lead() (BR-17) needs but that nothing in the agent currently
    populates. Meant to be combined via apply_score_floor() — never lowers a score on
    its own, only raises it (more messages / a completed form signal real engagement,
    they never signal disengagement)."""
    if user_message_count >= 10:
        return LeadScore.HOT, "10+ mensajes del usuario en la conversación."
    if user_message_count >= 5:
        return LeadScore.WARM, "5+ mensajes del usuario en la conversación."
    if form_completed:
        return LeadScore.WARM, "Completó el formulario de perfil (collect_profile_data)."
    return LeadScore.COLD, "Interacción inicial, sin señales suficientes."


def apply_score_floor(
    current_score: LeadScore,
    current_justification: str,
    user_message_count: int,
    form_completed: bool,
) -> tuple[LeadScore, str] | None:
    """Merges the BR-17b engagement floor with the lead's current score, monotonically
    (never downgrades). Returns the new (score, justification) if the floor exceeds the
    current score, or None if nothing changes."""
    floor_score, floor_justification = engagement_floor(user_message_count, form_completed)
    if _SCORE_RANK[floor_score] > _SCORE_RANK[current_score]:
        return floor_score, floor_justification
    return None
