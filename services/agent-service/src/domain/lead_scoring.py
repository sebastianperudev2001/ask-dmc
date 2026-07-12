"""BR-17b (business-rules.md Incremento 2/3): hot/warm/cold lead scoring. Pure
functions — no infrastructure dependency, deterministic (P9), so they can be
property-tested with Hypothesis without a live Postgres/agent connection.

Each ChatAgentClient call site (record_user_message, _flag_purchase_intent,
_collect_profile_data — see chat_agent_client.py) computes its own floor and merges it
via apply_score_floor(). A lead's score only ever goes up, never down, across these
independent signals."""
from __future__ import annotations

from src.domain.models import LeadScore

_SCORE_RANK: dict[LeadScore, int] = {LeadScore.COLD: 0, LeadScore.WARM: 1, LeadScore.HOT: 2}


def message_count_floor(user_message_count: int) -> tuple[LeadScore, str] | None:
    """Engagement-based minimum score from raw message volume alone. Returns None
    below the first threshold — nothing to raise yet."""
    if user_message_count >= 10:
        return LeadScore.HOT, "10+ mensajes del usuario en la conversación."
    if user_message_count >= 5:
        return LeadScore.WARM, "5+ mensajes del usuario en la conversación."
    return None


def apply_score_floor(
    current_score: LeadScore,
    floor_score: LeadScore,
    floor_justification: str,
) -> tuple[LeadScore, str] | None:
    """Merges a computed floor with the lead's current score, monotonically (never
    downgrades). Returns the new (score, justification) if the floor exceeds the
    current score, or None if nothing changes."""
    if _SCORE_RANK[floor_score] > _SCORE_RANK[current_score]:
        return floor_score, floor_justification
    return None
