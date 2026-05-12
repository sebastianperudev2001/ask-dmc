# AI-DLC State Tracking

## Project Information
- **Project Name**: DMC Sales Agent
- **Project Type**: Greenfield
- **Start Date**: 2026-04-23T00:00:00Z
- **Current Stage**: CONSTRUCTION - unit-1: ingestion-pipeline

## Workspace State
- **Existing Code**: No
- **Reverse Engineering Needed**: No
- **Workspace Root**: /Users/sebastianchavarry01/Documents/personal-github/ask-dmc

## Code Location Rules
- **Application Code**: Workspace root (NEVER in aidlc-docs/)
- **Documentation**: aidlc-docs/ only
- **Structure patterns**: See code-generation.md Critical Rules

## Extension Configuration

| Extension | Enabled | Decided At |
|---|---|---|
| Security Baseline (SECURITY-01 a SECURITY-15) | Yes | Requirements Analysis |
| Property-Based Testing (PBT-01 a PBT-10) | Yes — Full enforcement | Requirements Analysis |

## Known Divergences from Inception Decisions

| # | Decision in Inception | Divergence in Construction | Rationale | Affected Inception Docs |
|---|---|---|---|---|
| DIV-01 | `PDFExtractor` uses `LLMProvider` to extract 12 sections from brochures (Requirements Analysis, Application Design) | Functional Design (unit-1) replaces LLM extraction with a deterministic pdfplumber + regex parser | Brochure content structure is predictable and consistent; deterministic parsing is more reliable and eliminates LLM cost for this step | `requirements.md`, `components.md`, `services.md`, `unit-of-work.md`, `stories.md` |
| DIV-02 | `KeywordsExtractor.extract_keywords(sections) → list[BrochureSection]` — extracción por sección, keywords en `BrochureSection.keywords`, 3 retries con backoff (business-logic-model.md) | `extract_keywords(sections) → list[str]` — extracción a nivel de documento combinando 5 secciones clave, retorna una sola lista de keywords por brochure, sin retry, salida estructurada con Pydantic | Keywords a nivel de documento son más representativas para búsqueda; reduce de N llamadas LLM a 1 por PDF; Pydantic structured output elimina parsing manual de JSON | `business-logic-model.md`, `domain-entities.md` |
| DIV-03 | `EmbeddedChunk` tiene `section_type: SectionType`; `BrochureSection` tiene `keywords: list[str]` (domain-entities.md) | Ambos campos eliminados: `EmbeddedChunk` sin `section_type`, `BrochureSection` sin `keywords` | Consecuencia de DIV-02: keywords son documento-nivel; section_type no aporta valor en el vector DB para recuperación semántica | `domain-entities.md`, `migrations/001` |
| DIV-04 | `EmbeddingGenerator.generate(sections) → list[EmbeddedChunk]` — un chunk por sección, texto enriquecido `Programa:/Sección:`, keywords de `section.keywords` (business-logic-model.md) | `generate(sections, keywords: list[str]) → list[EmbeddedChunk]` — text-splitting 2000 chars / 200 overlap, formato `[section_type]\ncontent`, keywords externos aplicados a todos los chunks | Secciones largas excedían límite de tokens del modelo de embeddings; keywords externos vienen de DIV-02 | `business-logic-model.md` |
| DIV-05 | `brochure_chunks` table: `section_type TEXT NOT NULL`, `embedding vector(1536)` (migrations/001) | Columna `section_type` eliminada; `embedding vector(768)`; nueva migración 002 trunca la tabla | section_type eliminado por DIV-03; nomic-embed-text produce 768 dims (no 1536, que era para Bedrock Titan) | `migrations/001_create_brochure_chunks.sql` |
| DIV-06 | PATTERN-03: Retry con backoff en `OllamaEmbeddingsProvider.embed()` (nfr-design-patterns.md, post-build fix 2026-04-30) | Retry eliminado; reemplazado por `keep_alive=10m` en el payload de la llamada a Ollama | Causa raíz eran descargas de modelo entre llamadas (model swap); `keep_alive` previene la descarga, eliminando la condición — retry trataba el síntoma, no la causa | `nfr-design-patterns.md` (PATTERN-03) |
| DIV-07 | `LLMProvider.complete(prompt: str) → str` (ports/llm_provider.py) | `complete(prompt: str, format: dict | None = None) → str`; OllamaLLMProvider pasa `format` al payload para structured output | Consecuencia de DIV-02: keywords usan JSON schema de Pydantic como `format` para forzar salida estructurada válida | `ports/llm_provider.py`, `infrastructure/llm/ollama_llm.py`, `infrastructure/llm/bedrock_llm.py` |
| DIV-08 | `ingestion_workers=4 if env == ENV.LOCAL else int(os.environ.get("INGESTION_WORKERS", "4"))` (src/config.py) | `ingestion_workers=int(os.environ.get("INGESTION_WORKERS", "4"))` — siempre desde el entorno sin condicional por ENV | `.env` debe ser la única fuente de verdad; el hardcode para LOCAL ignoraba silenciosamente el valor en `.env` | `src/config.py` |
| DIV-09 | `EmbeddingGenerator` y `test_rag.py` usaban texto crudo al llamar a `OllamaEmbeddingsProvider.embed()` (sin prefijo) | `embed(f"search_document: {text}")` al indexar chunks; `embed(f"search_query: {question}")` al buscar | `nomic-embed-text` es un modelo asimétrico: requiere prefijos distintos para documentos y consultas para producir similitudes coseno bien alineadas. Sin ellos, la recuperación degrada significativamente. Acción posterior requerida: re-ejecutar la ingesta completa para recomputar embeddings con el prefijo correcto. | `src/pipeline/embedding_generator.py`, `scripts/test_rag.py` |

> Inception docs are kept as historical record. Construction artifacts take precedence for implementation.

---

## Stage Progress

### INCEPTION PHASE
- [x] Workspace Detection — COMPLETED (2026-04-23)
- [x] Requirements Analysis — COMPLETED and APPROVED (2026-04-28)
- [x] User Stories — COMPLETED and APPROVED (2026-04-28)
- [x] Workflow Planning — COMPLETED and APPROVED (2026-04-28)
- [x] Application Design — COMPLETED and APPROVED (2026-04-28)
- [x] Units Generation — COMPLETED and APPROVED (2026-04-28)

### CONSTRUCTION PHASE
- [x] Per-Unit Loop — unit-1: ingestion-pipeline COMPLETED (2026-04-30)
  - [x] Functional Design — COMPLETED and APPROVED
  - [x] NFR Requirements — COMPLETED and APPROVED
  - [x] NFR Design — COMPLETED and APPROVED
  - [x] Infrastructure Design — COMPLETED and APPROVED
  - [x] Code Generation — COMPLETED (awaiting approval)
- [x] Build and Test — COMPLETED (2026-04-30)

### OPERATIONS PHASE
- [ ] Operations — PLACEHOLDER
