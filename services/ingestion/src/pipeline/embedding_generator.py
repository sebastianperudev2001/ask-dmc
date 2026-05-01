from __future__ import annotations

from src.domain.entities import BrochureSection, EmbeddedChunk
from src.ports.embeddings_provider import EmbeddingsProvider


def _enrich_text(section: BrochureSection) -> str:
    return (
        f"Programa: {section.course_name}\n"
        f"Sección: {section.section_type.value}\n\n"
        f"{section.content}"
    )


class EmbeddingGenerator:
    def __init__(self, embeddings_provider: EmbeddingsProvider) -> None:
        self._provider = embeddings_provider

    def generate(self, sections: list[BrochureSection]) -> list[EmbeddedChunk]:
        chunks: list[EmbeddedChunk] = []
        for section in sections:
            enriched = _enrich_text(section)
            embedding = self._provider.embed(enriched)
            chunk = EmbeddedChunk(
                id=f"{section.course_name}_{section.section_type.value}",
                course_name=section.course_name,
                section_type=section.section_type,
                content=section.content,
                embedding=embedding,
                keywords=section.keywords[:10],
            )
            chunks.append(chunk)
        return chunks
