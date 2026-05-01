# Code Summary — ingestion-pipeline

**Fecha**: 2026-04-30
**Unit**: unit-1: ingestion-pipeline
**Stories**: US-17 (complete), US-18 (infrastructure base complete)

---

## Files Created

### Domain
| File | Contents |
|---|---|
| `src/domain/entities.py` | ENV, SectionType, BrochureSection, EmbeddedChunk, IngestionConfig, IngestionError, IngestionReport, PDFResult |

### Ports (Protocols)
| File | Interface |
|---|---|
| `src/ports/storage_provider.py` | StorageProvider |
| `src/ports/embeddings_provider.py` | EmbeddingsProvider |
| `src/ports/llm_provider.py` | LLMProvider |
| `src/ports/vector_db_repository.py` | VectorDBRepository |
| `src/ports/report_repository.py` | ReportRepository |

### Pipeline
| File | Component |
|---|---|
| `src/pipeline/pdf_parser.py` | PDFParser — deterministic pdfplumber + regex |
| `src/pipeline/keywords_extractor.py` | KeywordsExtractor — LLM + 3-retry backoff |
| `src/pipeline/embedding_generator.py` | EmbeddingGenerator — enriched text → EmbeddedChunk |
| `src/pipeline/orchestrator.py` | IngestionOrchestrator — ThreadPoolExecutor coordinator |
| `src/pipeline/provider_factory.py` | ProviderFactory + Providers + ThreadedConnectionPool |

### Infrastructure
| File | Provider |
|---|---|
| `src/infrastructure/storage/filesystem_storage.py` | FilesystemStorageProvider (LOCAL) |
| `src/infrastructure/storage/s3_storage.py` | S3StorageProvider (PRODUCTION) |
| `src/infrastructure/llm/ollama_llm.py` | OllamaLLMProvider (LOCAL) |
| `src/infrastructure/llm/bedrock_llm.py` | BedrockLLMProvider (PRODUCTION) |
| `src/infrastructure/embeddings/ollama_embeddings.py` | OllamaEmbeddingsProvider (LOCAL) |
| `src/infrastructure/embeddings/bedrock_embeddings.py` | BedrockEmbeddingsProvider (PRODUCTION) |
| `src/infrastructure/vector_db/pgvector_repository.py` | PgVectorRepository — psycopg2 + pgvector upsert |
| `src/infrastructure/reports/filesystem_report.py` | FilesystemReportRepository (LOCAL) |
| `src/infrastructure/reports/s3_report.py` | S3ReportRepository (PRODUCTION) |

### Config & Logging
| File | Purpose |
|---|---|
| `src/config.py` | Loads IngestionConfig from environment variables |
| `src/logging_config.py` | Dual-handler logger (stdout + file) |

### Entry Points
| File | Purpose |
|---|---|
| `cli.py` | Manual CLI trigger: `python cli.py` |
| `lambda_handler.py` | AWS Lambda handler (future production) |

### Tests
| File | Type | Coverage |
|---|---|---|
| `tests/unit/test_pdf_parser.py` | Unit | PDFParser shape, content, validation |
| `tests/unit/test_keywords_extractor.py` | Unit | Success, retry, failure, truncation |
| `tests/unit/test_embedding_generator.py` | Unit | Output shape, ID, keywords, enrich |
| `tests/unit/test_orchestrator.py` | Unit | Report totals, error accumulation |
| `tests/conftest.py` | PBT generators | Domain-specific Hypothesis strategies |
| `tests/pbt/test_pdf_parser_properties.py` | PBT | BR-01, BR-02: always 12 sections, present invariant |
| `tests/pbt/test_chunk_properties.py` | PBT | BR-03, BR-08: deterministic ID, keywords ≤ 10, report totals |

### Deployment Artifacts
| File | Purpose |
|---|---|
| `docker-compose.yml` | pgvector PostgreSQL for local dev |
| `.env.example` | Environment variable template |
| `requirements.txt` | Runtime dependencies |
| `requirements-dev.txt` | Dev + test dependencies |
| `Makefile` | `make test`, `make run`, `make db-up` targets |
| `migrations/001_create_brochure_chunks.sql` | pgvector schema + ivfflat index |
