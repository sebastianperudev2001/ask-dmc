from __future__ import annotations

"""Shared Hypothesis generators for domain types."""
from hypothesis import strategies as st

from src.domain.entities import BrochureSection, SectionType

# Valid course names: non-empty, no whitespace-only strings
course_name_strategy = st.text(
    alphabet=st.characters(whitelist_categories=("Ll", "Lu", "Nd"), whitelist_characters="-_"),
    min_size=1,
    max_size=60,
).filter(lambda s: s.strip() != "")

section_type_strategy = st.sampled_from(list(SectionType))

# Non-empty content strings (realistic text, no null bytes)
content_strategy = st.text(min_size=1, max_size=2000).filter(
    lambda s: s.strip() != "" and "\x00" not in s
)

keywords_strategy = st.lists(
    st.text(min_size=1, max_size=50).filter(lambda s: s.strip() != ""),
    min_size=0,
    max_size=10,
)


def brochure_section_strategy(
    present: bool = True,
) -> st.SearchStrategy[BrochureSection]:
    return st.builds(
        BrochureSection,
        course_name=course_name_strategy,
        section_type=section_type_strategy,
        content=content_strategy if present else st.just(""),
        present=st.just(present),
        keywords=keywords_strategy,
    )
