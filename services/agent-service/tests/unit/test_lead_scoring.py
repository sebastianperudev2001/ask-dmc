"""Property-based tests (Hypothesis) for BR-17 lead scoring — P9 (determinism) and
P10 (hot requires complete data), business-logic-model.md Section 12 (Incremento 2)."""
from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from src.domain.lead_scoring import ScoringSignals, apply_score_floor, engagement_floor, score_lead
from src.domain.models import LeadScore, Motivation

_signals = st.builds(
    ScoringSignals,
    purchase_intent=st.booleans(),
    motivation=st.sampled_from(list(Motivation)),
    profile_fits_recommendation=st.booleans(),
    urgent=st.booleans(),
    has_complete_data=st.booleans(),
)


# P9 — Idempotence/determinism: same signals always produce the same score.
@given(signals=_signals)
def test_p9_scoring_is_deterministic(signals):
    first = score_lead(signals)
    second = score_lead(signals)
    assert first == second


# P10 — Invariant: score is never `hot` if data is incomplete, regardless of other signals.
@given(signals=_signals.filter(lambda s: not s.has_complete_data))
def test_p10_hot_requires_complete_data(signals):
    score, _justification = score_lead(signals)
    assert score != LeadScore.HOT


def test_purchase_intent_with_complete_data_is_hot():
    signals = ScoringSignals(
        purchase_intent=True,
        motivation=Motivation.GROWTH,
        profile_fits_recommendation=True,
        urgent=False,
        has_complete_data=True,
    )
    score, _ = score_lead(signals)
    assert score == LeadScore.HOT


def test_undefined_motivation_without_purchase_intent_is_cold():
    signals = ScoringSignals(
        purchase_intent=False,
        motivation=Motivation.UNDEFINED,
        profile_fits_recommendation=False,
        urgent=False,
        has_complete_data=True,
    )
    score, _ = score_lead(signals)
    assert score == LeadScore.COLD


# ── BR-17b — engagement floor (message-count based, in lieu of the motivation/purchase-
# intent extraction score_lead() needs but nothing currently populates) ─────────────────


def test_engagement_floor_below_5_messages_without_form_is_cold():
    score, _ = engagement_floor(user_message_count=4, form_completed=False)
    assert score == LeadScore.COLD


def test_engagement_floor_at_5_messages_is_warm():
    score, _ = engagement_floor(user_message_count=5, form_completed=False)
    assert score == LeadScore.WARM


def test_engagement_floor_at_10_messages_is_hot():
    score, _ = engagement_floor(user_message_count=10, form_completed=False)
    assert score == LeadScore.HOT


def test_engagement_floor_form_completed_alone_is_warm():
    score, _ = engagement_floor(user_message_count=0, form_completed=True)
    assert score == LeadScore.WARM


@given(count=st.integers(min_value=0, max_value=4))
def test_engagement_floor_never_warm_below_5_messages_without_form(count):
    score, _ = engagement_floor(user_message_count=count, form_completed=False)
    assert score == LeadScore.COLD


@given(count=st.integers(min_value=10, max_value=1000))
def test_engagement_floor_always_hot_at_or_above_10_messages(count):
    score, _ = engagement_floor(user_message_count=count, form_completed=True)
    assert score == LeadScore.HOT


_lead_scores = st.sampled_from(list(LeadScore))
_message_counts = st.integers(min_value=0, max_value=20)


# Monotonic invariant (BR-17b): applying the engagement floor never lowers the score.
@given(current_score=_lead_scores, count=_message_counts, form_completed=st.booleans())
def test_apply_score_floor_never_downgrades(current_score, count, form_completed):
    result = apply_score_floor(current_score, "existing justification", count, form_completed)
    if result is None:
        new_score = current_score
    else:
        new_score, _ = result
    rank = {LeadScore.COLD: 0, LeadScore.WARM: 1, LeadScore.HOT: 2}
    assert rank[new_score] >= rank[current_score]


def test_apply_score_floor_returns_none_when_floor_does_not_exceed_current():
    result = apply_score_floor(LeadScore.HOT, "already hot", user_message_count=0, form_completed=False)
    assert result is None


def test_apply_score_floor_upgrades_cold_to_warm_at_5_messages():
    result = apply_score_floor(LeadScore.COLD, "", user_message_count=5, form_completed=False)
    assert result is not None
    score, justification = result
    assert score == LeadScore.WARM
    assert justification
