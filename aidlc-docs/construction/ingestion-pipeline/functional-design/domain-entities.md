# Domain Entities — ingestion-pipeline

**Fecha**: 2026-04-29 (v2 — deterministic extraction + ENV support)

---

## ENV (Enum)

Controla la fuente de datos y los proveedores de embeddings/LLM usados en el pipeline.

```python
from enum import Enum

class ENV(str, Enum):
    LOCAL      = "local"       # Filesystem local + Ollama
    PRODUCTION = "production"  # S3 + Bedrock
```

---

## IngestionConfig

Configuración del pipeline derivada del ENV activo.

```python
from dataclasses import dataclass

@dataclass
class IngestionConfig:
    env: ENV
    # Storage
    local_knowledge_dir: str | None   # e.g. "knowledge_source/" — solo LOCAL
    s3_bucket: str | None             # e.g. "dmc-knowledge-base" — solo PRODUCTION
    s3_prefix: str | None             # e.g. "brochures/" — solo PRODUCTION
    # Reports
    local_reports_dir: str            # Directorio donde guardar IngestionReport (JSON)
    s3_reports_prefix: str | None     # Prefix S3 para reportes — solo PRODUCTION
    # Embeddings model
    ollama_model: str | None          # e.g. "nomic-embed-text" — solo LOCAL
    bedrock_embeddings_model: str | None  # e.g. "amazon.titan-embed-text-v2:0" — solo PRODUCTION
    # Keywords LLM
    keywords_model: str               # e.g. "claude-haiku-4-5" (prod) | "gemma3:4b" (local)
```

---

## SectionType (Enum)

Las 12 secciones que se extraen de cada brochure PDF mediante parser determinístico.

```python
class SectionType(str, Enum):
    PRESENTACION           = "presentacion"
    SOBRE_ESTE_DIPLOMA     = "sobre_este_diploma"
    COMO_IMPULSAMOS        = "como_impulsamos"
    POR_QUE_ESTUDIAR       = "por_que_estudiar"
    OBJETIVO               = "objetivo"
    A_QUIEN_DIRIGIDO       = "a_quien_dirigido"
    REQUISITOS             = "requisitos"
    HERRAMIENTAS           = "herramientas"
    MALLA_CURRICULAR       = "malla_curricular"
    PROPUESTA_CAPACITACION = "propuesta_capacitacion"
    CERTIFICACION          = "certificacion"
    DOCENTES               = "docentes"
```

---

## BrochureSection

Representa una sección extraída de un brochure PDF por el parser determinístico.

```python
@dataclass
class BrochureSection:
    course_name: str         # Nombre del archivo PDF sin extensión
    section_type: SectionType
    content: str             # Texto extraído por el parser determinístico
    present: bool = True     # False si la sección no existe en el PDF
```

**Invariantes**:
- `course_name` es el nombre del archivo PDF sin extensión
- `content` puede estar vacío si `present=False`
- El parser produce exactamente 12 instancias por PDF (una por `SectionType`)
- No se usa ningún LLM en la extracción de secciones

---

## EmbeddedChunk

Unidad de almacenamiento en el Vector DB. Cada `BrochureSection` con `present=True` produce exactamente un `EmbeddedChunk`.

```python
@dataclass
class EmbeddedChunk:
    id: str                     # UUID determinístico: f"{course_name}_{section_type}"
    course_name: str
    section_type: SectionType
    content: str
    embedding: list[float]      # Generado por Ollama (local) o Bedrock (producción)
    keywords: list[str]         # 3-5 términos extraídos por cheap LLM (Haiku / Gemma 4)
```

**Invariantes**:
- `id` es determinístico — re-procesar el mismo PDF produce el mismo `id`, permitiendo upsert idempotente
- `embedding` nunca es vacío — si falla la generación, el chunk no se persiste
- `keywords` tiene entre 0 y 10 términos; nunca es None

---

## CourseMetadata

Mapeo entre nombre de curso y sus perfiles prioritarios para ranking de búsqueda.

```python
@dataclass
class CourseMetadata:
    course_name: str
    priority_profiles: list[str]
```

---

## IngestionReport

Resultado del pipeline completo. Se persiste como archivo JSON (no en DB).

```python
@dataclass
class IngestionReport:
    total_pdfs: int
    processed: int
    failed: int
    total_sections_extracted: int
    total_chunks_upserted: int
    errors: list[IngestionError]
    duration_seconds: float
    env: ENV
    timestamp: str               # ISO 8601

@dataclass
class IngestionError:
    course_name: str
    step: str                    # "parse" | "keywords" | "embedding" | "upsert"
    message: str
```
