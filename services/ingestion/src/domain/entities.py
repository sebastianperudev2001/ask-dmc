from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ENV(str, Enum):
    LOCAL = "local"
    PRODUCTION = "production"


class SectionType(str, Enum):
    PRESENTACION = "presentacion"
    SOBRE_ESTE_DIPLOMA = "sobre_este_diploma"
    COMO_IMPULSAMOS = "como_impulsamos"
    POR_QUE_ESTUDIAR = "por_que_estudiar"
    OBJETIVO = "objetivo"
    A_QUIEN_DIRIGIDO = "a_quien_dirigido"
    REQUISITOS = "requisitos"
    HERRAMIENTAS = "herramientas"
    MALLA_CURRICULAR = "malla_curricular"
    PROPUESTA_CAPACITACION = "propuesta_capacitacion"
    CERTIFICACION = "certificacion"
    DOCENTES = "docentes"


@dataclass
class BrochureSection:
    course_name: str
    section_type: SectionType
    content: str
    present: bool = True
    keywords: list[str] = field(default_factory=list)


@dataclass
class EmbeddedChunk:
    id: str
    course_name: str
    section_type: SectionType
    content: str
    embedding: list[float]
    keywords: list[str]


@dataclass
class IngestionConfig:
    env: ENV
    vector_db_url: str
    local_knowledge_dir: str | None = None
    s3_bucket: str | None = None
    s3_prefix: str | None = None
    local_reports_dir: str = "reports"
    s3_reports_prefix: str | None = None
    ollama_base_url: str | None = None
    ollama_model: str | None = None
    bedrock_embeddings_model: str | None = None
    keywords_model: str = "gemma3:4b"
    ingestion_workers: int = 4


@dataclass
class IngestionError:
    course_name: str
    step: str  # "parse" | "keywords" | "embedding" | "upsert"
    message: str


@dataclass
class IngestionReport:
    env: ENV
    timestamp: str
    total_pdfs: int = 0
    processed: int = 0
    failed: int = 0
    total_sections_extracted: int = 0
    total_chunks_upserted: int = 0
    duration_seconds: float = 0.0
    errors: list[IngestionError] = field(default_factory=list)


@dataclass
class PDFResult:
    course_name: str
    success: bool
    chunks_upserted: int = 0
    sections_extracted: int = 0
    error: IngestionError | None = None
