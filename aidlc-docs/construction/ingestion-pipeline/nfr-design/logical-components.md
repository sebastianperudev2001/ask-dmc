# Logical Components — ingestion-pipeline

**Fecha**: 2026-04-30
**Unit**: unit-1: ingestion-pipeline

---

## Component Overview

```
CLI Entry Point
    └── IngestionOrchestrator
            ├── ProviderFactory          (creates ENV-appropriate providers)
            ├── ThreadedConnectionPool   (PostgreSQL connections for parallel threads)
            ├── LoggingConfigurator      (stdout + file handlers)
            └── ThreadPoolExecutor
                    └── _process_pdf() [per thread]
                            ├── StorageProvider
                            ├── PDFParser
                            ├── KeywordsExtractor  ──► LLMProvider (with retry)
                            ├── EmbeddingGenerator ──► EmbeddingsProvider
                            └── VectorDBRepository ──► ThreadedConnectionPool
                    ↓ as_completed()
            IngestionReport aggregation
            ReportRepository (save JSON + log file already written)
```

---

## LC-01: IngestionOrchestrator

**Role**: Parallel pipeline coordinator and report aggregator.

**Responsibilities**:
- Initialize providers via `ProviderFactory`
- Initialize `ThreadedConnectionPool` and `LoggingConfigurator`
- Submit one `_process_pdf()` task per PDF to `ThreadPoolExecutor`
- Collect futures via `as_completed()` and aggregate into `IngestionReport`
- Save final report via `ReportRepository`

**State**: Holds the connection pool and provider instances. These are read-only during parallel execution — no mutation from worker threads.

**Patterns applied**: PATTERN-01, PATTERN-05

---

## LC-02: ProviderFactory

**Role**: Centralized ENV-to-provider resolver. Created once at pipeline startup.

**Responsibilities**:
- Read `INGESTION_ENV` from environment
- Construct and return all provider instances for the active ENV:
  - `StorageProvider` (Filesystem or S3)
  - `EmbeddingsProvider` (Ollama or Bedrock)
  - `LLMProvider` (Ollama or Bedrock — for keywords)
  - `ReportRepository` (Filesystem or S3)

**Patterns applied**: PATTERN-02

| Provider Interface | LOCAL Implementation | PRODUCTION Implementation |
|---|---|---|
| `StorageProvider` | `FilesystemStorageProvider` | `S3StorageProvider` |
| `EmbeddingsProvider` | `OllamaEmbeddingsProvider` | `BedrockEmbeddingsProvider` |
| `LLMProvider` | `OllamaLLMProvider` | `BedrockLLMProvider` |
| `ReportRepository` | `FilesystemReportRepository` | `S3ReportRepository` |

---

## LC-03: ThreadedConnectionPool

**Role**: PostgreSQL connection pool for safe parallel DB access.

**Type**: `psycopg2.pool.ThreadedConnectionPool`

**Responsibilities**:
- Maintain a pool of live connections to the pgvector PostgreSQL instance
- Issue one connection per worker thread on checkout
- Return connections to pool after use
- Close all connections on pipeline shutdown

**Sizing**: `minconn=1`, `maxconn=INGESTION_WORKERS` (default 4)

**Lifecycle**:
```
startup  → ThreadedConnectionPool(minconn=1, maxconn=workers, dsn=VECTOR_DB_URL)
per PDF  → conn = pool.getconn() ... pool.putconn(conn)
shutdown → pool.closeall()
```

**Patterns applied**: PATTERN-06

---

## LC-04: LoggingConfigurator

**Role**: Sets up the dual-handler logger at pipeline startup.

**Responsibilities**:
- Create a `StreamHandler` (stdout) and `FileHandler` (`reports/pipeline_{timestamp}.log`)
- Attach both to the root `ingestion` logger with a shared formatter
- Return the configured logger for use throughout the pipeline

**Output**:
- Stdout: real-time progress during pipeline execution
- File: persistent log at `reports/pipeline_{timestamp}.log` (same timestamp as `IngestionReport`)

**Patterns applied**: PATTERN-07

---

## LC-05: VectorDBRepository

**Role**: Persists `EmbeddedChunk` objects to pgvector via idempotent upsert.

**Responsibilities**:
- Accept a DB connection from the pool (injected per thread)
- Execute `INSERT ... ON CONFLICT (id) DO UPDATE` for each chunk
- Register pgvector type on the connection via `register_vector(conn)`

**Schema target**: `brochure_chunks` table (defined in TSD-01)

**Patterns applied**: PATTERN-04, PATTERN-06

---

## LC-06: KeywordsExtractor (with retry decorator)

**Role**: Wraps LLM keyword extraction with retry + backoff logic.

**Responsibilities**:
- Call `LLMProvider.complete()` with the keywords prompt per section
- Apply PATTERN-03: up to 3 retries with backoff (1s, 2s, 4s)
- On total failure: set `section.keywords = []` and log WARNING
- Return sections with keywords populated (or empty list on failure)

**Patterns applied**: PATTERN-03

---

## LC-07: PDFResult (Value Object)

**Role**: Thread-safe return value from `_process_pdf()`.

**Fields**:
```python
@dataclass
class PDFResult:
    course_name: str
    success: bool
    chunks_upserted: int
    sections_extracted: int
    error: IngestionError | None
```

**Purpose**: Allows the main thread to aggregate results from all worker futures without shared mutable state. Each thread returns an independent `PDFResult`.

**Patterns applied**: PATTERN-05

---

## Environment Variable Reference

| Variable | Used By | Description |
|---|---|---|
| `INGESTION_ENV` | ProviderFactory | `local` or `production` |
| `INGESTION_WORKERS` | IngestionOrchestrator | Thread pool size (default: 4) |
| `VECTOR_DB_URL` | ThreadedConnectionPool | PostgreSQL DSN |
| `S3_BUCKET` | S3StorageProvider, S3ReportRepository | S3 bucket name |
| `S3_BROCHURES_PREFIX` | S3StorageProvider | S3 prefix for PDFs |
| `S3_REPORTS_PREFIX` | S3ReportRepository | S3 prefix for reports |
| `BEDROCK_EMBEDDINGS_MODEL` | BedrockEmbeddingsProvider | e.g. `amazon.titan-embed-text-v2:0` |
| `KEYWORDS_MODEL` | LLMProvider | e.g. `claude-haiku-4-5` (prod) / `gemma3:4b` (local) |
| `OLLAMA_BASE_URL` | OllamaEmbeddingsProvider, OllamaLLMProvider | e.g. `http://localhost:11434` |
| `LOCAL_KNOWLEDGE_DIR` | FilesystemStorageProvider | e.g. `knowledge_source/` |
| `LOCAL_REPORTS_DIR` | FilesystemReportRepository, LoggingConfigurator | e.g. `reports/` |
