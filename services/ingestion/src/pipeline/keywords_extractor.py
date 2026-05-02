from __future__ import annotations

import logging

from pydantic import BaseModel

from src.domain.entities import BrochureSection, SectionType
from src.ports.llm_provider import LLMProvider

logger = logging.getLogger("ingestion")

KEYWORDS_PROMPT = """\
Dado el contenido de un brochure educativo, extrae entre 5 y 10 keywords o frases clave
que representen los temas principales del programa. Responde SOLO con un objeto JSON.

Contenido:
{content}"""

MAX_KEYWORDS = 10
MAX_SECTION_CHARS = 300

# Sections used to extract document-level keywords
_KEYWORD_SECTIONS = {
    SectionType.PRESENTACION,
    SectionType.SOBRE_ESTE_DIPLOMA,
    SectionType.OBJETIVO,
    SectionType.A_QUIEN_DIRIGIDO,
    SectionType.MALLA_CURRICULAR,
}


class KeywordsResponse(BaseModel):
    keywords: list[str]


class KeywordsExtractor:
    def __init__(self, llm_provider: LLMProvider) -> None:
        self._llm = llm_provider

    def extract_keywords(self, sections: list[BrochureSection]) -> list[str]:
        keyword_sections = [s for s in sections if s.section_type in _KEYWORD_SECTIONS]
        combined = "\n\n".join(
            f"[{s.section_type.value}]: {s.content[:MAX_SECTION_CHARS]}"
            for s in keyword_sections
        )
        prompt = KEYWORDS_PROMPT.format(content=combined)
        try:
            response = self._llm.complete(
                prompt, format=KeywordsResponse.model_json_schema()
            )
            result = KeywordsResponse.model_validate_json(response)
            return result.keywords[:MAX_KEYWORDS]
        except Exception as exc:
            logger.warning("keywords extraction failed: %s", exc)
            return []
