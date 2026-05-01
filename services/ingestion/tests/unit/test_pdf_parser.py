from unittest.mock import MagicMock, patch

import pytest

from src.domain.entities import SectionType
from src.pipeline.pdf_parser import PDFParser


MINIMAL_PDF_TEXT = """
Presentación
Somos DMC, una academia de datos.

Objetivo
Formar profesionales en ciencia de datos.

Requisitos
Conocimientos básicos de programación.
"""

ALL_SECTIONS_TEXT = "\n\n".join([
    "Presentación\nContenido presentacion.",
    "Sobre este diploma\nContenido sobre diploma.",
    "Cómo impulsamos\nContenido impulso.",
    "Por qué estudiar\nContenido por que.",
    "Objetivo\nContenido objetivo.",
    "A quién va dirigido\nContenido dirigido.",
    "Requisitos\nContenido requisitos.",
    "Herramientas\nContenido herramientas.",
    "Malla curricular\nContenido malla.",
    "Propuesta de capacitación\nContenido propuesta.",
    "Certificación\nContenido certificacion.",
    "Docentes\nContenido docentes.",
])


def make_parser_with_text(text: str) -> PDFParser:
    parser = PDFParser()
    parser._extract_text = MagicMock(return_value=text)
    return parser


class TestPDFParserOutputShape:
    def test_always_returns_12_sections(self):
        parser = make_parser_with_text(MINIMAL_PDF_TEXT)
        result = parser.parse(b"fake", "test-course")
        assert len(result) == 12

    def test_all_12_section_types_present(self):
        parser = make_parser_with_text(MINIMAL_PDF_TEXT)
        result = parser.parse(b"fake", "test-course")
        section_types = {s.section_type for s in result}
        assert section_types == set(SectionType)

    def test_section_types_are_unique(self):
        parser = make_parser_with_text(MINIMAL_PDF_TEXT)
        result = parser.parse(b"fake", "test-course")
        types = [s.section_type for s in result]
        assert len(types) == len(set(types))

    def test_course_name_propagated_to_all_sections(self):
        parser = make_parser_with_text(MINIMAL_PDF_TEXT)
        result = parser.parse(b"fake", "mi-curso")
        assert all(s.course_name == "mi-curso" for s in result)


class TestPDFParserContentExtraction:
    def test_detected_sections_are_marked_present(self):
        parser = make_parser_with_text(MINIMAL_PDF_TEXT)
        result = parser.parse(b"fake", "test-course")
        by_type = {s.section_type: s for s in result}
        assert by_type[SectionType.PRESENTACION].present is True
        assert by_type[SectionType.OBJETIVO].present is True
        assert by_type[SectionType.REQUISITOS].present is True

    def test_missing_sections_are_not_present(self):
        parser = make_parser_with_text(MINIMAL_PDF_TEXT)
        result = parser.parse(b"fake", "test-course")
        by_type = {s.section_type: s for s in result}
        assert by_type[SectionType.DOCENTES].present is False
        assert by_type[SectionType.CERTIFICACION].present is False

    def test_not_present_sections_have_empty_content(self):
        parser = make_parser_with_text(MINIMAL_PDF_TEXT)
        result = parser.parse(b"fake", "test-course")
        for s in result:
            if not s.present:
                assert s.content == ""

    def test_all_sections_detected_when_all_headers_present(self):
        parser = make_parser_with_text(ALL_SECTIONS_TEXT)
        result = parser.parse(b"fake", "full-course")
        assert all(s.present for s in result)

    def test_present_sections_have_non_empty_content(self):
        parser = make_parser_with_text(ALL_SECTIONS_TEXT)
        result = parser.parse(b"fake", "full-course")
        for s in result:
            if s.present:
                assert s.content.strip() != ""


class TestPDFParserInputValidation:
    def test_raises_on_empty_bytes(self):
        parser = PDFParser()
        with pytest.raises(ValueError, match="pdf_bytes"):
            parser.parse(b"", "course")

    def test_raises_on_empty_course_name(self):
        parser = PDFParser()
        with pytest.raises(ValueError, match="course_name"):
            parser.parse(b"fake", "")

    def test_raises_on_whitespace_course_name(self):
        parser = PDFParser()
        with pytest.raises(ValueError, match="course_name"):
            parser.parse(b"fake", "   ")
