from __future__ import annotations
import logging

logger = logging.getLogger("ingestion.embedding")

from src.domain.entities import BrochureSection, EmbeddedChunk
from src.ports.embeddings_provider import EmbeddingsProvider

_MAX_CHARS = 2000
_OVERLAP = 200


def _split_text(text: str) -> list[str]:
    if len(text) <= _MAX_CHARS:
        return [text]
    parts = []
    start = 0
    while start < len(text):
        parts.append(text[start : start + _MAX_CHARS])
        start += _MAX_CHARS - _OVERLAP
    return parts


class EmbeddingGenerator:
    def __init__(self, embeddings_provider: EmbeddingsProvider) -> None:
        self._provider = embeddings_provider

    def generate(
        self, sections: list[BrochureSection], keywords: list[str]
    ) -> list[EmbeddedChunk]:
        chunks: list[EmbeddedChunk] = []
        for section in sections:
            header = f"[{section.section_type.value}]\n"
            parts = _split_text(header + section.content)
            for i, text in enumerate(parts):
                chunk_id = (
                    f"{section.course_name}__{section.section_type.value}"
                    if len(parts) == 1
                    else f"{section.course_name}__{section.section_type.value}__{i}"
                )
                try:
                    embedding = self._provider.embed(text)
                    logger.info(
                        "Embedding successful: %s/%s (part %d/%d)",
                        section.course_name, section.section_type.value, i + 1, len(parts),
                    )
                except Exception as e:
                    logger.error(
                        "Embedding failed for %s/%s (part %d/%d): %s",
                        section.course_name, section.section_type.value, i + 1, len(parts), str(e),
                    )
                    raise
                chunks.append(
                    EmbeddedChunk(
                        id=chunk_id,
                        course_name=section.course_name,
                        content=text,
                        embedding=embedding,
                        keywords=keywords,
                    )
                )
        return chunks
