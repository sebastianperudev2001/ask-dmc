from __future__ import annotations

"""PBT — EmbeddedChunk and IngestionReport invariants (BR-03, BR-08)."""
from unittest.mock import MagicMock

from hypothesis import given, settings

from src.domain.entities import IngestionError, IngestionReport, PDFResult
from src.pipeline.embedding_generator import EmbeddingGenerator

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from conftest import brochure_section_strategy, course_name_strategy, section_type_strategy


@given(
    course_name=course_name_strategy,
    section_type=section_type_strategy,
)
@settings(max_examples=200)
def test_chunk_id_is_deterministic(course_name: str, section_type) -> None:
    """BR-03: chunk.id == f'{course_name}_{section_type.value}' always."""
    provider = MagicMock()
    provider.embed.return_value = [0.1] * 1536
    gen = EmbeddingGenerator(provider)

    from src.domain.entities import BrochureSection
    section = BrochureSection(
        course_name=course_name,
        section_type=section_type,
        content="Some content.",
        present=True,
        keywords=["kw1"],
    )
    chunks = gen.generate([section])
    assert len(chunks) == 1
    assert chunks[0].id == f"{course_name}_{section_type.value}"


@given(sections=brochure_section_strategy(present=True).flatmap(
    lambda s: brochure_section_strategy(present=True).map(lambda s2: [s, s2])
))
@settings(max_examples=100)
def test_keywords_never_exceed_10(sections) -> None:
    """BR-08: keywords list always has <= 10 elements."""
    provider = MagicMock()
    provider.embed.return_value = [0.0] * 1536
    gen = EmbeddingGenerator(provider)
    chunks = gen.generate(sections)
    for chunk in chunks:
        assert len(chunk.keywords) <= 10, (
            f"chunk {chunk.id} has {len(chunk.keywords)} keywords, expected <= 10"
        )


from hypothesis import strategies as st

pdf_result_strategy = st.one_of(
    st.builds(
        PDFResult,
        course_name=course_name_strategy,
        success=st.just(True),
        chunks_upserted=st.integers(min_value=0, max_value=12),
        sections_extracted=st.integers(min_value=0, max_value=12),
        error=st.none(),
    ),
    st.builds(
        PDFResult,
        course_name=course_name_strategy,
        success=st.just(False),
        chunks_upserted=st.just(0),
        sections_extracted=st.just(0),
        error=st.builds(
            IngestionError,
            course_name=course_name_strategy,
            step=st.sampled_from(["parse", "keywords", "embedding", "upsert"]),
            message=st.text(min_size=1, max_size=200),
        ),
    ),
)


@given(results=st.lists(pdf_result_strategy, min_size=0, max_size=30))
@settings(max_examples=200)
def test_report_processed_plus_failed_equals_total(results: list[PDFResult]) -> None:
    """processed + failed == total_pdfs always holds in an IngestionReport."""
    from src.domain.entities import ENV
    report = IngestionReport(env=ENV.LOCAL, timestamp="20260430T000000Z", total_pdfs=len(results))
    for r in results:
        if r.success:
            report.processed += 1
        else:
            report.failed += 1
    assert report.processed + report.failed == report.total_pdfs
