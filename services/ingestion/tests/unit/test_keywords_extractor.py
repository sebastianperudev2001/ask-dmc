from unittest.mock import MagicMock

import pytest

from src.domain.entities import BrochureSection, SectionType
from src.pipeline.keywords_extractor import KeywordsExtractor


def make_section(content: str = "Some content about data science.") -> BrochureSection:
    return BrochureSection(
        course_name="test-course",
        section_type=SectionType.OBJETIVO,
        content=content,
        present=True,
    )


def make_extractor(return_value: str) -> KeywordsExtractor:
    llm = MagicMock()
    llm.complete.return_value = return_value
    return KeywordsExtractor(llm)


class TestKeywordsExtractorSuccess:
    def test_returns_parsed_keywords(self):
        extractor = make_extractor('["machine learning", "python", "data"]')
        section = make_section()
        result = extractor.extract_keywords([section])
        assert result[0].keywords == ["machine learning", "python", "data"]

    def test_strips_markdown_code_fence(self):
        extractor = make_extractor('```json\n["ml", "ai"]\n```')
        section = make_section()
        result = extractor.extract_keywords([section])
        assert result[0].keywords == ["ml", "ai"]

    def test_truncates_to_10_keywords(self):
        many = json_list(15)
        extractor = make_extractor(many)
        section = make_section()
        result = extractor.extract_keywords([section])
        assert len(result[0].keywords) == 10

    def test_processes_multiple_sections(self):
        llm = MagicMock()
        llm.complete.side_effect = ['["kw1"]', '["kw2"]']
        extractor = KeywordsExtractor(llm)
        sections = [make_section("content1"), make_section("content2")]
        sections[1].section_type = SectionType.HERRAMIENTAS
        result = extractor.extract_keywords(sections)
        assert result[0].keywords == ["kw1"]
        assert result[1].keywords == ["kw2"]


class TestKeywordsExtractorFailure:
    def test_returns_empty_list_after_3_failures(self):
        llm = MagicMock()
        llm.complete.side_effect = Exception("timeout")
        extractor = KeywordsExtractor(llm)
        section = make_section()
        result = extractor.extract_keywords([section])
        assert result[0].keywords == []
        assert llm.complete.call_count == 3

    def test_retries_on_json_parse_error_then_succeeds(self):
        llm = MagicMock()
        llm.complete.side_effect = ["not-json", '["ok"]']
        extractor = KeywordsExtractor(llm)
        section = make_section()
        result = extractor.extract_keywords([section])
        assert result[0].keywords == ["ok"]

    def test_keywords_never_none_on_failure(self):
        llm = MagicMock()
        llm.complete.side_effect = ValueError("bad")
        extractor = KeywordsExtractor(llm)
        section = make_section()
        result = extractor.extract_keywords([section])
        assert result[0].keywords is not None
        assert isinstance(result[0].keywords, list)


def json_list(n: int) -> str:
    import json
    return json.dumps([f"kw{i}" for i in range(n)])
