from __future__ import annotations

import re
import unicodedata
from src.domain.entities import BrochureSection, SectionType

# All patterns are anchored to line starts (re.MULTILINE) so they only match
# actual section headers, not the same words appearing inside body text.
SECTION_PATTERNS: dict[SectionType, list[str]] = {
    SectionType.PRESENTACION: [r"^presentaci[oó]n", r"^acerca de"],
    SectionType.SOBRE_ESTE_DIPLOMA: [
        r"^sobre (este|esta|el) (diploma|programa|curso|especializ)",
    ],
    SectionType.POR_QUE_ESTUDIAR: [
        r"^¿?porqu[eé] estudiar",   # "Porqué" written as one word (all DMC brochures)
        r"^¿?por qu[eé] estudiar",  # two-word fallback
        r"^¿?por qu[eé] (este|esta)",
    ],
    SectionType.OBJETIVO: [r"^objetivo(s)?", r"^metas del programa"],
    SectionType.A_QUIEN_DIRIGIDO: [
        r"^¿?a qui[eé]n",  # "dirigido" omitted — can get cut across page boundaries
        r"^dirigido a",
    ],
    SectionType.REQUISITOS: [r"^¿?cu[aá]les son los requisitos", r"^requisitos", r"^prerrequisitos"],
    SectionType.HERRAMIENTAS: [r"^herramientas\s*$", r"^tecnolog[ií]as\s*$"],
    SectionType.MALLA_CURRICULAR: [r"^malla curricular", r"^curr[ií]culum", r"^plan de estudios"],
    SectionType.PROPUESTA_CAPACITACION: [
        r"^(nuestra )?propuesta de capacitaci[oó]n",
        r"^metodolog[ií]a dmc",
    ],
    SectionType.CERTIFICACION: [r"^certificaci[oó]n", r"^certificado"],
    SectionType.DOCENTES: [r"^docentes?( expertos?)?$", r"^instructores", r"^profesores"],
}

# Page headers like "_DIPLOMA ADVANCED DATA ANALYST" repeat on every page.
# They start with an underscore followed by uppercase text — strip them so they
# don't bleed into section content.
_PAGE_HEADER_RE = re.compile(r"^_[A-ZÁÉÍÓÚÜÑ][^\n]*\n?", re.MULTILINE)


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _strip_page_headers(text: str) -> str:
    return _PAGE_HEADER_RE.sub("", text)


def _strip_header_line(content: str) -> str:
    lines = content.split("\n", 1)
    return lines[1].strip() if len(lines) > 1 else ""


def _parse_sobre_section(content: str) -> str:
    """Convert the sobre_este_diploma infographic into readable number-label pairs.

    pdfplumber reads multi-column grids row by row, producing output like:
        128 75 01          <- row 1 numbers
        33                 <- row 2 numbers
        horas talleres proyecto para   <- row 1 label words, part 1
        sesiones                       <- row 2 label words
        académicas prácticos tu portafolio  <- row 1 label words, part 2

    This function reconstructs: "128 horas académicas, 75 talleres prácticos,
    1 proyecto para tu portafolio, 33 sesiones".
    """
    lines = [line.strip() for line in content.split("\n") if line.strip()]

    number_rows: list[list[int]] = []
    label_lines: list[str] = []
    in_labels = False

    for line in lines:
        tokens = line.split()
        if not in_labels and tokens and all(t.isdigit() for t in tokens):
            number_rows.append([int(t) for t in tokens])
        else:
            in_labels = True
            # Stop at question-mark lines or long lines — those are paragraph text
            if line.startswith("¿") or len(line) > 60:
                break
            label_lines.append(line)

    if not number_rows or not label_lines:
        return content

    n_rows = len(number_rows)

    # Label lines interleave by row: row0_part1, row1_part1, row0_part2, ...
    row_label_groups: list[list[str]] = [[] for _ in range(n_rows)]
    for i, label_line in enumerate(label_lines):
        row_label_groups[i % n_rows].append(label_line)

    pairs: list[str] = []
    for row_nums, row_label_lines in zip(number_rows, row_label_groups):
        N = len(row_nums)
        col_labels = [""] * N
        for label_line in row_label_lines:
            words = label_line.split()
            if not words:
                continue
            # Distribute words across N columns; extra words go to the rightmost columns.
            per_col, extra = divmod(len(words), N)
            offset = 0
            for col in range(N):
                count = per_col + (1 if col >= N - extra else 0)
                chunk = " ".join(words[offset : offset + count])
                col_labels[col] = (col_labels[col] + " " + chunk).strip()
                offset += count
        for num, label in zip(row_nums, col_labels):
            pairs.append(f"{num} {label}")

    return ", ".join(pairs)


def _extract_text(pdf_bytes: bytes) -> str:
    # Why am I importing these libraries inside this function ?
    # This is lazy loading. It's only imported when this functioned is executed
    import io
    import pdfplumber
    # also to consider that if it's used more than once, it caches the result, so it's not a performance issue

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        pages = [page.extract_text() or "" for page in pdf.pages]
    return "\n".join(pages)


class PDFParser:
    def parse(self, pdf_bytes: bytes, course_name: str) -> list[BrochureSection]:
        # Input validations
        if not course_name or not course_name.strip():
            raise ValueError("Course name must be provided")
        if not pdf_bytes:
            raise ValueError(f"PDF document is required for course: {course_name}")

        raw_text = _extract_text(pdf_bytes)
        normalized = _normalize(raw_text)
        normalized = _strip_page_headers(normalized)

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
                m = re.search(pattern, normalized, re.IGNORECASE | re.MULTILINE)
                if m:
                    matches.append((m.start(), section_type))
                    break

        matches.sort(key=lambda x: x[0])

        for i, (start_pos, section_type) in enumerate(matches):
            end_pos = matches[i + 1][0] if i + 1 < len(matches) else len(normalized)
            content = _strip_header_line(normalized[start_pos:end_pos].strip())
            if content:
                if section_type == SectionType.SOBRE_ESTE_DIPLOMA:
                    content = _parse_sobre_section(content)
                sections[section_type].content = content
                sections[section_type].present = True

        return list(sections.values())
