from __future__ import annotations

import logging

from strands import tool

from src.domain.entities import CourseMetadata

logger = logging.getLogger(__name__)

_courses: list[CourseMetadata] = []


def init_tools(courses: list[CourseMetadata]) -> None:
    global _courses
    _courses = courses


@tool
def list_courses(topic: str = "", program_type: str = "") -> str:
    """
    List DMC Institute courses from the catalog, optionally filtered by topic or program type.
    Use this to show available courses, recommend options by profile or interest area,
    or filter the catalog by category.

    Args:
        topic (str): Optional topic or keyword to filter by (e.g. "SQL", "Python", "Power BI", "data engineer")
        program_type (str): Optional program type: "curso", "diploma", or "especializacion"

    Returns:
        str: Formatted list of matching courses with their type, topics, and ID
    """
    results = _courses[:]

    if program_type:
        results = [c for c in results if c.program_type.lower() == program_type.lower()]

    if topic:
        t = topic.lower()
        results = [
            c for c in results
            if t in " ".join(c.keywords).lower()
            or t in " ".join(c.topics).lower()
            or t in c.title.lower()
            or any(t in alias.lower() for alias in c.aliases)
        ]

    if not results:
        return "No se encontraron cursos con esos filtros."

    lines = [
        f"- [{c.program_type.upper()}] {c.title}  (id: {c.id})"
        for c in results
    ]
    return f"Se encontraron {len(results)} programa(s):\n" + "\n".join(lines)


@tool
def get_course_details(course_id: str) -> str:
    """
    Get catalog metadata for a specific course by its ID.
    Use this when the user asks about a specific course by name or wants more details
    about a course returned by list_courses.

    Args:
        course_id (str): Course ID from the catalog (e.g. "diploma_data_analyst")

    Returns:
        str: Course title, type, topics, keywords, and aliases
    """
    course = next((c for c in _courses if c.id == course_id), None)
    if not course:
        ids = ", ".join(c.id for c in _courses)
        return f"Curso '{course_id}' no encontrado. IDs disponibles: {ids}"

    return (
        f"Título: {course.title}\n"
        f"Tipo: {course.program_type}\n"
        f"Temas: {', '.join(course.topics)}\n"
        f"Palabras clave: {', '.join(course.keywords)}\n"
        f"Aliases: {', '.join(course.aliases)}"
    )
