from __future__ import annotations

import re
import unicodedata

import pdfplumber

from src.domain.entities import BrochureSection, SectionType

SECTION_PATTERNS: dict[SectionType, list[str]] = {
    SectionType.PRESENTACION:           [r"presentaci[oó]n", r"acerca de"],
    SectionType.SOBRE_ESTE_DIPLOMA:     [r"sobre este diploma", r"sobre el programa"],
    SectionType.COMO_IMPULSAMOS:        [r"c[oó]mo impulsamos", r"impulsamos tu carrera"],
    SectionType.POR_QUE_ESTUDIAR:       [r"por qu[eé] estudiar", r"por qu[eé] este"],
    SectionType.OBJETIVO:               [r"objetivo(s)?", r"metas del programa"],
    SectionType.A_QUIEN_DIRIGIDO:       [r"a qui[eé]n (va )?dirigido", r"dirigido a"],
    SectionType.REQUISITOS:             [r"requisitos", r"prerrequisitos"],
    SectionType.HERRAMIENTAS:           [r"herramientas", r"tecnolog[ií]as"],
    SectionType.MALLA_CURRICULAR:       [r"malla curricular", r"curr[ií]culum", r"contenido"],
    SectionType.PROPUESTA_CAPACITACION: [r"propuesta de capacitaci[oó]n", r"metodolog[ií]a"],
    SectionType.CERTIFICACION:          [r"certificaci[oó]n", r"certificado"],
    SectionType.DOCENTES:               [r"docentes", r"instructores", r"profesores"],
}


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _strip_header_line(content: str) -> str:
    lines = content.split("\n", 1)
    return lines[1].strip() if len(lines) > 1 else ""


class PDFParser:
    def parse(self, pdf_bytes: bytes, course_name: str) -> list[BrochureSection]:
        if not pdf_bytes:
            raise ValueError("pdf_bytes must not be empty")
        if not course_name or not course_name.strip():
            raise ValueError("course_name must not be empty")

        raw_text = self._extract_text(pdf_bytes)
        normalized = _normalize(raw_text)

        sections: dict[SectionType, BrochureSection] = {
            st: BrochureSection(
                course_name=course_name,
                section_type=st,
                content="",
                present=False,
            )
            for st in SectionType
        }

        matches: list[tuple[int, SectionType]] = []
        for section_type, patterns in SECTION_PATTERNS.items():
            for pattern in patterns:
                m = re.search(pattern, normalized, re.IGNORECASE)
                if m:
                    matches.append((m.start(), section_type))
                    break

        matches.sort(key=lambda x: x[0])

        for i, (start_pos, section_type) in enumerate(matches):
            end_pos = matches[i + 1][0] if i + 1 < len(matches) else len(normalized)
            content = _strip_header_line(normalized[start_pos:end_pos].strip())
            if content:
                sections[section_type].content = content
                sections[section_type].present = True

        return list(sections.values())

    def _extract_text(self, pdf_bytes: bytes) -> str:
        import io
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            pages = [page.extract_text() or "" for page in pdf.pages]
        return "\n".join(pages)
