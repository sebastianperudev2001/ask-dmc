"""Found via user report: a ParseError in the browser (`JSON.parse` rejecting a literal
`NaN`) after submitting the profile-data widget. Root cause: a course with a zero-vector
embedding makes pgvector's cosine distance (`<=>`) undefined, so `similarity_score`
becomes `float('nan')` — and Python's `json.dumps` happily emits the invalid `NaN`
literal (not valid per the JSON spec), which every browser's `JSON.parse` rejects."""
from __future__ import annotations

import math
from datetime import datetime, timezone
from decimal import Decimal

from src.api.schemas import CandidateSummary, LeadOut, OutreachDraftOut
from src.domain.models import Course, DraftStatus, DraftTrigger, Lead, OutreachDraft, RecommendationCandidate


def _course(course_id: str = "course-1") -> Course:
    return Course(
        course_id=course_id,
        name="Curso de prueba",
        description="desc",
        category="Data Science",
        curriculum=("tema 1",),
        price=Decimal("100"),
        duration_weeks=4,
        embedding=(0.0,) * 8,
    )


def test_from_candidate_sanitizes_nan_similarity_score_to_zero():
    candidate = RecommendationCandidate(course=_course(), similarity_score=float("nan"))

    summary = CandidateSummary.from_candidate(candidate)

    assert summary.similarity_score == 0.0
    assert not math.isnan(summary.similarity_score)


def test_from_candidate_keeps_a_real_similarity_score_unchanged():
    candidate = RecommendationCandidate(course=_course(), similarity_score=0.87)

    summary = CandidateSummary.from_candidate(candidate)

    assert summary.similarity_score == 0.87


# ── Incremento 3 — BackOffice ──


def test_lead_out_from_lead_maps_enum_fields_to_their_values():
    lead = Lead(id="lead-1", created_at=datetime.now(timezone.utc), name="Ana")

    out = LeadOut.from_lead(lead)

    assert out.id == "lead-1"
    assert out.motivation == "undefined"
    assert out.score == "cold"


def test_outreach_draft_out_from_draft_maps_enum_fields_to_their_values():
    draft = OutreachDraft(
        draft_id="draft-1",
        lead_id="lead-1",
        subject="s",
        body="b",
        created_at=datetime.now(timezone.utc),
        status=DraftStatus.SENT,
        trigger=DraftTrigger.AUTO,
    )

    out = OutreachDraftOut.from_draft(draft)

    assert out.status == "sent"
    assert out.trigger == "auto"
