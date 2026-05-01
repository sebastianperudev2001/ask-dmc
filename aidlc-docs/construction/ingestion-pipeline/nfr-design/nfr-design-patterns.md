# NFR Design Patterns — ingestion-pipeline

**Fecha**: 2026-04-30
**Unit**: unit-1: ingestion-pipeline

---

## PATTERN-01: Thread-per-PDF Isolation

**NFR Drivers**: PERF-02, REL-05, SCAL-04

**Problem**: Processing 26 PDFs sequentially leaves LLM I/O time (keyword extraction, embedding) wasted. Parallel execution needs to be safe — a failure in one PDF must not corrupt another's state.

**Solution**: Each PDF is processed in a completely isolated execution unit. No shared mutable state exists between threads. All data flows through function arguments and return values only.

```
ThreadPoolExecutor
    ├── Thread A: _process_pdf(entry_1) → PDFResult
    ├── Thread B: _process_pdf(entry_2) → PDFResult
    ├── Thread C: _process_pdf(entry_3) → PDFResult
    └── Thread D: _process_pdf(entry_4) → PDFResult
                      ↓ as_completed()
              IngestionReport (aggregated after all futures)
```

**Invariants**:
- `_process_pdf()` receives its own DB connection from the pool (PATTERN-06)
- All providers (StorageProvider, EmbeddingsProvider, LLMProvider) are stateless or thread-safe
- IngestionReport is only written after all futures complete (PATTERN-05)

---

## PATTERN-02: Provider Factory (ENV-based Selection)

**NFR Drivers**: MAINT-02, SEC-04, MAINT-04

**Problem**: Each ENV (LOCAL, PRODUCTION) requires different provider implementations. Scattering `if env == LOCAL` checks throughout the codebase makes the pipeline fragile and hard to test.

**Solution**: A centralized `ProviderFactory` reads `INGESTION_ENV` once at startup and constructs all provider instances. The pipeline orchestrator receives ready-to-use interfaces — it never inspects ENV itself.

```
INGESTION_ENV=local
        ↓
ProviderFactory.create(config)
    ├── storage    → FilesystemStorageProvider(config.local_knowledge_dir)
    ├── embeddings → OllamaEmbeddingsProvider(config.ollama_model)
    ├── keywords   → OllamaLLMProvider(config.keywords_model)
    ├── vector_db  → VectorDBRepository(pool.getconn())
    └── reports    → FilesystemReportRepository(config.local_reports_dir)

INGESTION_ENV=production
        ↓
ProviderFactory.create(config)
    ├── storage    → S3StorageProvider(config.s3_bucket, config.s3_prefix)
    ├── embeddings → BedrockEmbeddingsProvider(config.bedrock_embeddings_model)
    ├── keywords   → BedrockLLMProvider(config.keywords_model)
    ├── vector_db  → VectorDBRepository(pool.getconn())
    └── reports    → S3ReportRepository(config.s3_bucket, config.s3_reports_prefix)
```

**Invariants**:
- Factory is called once per pipeline run
- Each provider implements a well-defined interface (StorageProvider, EmbeddingsProvider, etc.)
- Adding a new ENV requires only new provider implementations + one factory branch

---

## PATTERN-03: Retry with Exponential Backoff

**NFR Drivers**: REL-01, PERF-03

**Problem**: LLM calls (keyword extraction) are network-bound and subject to transient failures (timeout, rate limit). A single failure should not discard the chunk.

**Solution**: Wrap each LLM call in a retry loop with exponential backoff. After 3 failures, degrade gracefully (`keywords=[]`).

```
attempt 1 → LLMError → sleep(1s)
attempt 2 → LLMError → sleep(2s)
attempt 3 → LLMError → keywords=[] (chunk preserved, not discarded)
```

**Scope**: Applied only to keyword extraction (BR-09). Embedding generation failures are hard failures — the chunk is not persisted if embedding fails.

**Backoff schedule**: 1s → 2s → 4s (2^(attempt-1))

---

## PATTERN-04: Idempotent Upsert

**NFR Drivers**: REL-03, AVAIL-03

**Problem**: The pipeline may be re-run after partial failure or after a brochure PDF is updated. Duplicate inserts must be handled without manual cleanup.

**Solution**: All vector DB writes use PostgreSQL `INSERT ... ON CONFLICT (id) DO UPDATE`, where `id` is the deterministic chunk ID (`{course_name}_{section_type}`, BR-03). Re-running the pipeline on unchanged PDFs is a no-op in effect; running on updated PDFs refreshes content and embeddings.

```
First run:   INSERT chunk(id="power-bi_objetivo", ...)  → inserted
Second run:  INSERT chunk(id="power-bi_objetivo", ...)  → updated (same content)
After PDF update: INSERT chunk(id="power-bi_objetivo", new_content, new_embedding) → updated
```

---

## PATTERN-05: Thread-Safe Result Aggregation

**NFR Drivers**: REL-05, PERF-02

**Problem**: Multiple threads complete `_process_pdf()` concurrently. The IngestionReport must accumulate results without race conditions.

**Solution**: Each thread returns a `PDFResult` (success) or `IngestionError` (failure) as a return value. The main thread collects all `Future` results via `as_completed()` and builds the IngestionReport serially after all futures complete — no shared mutable state during parallel execution.

```python
results = [future.result() for future in as_completed(futures)]
# All threads done — single-threaded aggregation
report = aggregate(results)
```

---

## PATTERN-06: Threaded Connection Pool (PostgreSQL)

**NFR Drivers**: PERF-02, REL-05

**Problem**: With N parallel threads each needing a PostgreSQL connection for `VectorDBRepository.upsert()`, creating a new connection per thread on every call is expensive. Sharing a single connection across threads is not thread-safe with psycopg2.

**Solution**: Use `psycopg2.pool.ThreadedConnectionPool` initialized at pipeline startup. Each thread checks out a connection, uses it, and returns it to the pool after the PDF is processed.

```
Startup: ThreadedConnectionPool(minconn=1, maxconn=INGESTION_WORKERS)
    ↓
Thread A: conn = pool.getconn() → upsert chunks → pool.putconn(conn)
Thread B: conn = pool.getconn() → upsert chunks → pool.putconn(conn)
    ↓
Shutdown: pool.closeall()
```

**Pool sizing**: `maxconn = INGESTION_WORKERS` (default 4). Each thread needs exactly one connection.

---

## PATTERN-07: Dual-Handler Structured Logging

**NFR Drivers**: OBS-01, OBS-02, OBS-03, OBS-04

**Problem**: Logs need to be visible in real-time (stdout) and persist after the run (log file) for post-mortem review.

**Solution**: Configure a single Python logger with two handlers sharing the same formatter. Both handlers are attached at pipeline startup.

```
Logger("ingestion")
    ├── StreamHandler(sys.stdout)  → real-time terminal output
    └── FileHandler("reports/pipeline_{timestamp}.log")  → persistent log file

Formatter: "[%(asctime)s] [%(levelname)s] [%(course_name)s] %(message)s"
```

**Thread safety**: Python's `logging` module is thread-safe by default — no additional locking needed.

**Log levels**:
- `INFO`: PDF start/complete, chunk count, pipeline summary
- `WARNING`: LLM retry, missing section, keywords degraded to `[]`
- `ERROR`: PDF processing failure (recorded in IngestionReport)
