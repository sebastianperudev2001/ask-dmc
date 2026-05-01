# Code Generation Plan — ingestion-pipeline

**Fecha**: 2026-04-30
**Unit**: unit-1: ingestion-pipeline
**Directory**: `services/ingestion/` (workspace root)
**Stories**: US-17 (primary), US-18 (infrastructure base)

---

## Unit Context

| Field | Value |
|---|---|
| Runtime | Python 3.11 |
| ENV split | LOCAL (filesystem + Ollama + pgvector Docker) / PRODUCTION (S3 + Bedrock + RDS) |
| Trigger | Manual CLI (`python cli.py`) / Lambda handler (future) |
| Vector DB | pgvector via psycopg2 + ThreadedConnectionPool |
| Concurrency | ThreadPoolExecutor (INGESTION_WORKERS, default 4) |
| PBT framework | Hypothesis |

### Story Traceability
- **US-17** — Ingestion de brochures PDF: PDFParser + KeywordsExtractor + EmbeddingGenerator + IngestionOrchestrator + all infrastructure
- **US-18** — Búsqueda semántica (infra base): VectorDBRepository (upsert + schema)

### Key Construction Divergences Applied
- DIV-01: PDFParser is deterministic (pdfplumber + regex), NOT LLM-based
- ENV abstraction: all providers selected via ProviderFactory based on INGESTION_ENV

---

## Target Structure

```
services/ingestion/
├── src/
│   ├── domain/
│   │   ├── __init__.py
│   │   └── entities.py
│   ├── ports/
│   │   ├── __init__.py
│   │   ├── storage_provider.py
│   │   ├── embeddings_provider.py
│   │   ├── llm_provider.py
│   │   ├── vector_db_repository.py
│   │   └── report_repository.py
│   ├── pipeline/
│   │   ├── __init__.py
│   │   ├── pdf_parser.py
│   │   ├── keywords_extractor.py
│   │   ├── embedding_generator.py
│   │   ├── orchestrator.py
│   │   └── provider_factory.py
│   ├── infrastructure/
│   │   ├── __init__.py
│   │   ├── storage/
│   │   │   ├── __init__.py
│   │   │   ├── filesystem_storage.py
│   │   │   └── s3_storage.py
│   │   ├── llm/
│   │   │   ├── __init__.py
│   │   │   ├── ollama_llm.py
│   │   │   └── bedrock_llm.py
│   │   ├── embeddings/
│   │   │   ├── __init__.py
│   │   │   ├── ollama_embeddings.py
│   │   │   └── bedrock_embeddings.py
│   │   ├── vector_db/
│   │   │   ├── __init__.py
│   │   │   └── pgvector_repository.py
│   │   └── reports/
│   │       ├── __init__.py
│   │       ├── filesystem_report.py
│   │       └── s3_report.py
│   ├── logging_config.py
│   └── config.py
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── unit/
│   │   ├── __init__.py
│   │   ├── test_pdf_parser.py
│   │   ├── test_keywords_extractor.py
│   │   ├── test_embedding_generator.py
│   │   └── test_orchestrator.py
│   └── pbt/
│       ├── __init__.py
│       ├── test_pdf_parser_properties.py
│       └── test_chunk_properties.py
├── migrations/
│   └── 001_create_brochure_chunks.sql
├── cli.py
├── lambda_handler.py
├── docker-compose.yml
├── .env.example
├── requirements.txt
├── requirements-dev.txt
└── Makefile
```

---

## Execution Checkboxes

- [x] **Step 1**: Project structure + domain entities (`src/domain/entities.py`)
- [x] **Step 2**: Port interfaces (`src/ports/`)
- [x] **Step 3**: PDFParser (`src/pipeline/pdf_parser.py`) + unit tests (`tests/unit/test_pdf_parser.py`)
- [x] **Step 4**: KeywordsExtractor (`src/pipeline/keywords_extractor.py`) + unit tests
- [x] **Step 5**: EmbeddingGenerator (`src/pipeline/embedding_generator.py`) + unit tests
- [x] **Step 6**: Infrastructure — Storage (`filesystem_storage.py`, `s3_storage.py`)
- [x] **Step 7**: Infrastructure — LLM providers (`ollama_llm.py`, `bedrock_llm.py`)
- [x] **Step 8**: Infrastructure — Embeddings providers (`ollama_embeddings.py`, `bedrock_embeddings.py`)
- [x] **Step 9**: Infrastructure — VectorDBRepository (`pgvector_repository.py`) + DB migration SQL
- [x] **Step 10**: Infrastructure — ReportRepository (`filesystem_report.py`, `s3_report.py`)
- [x] **Step 11**: ProviderFactory (`src/pipeline/provider_factory.py`) + Config (`src/config.py`) + LoggingConfigurator (`src/logging_config.py`)
- [x] **Step 12**: IngestionOrchestrator (`src/pipeline/orchestrator.py`) + PDFResult + unit tests (`tests/unit/test_orchestrator.py`)
- [x] **Step 13**: CLI entry point (`cli.py`) + Lambda handler (`lambda_handler.py`)
- [x] **Step 14**: PBT tests — conftest generators (`tests/conftest.py`) + property tests (`tests/pbt/`)
- [x] **Step 15**: Deployment artifacts (`docker-compose.yml`, `.env.example`, `requirements.txt`, `requirements-dev.txt`, `Makefile`)
- [x] **Step 16**: Documentation summary (`aidlc-docs/construction/ingestion-pipeline/code/code-summary.md`)

---

## PBT Coverage Plan (Hypothesis)

| Test | Rule | Property | Category |
|---|---|---|---|
| PDFParser always produces exactly 12 BrochureSection | BR-01 | `len(parse(pdf_bytes, name)) == 12` for any valid PDF bytes | Invariant |
| PDFParser section types are unique | BR-01 | All 12 section_type values are distinct | Invariant |
| Sections with present=False have empty content | — | `not s.present → s.content == ""` | Invariant |
| Chunk ID is deterministic | BR-03 | `chunk.id == f"{name}_{stype}"` always | Invariant |
| Keywords length constraint | BR-08 | `0 <= len(keywords) <= 10` always | Invariant |
| IngestionReport totals | — | `report.processed + report.failed == report.total_pdfs` | Invariant |
| Upsert idempotency | BR-03 | Upserting same chunk twice = same DB state as once | Idempotency |

---

## Story Completion Tracking

- [x] US-17 — Ingestion de brochures PDF (completed when Step 12 done)
- [x] US-18 — Búsqueda semántica infra (completed when Step 9 done)
