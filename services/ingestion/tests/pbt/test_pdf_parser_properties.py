from __future__ import annotations

"""PBT — PDFParser invariants (BR-01, BR-02, BR-04)."""
from unittest.mock import MagicMock

from hypothesis import given, settings
from hypothesis import strategies as st

from src.domain.entities import SectionType
from src.pipeline.pdf_parser import PDFParser

# Strategies for realistic PDF text
header_line = st.sampled_from([
    "Presentación", "Objetivo", "Requisitos", "Docentes",
    "Malla curricular", "Certificación", "Herramientas",
    "Sobre este diploma", "A quién va dirigido",
    "Por qué estudiar", "Propuesta de capacitación", "Cómo impulsamos",
])
paragraph = st.text(
    alphabet=st.characters(whitelist_categories=("Ll", "Lu", "Nd", "Zs"), whitelist_characters=".,;:()"),
    min_size=10,
    max_size=200,
)

pdf_text_strategy = st.lists(
    st.tuples(header_line, paragraph), min_size=1, max_size=12
).map(lambda pairs: "\n\n".join(f"{h}\n{p}" for h, p in pairs))

course_name_strategy = st.text(
    alphabet=st.characters(whitelist_categories=("Ll", "Lu", "Nd"), whitelist_characters="-"),
    min_size=1,
    max_size=50,
).filter(lambda s: s.strip())


def make_parser(text: str) -> PDFParser:
    parser = PDFParser()
    parser._extract_text = MagicMock(return_value=text)
    return parser


@given(text=pdf_text_strategy, course_name=course_name_strategy)
@settings(max_examples=100)
def test_always_produces_exactly_12_sections(text: str, course_name: str) -> None:
    """BR-01: parser always returns exactly 12 BrochureSection objects."""
    parser = make_parser(text)
    result = parser.parse(b"fake", course_name)
    assert len(result) == 12


@given(text=pdf_text_strategy, course_name=course_name_strategy)
@settings(max_examples=100)
def test_all_12_section_types_represented(text: str, course_name: str) -> None:
    """All 12 SectionType values appear exactly once."""
    parser = make_parser(text)
    result = parser.parse(b"fake", course_name)
    section_types = [s.section_type for s in result]
    assert sorted(section_types, key=lambda x: x.value) == sorted(SectionType, key=lambda x: x.value)


@given(text=pdf_text_strategy, course_name=course_name_strategy)
@settings(max_examples=100)
def test_not_present_sections_have_empty_content(text: str, course_name: str) -> None:
    """BR-02: sections with present=False always have content == ''."""
    parser = make_parser(text)
    result = parser.parse(b"fake", course_name)
    for section in result:
        if not section.present:
            assert section.content == "", (
                f"Section {section.section_type} has present=False but non-empty content"
            )


@given(text=pdf_text_strategy, course_name=course_name_strategy)
@settings(max_examples=100)
def test_course_name_preserved_in_all_sections(text: str, course_name: str) -> None:
    """course_name is propagated to all 12 sections unchanged."""
    parser = make_parser(text)
    result = parser.parse(b"fake", course_name)
    for section in result:
        assert section.course_name == course_name
