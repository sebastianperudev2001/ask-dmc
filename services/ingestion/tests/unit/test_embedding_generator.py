from unittest.mock import MagicMock

from src.domain.entities import BrochureSection, SectionType
from src.pipeline.embedding_generator import EmbeddingGenerator, _enrich_text


FAKE_EMBEDDING = [0.1] * 1536


def make_section(
    course_name: str = "power-bi",
    section_type: SectionType = SectionType.OBJETIVO,
    content: str = "Aprende Power BI desde cero.",
    keywords: list[str] | None = None,
) -> BrochureSection:
    return BrochureSection(
        course_name=course_name,
        section_type=section_type,
        content=content,
        present=True,
        keywords=keywords or ["power bi", "dashboard"],
    )


def make_generator() -> EmbeddingGenerator:
    provider = MagicMock()
    provider.embed.return_value = FAKE_EMBEDDING
    return EmbeddingGenerator(provider)


class TestEmbeddingGeneratorOutput:
    def test_produces_one_chunk_per_section(self):
        gen = make_generator()
        sections = [make_section(), make_section(section_type=SectionType.HERRAMIENTAS)]
        chunks = gen.generate(sections)
        assert len(chunks) == 2

    def test_chunk_id_is_deterministic(self):
        gen = make_generator()
        section = make_section(course_name="power-bi", section_type=SectionType.OBJETIVO)
        chunks = gen.generate([section])
        assert chunks[0].id == "power-bi_objetivo"

    def test_chunk_embedding_set_from_provider(self):
        gen = make_generator()
        chunks = gen.generate([make_section()])
        assert chunks[0].embedding == FAKE_EMBEDDING

    def test_keywords_truncated_to_10(self):
        gen = make_generator()
        section = make_section(keywords=[f"kw{i}" for i in range(15)])
        chunks = gen.generate([section])
        assert len(chunks[0].keywords) == 10

    def test_content_preserved_in_chunk(self):
        gen = make_generator()
        section = make_section(content="Unique content here.")
        chunks = gen.generate([section])
        assert chunks[0].content == "Unique content here."

    def test_empty_section_list_returns_empty(self):
        gen = make_generator()
        assert gen.generate([]) == []


class TestEnrichText:
    def test_includes_course_name(self):
        section = make_section(course_name="machine-learning")
        text = _enrich_text(section)
        assert "machine-learning" in text

    def test_includes_section_type(self):
        section = make_section(section_type=SectionType.HERRAMIENTAS)
        text = _enrich_text(section)
        assert "herramientas" in text

    def test_includes_content(self):
        section = make_section(content="Aprende Python.")
        text = _enrich_text(section)
        assert "Aprende Python." in text
