"""Property-based tests (Hypothesis) for BR-17b lead-scoring floors — P9 (determinism)
and the monotonic never-downgrades invariant (business-logic-model.md Section 12,
Incremento 2/3). Each ChatAgentClient call site computes its own floor and merges it
via apply_score_floor(); a lead's score only ever goes up."""
from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from src.domain.lead_scoring import apply_score_floor, message_count_floor
from src.domain.models import LeadScore

_RANK = {LeadScore.COLD: 0, LeadScore.WARM: 1, LeadScore.HOT: 2}


def test_message_count_floor_below_5_is_none():
    assert message_count_floor(4) is None


def test_message_count_floor_at_5_is_warm():
    score, _ = message_count_floor(5)
    assert score == LeadScore.WARM


def test_message_count_floor_at_10_is_hot():
    score, _ = message_count_floor(10)
    assert score == LeadScore.HOT


@given(count=st.integers(min_value=0, max_value=4))
def test_message_count_floor_always_none_below_5(count):
    assert message_count_floor(count) is None


@given(count=st.integers(min_value=5, max_value=9))
def test_message_count_floor_always_warm_between_5_and_9(count):
    score, _ = message_count_floor(count)
    assert score == LeadScore.WARM


@given(count=st.integers(min_value=10, max_value=1000))
def test_message_count_floor_always_hot_at_or_above_10(count):
    score, _ = message_count_floor(count)
    assert score == LeadScore.HOT


_lead_scores = st.sampled_from(list(LeadScore))


@given(current_score=_lead_scores, floor_score=_lead_scores)
def test_apply_score_floor_never_downgrades(current_score, floor_score):
    result = apply_score_floor(current_score, floor_score, "some justification")
    new_score = result[0] if result is not None else current_score
    assert _RANK[new_score] >= _RANK[current_score]


def test_apply_score_floor_returns_none_when_floor_does_not_exceed_current():
    assert apply_score_floor(LeadScore.HOT, LeadScore.WARM, "not enough") is None


def test_apply_score_floor_upgrades_cold_to_warm():
    result = apply_score_floor(LeadScore.COLD, LeadScore.WARM, "5+ mensajes")
    assert result == (LeadScore.WARM, "5+ mensajes")
