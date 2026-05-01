from __future__ import annotations

import json
import logging
import time

from src.domain.entities import BrochureSection
from src.ports.llm_provider import LLMProvider

logger = logging.getLogger("ingestion")

KEYWORDS_PROMPT = """\
Dado este texto de un brochure educativo, extrae entre 3 y 5 keywords o frases clave
que representen los temas principales. Responde solo con una lista JSON de strings.

Texto: {content}"""

MAX_KEYWORDS = 10
MAX_RETRIES = 3
BACKOFF_BASE = 1.0


class KeywordsExtractor:
    def __init__(self, llm_provider: LLMProvider) -> None:
        self._llm = llm_provider

    def extract_keywords(self, sections: list[BrochureSection]) -> list[BrochureSection]:
        for section in sections:
            section.keywords = self._extract_for_section(section)
        return sections

    def _extract_for_section(self, section: BrochureSection) -> list[str]:
        prompt = KEYWORDS_PROMPT.format(content=section.content)
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                response = self._llm.complete(prompt)
                keywords = self._parse_keywords(response)
                return keywords[:MAX_KEYWORDS]
            except Exception as exc:
                if attempt == MAX_RETRIES:
                    logger.warning(
                        "keywords failed for %s/%s after %d attempts: %s",
                        section.course_name,
                        section.section_type.value,
                        MAX_RETRIES,
                        exc,
                    )
                    return []
                time.sleep(BACKOFF_BASE * (2 ** (attempt - 1)))
        return []

    def _parse_keywords(self, response: str) -> list[str]:
        text = response.strip()
        # Strip markdown code fences if present
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        parsed = json.loads(text)
        if not isinstance(parsed, list):
            raise ValueError("LLM did not return a JSON list")
        return [str(k) for k in parsed if str(k).strip()]
