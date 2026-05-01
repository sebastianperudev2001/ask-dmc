# Tech Stack Decisions — ingestion-pipeline

**Fecha**: 2026-04-30
**Unit**: unit-1: ingestion-pipeline

---

## TSD-01: Vector DB (Production) — pgvector on Amazon RDS PostgreSQL

**Decision**: Use `pgvector` extension on Amazon RDS PostgreSQL as the production vector store.

**Rationale**:
- Cost-effective at current scale (~312 chunks); no minimum charge like OpenSearch Serverless
- Familiar SQL interface — metadata filtering via standard WHERE clauses
- pgvector supports cosine similarity search natively with `<=>` operator
- Same tech as local dev environment (TSD-02), reducing prod/local divergence

**Implications**:
- RDS instance must be provisioned in a private VPC subnet
- Connection string provided via `VECTOR_DB_URL` environment variable
- pgvector extension must be enabled: `CREATE EXTENSION vector;`
- Recommended instance: `db.t3.micro` or `db.t3.small` sufficient for current scale

**Schema**:
```sql
CREATE TABLE brochure_chunks (
    id           TEXT PRIMARY KEY,           -- "{course_name}_{section_type}"
    course_name  TEXT NOT NULL,
    section_type TEXT NOT NULL,
    content      TEXT NOT NULL,
    embedding    vector(1536),               -- Bedrock titan-embed-text-v2 dimension
    keywords     TEXT[]                      -- Array of keyword strings
);

CREATE INDEX ON brochure_chunks USING ivfflat (embedding vector_cosine_ops);
```

**Future path**: If scale grows significantly, migrate to OpenSearch Serverless or Aurora pgvector without changing application logic (only `VectorDBRepository` implementation changes).

---

## TSD-02: Vector DB (Local) — pgvector on local PostgreSQL via Docker

**Decision**: Use `pgvector` extension on a local PostgreSQL instance via Docker for development.

**Rationale**:
- Same tech as production (TSD-01) — eliminates prod/local divergence in vector operations
- Reproducible via Docker Compose; no local PostgreSQL installation required
- `ankane/pgvector` Docker image bundles pgvector extension out of the box

**Docker Compose snippet**:
```yaml
services:
  postgres:
    image: ankane/pgvector
    environment:
      POSTGRES_DB: ask_dmc
      POSTGRES_USER: ask_dmc
      POSTGRES_PASSWORD: ask_dmc
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data

volumes:
  pgdata:
```

**Local connection**: `VECTOR_DB_URL=postgresql://ask_dmc:ask_dmc@localhost:5432/ask_dmc`

---

## TSD-03: Pipeline Execution Mode — Parallel (ThreadPoolExecutor)

**Decision**: Process PDFs in parallel using Python's `concurrent.futures.ThreadPoolExecutor`.

**Rationale**:
- Keyword extraction and embedding generation are network I/O-bound — parallelism directly reduces wall-clock time
- ThreadPoolExecutor integrates cleanly with Python's standard library; no additional dependencies
- PDF parsing (CPU-bound, fast) also benefits when combined with I/O steps

**Configuration**:
- Worker count: controlled by `INGESTION_WORKERS` env var (default: `4`)
- Thread safety: each PDF processed fully independently; no shared mutable state between threads
- The `IngestionReport` aggregation is performed after all futures complete

**Implementation pattern**:
```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def run(self, config: IngestionConfig) -> IngestionReport:
    workers = int(os.getenv("INGESTION_WORKERS", "4"))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(self._process_pdf, entry): entry
            for entry in pdf_entries
        }
        for future in as_completed(futures):
            result = future.result()  # PDFResult or IngestionError
            # aggregate into report
```

---

## TSD-04: Pipeline Trigger — Manual CLI Script

**Decision**: Trigger ingestion via a manual CLI script (`python -m ingestion.cli` or `python ingest.py`).

**Rationale**:
- Current catalog (~26 PDFs) changes infrequently; automation not yet justified
- Manual trigger keeps infrastructure minimal at launch
- Operator runs script locally (LOCAL env) or via ECS task / SSH (PRODUCTION env)

**Future migration path**: Architecture explicitly supports future EventBridge scheduled trigger (Q4 note). The pipeline entry point is a single `IngestionOrchestrator.run(config)` call — wrapping it in a Lambda handler or ECS task requires no changes to pipeline logic.

---

## TSD-05: Logging — Structured Stdout + Log File

**Decision**: Emit structured logs to stdout and write a log file per run to `reports/pipeline_{timestamp}.log`.

**Rationale**:
- No infrastructure required at current scale
- Log file provides persistent audit trail alongside the JSON `IngestionReport`
- Sufficient for development debugging and post-run review

**Log format**: `[2026-04-30T12:00:00Z] [INFO] [course_name] Processing PDF`

**Implementation**: Python `logging` module with a `FileHandler` (log file) and `StreamHandler` (stdout), both using a shared formatter. Logger configured at pipeline startup from `IngestionConfig`.

**Future path**: Adding CloudWatch log shipping requires only replacing `StreamHandler` with `watchtower.CloudWatchLogHandler` — no log statement changes.

---

## TSD-06: Python DB Client — psycopg2 + pgvector adapter

**Decision**: Use `psycopg2` as the PostgreSQL client with the `pgvector` Python adapter for vector type support.

**Rationale**:
- `psycopg2` is the standard, battle-tested PostgreSQL client for Python
- `pgvector` Python package provides `register_vector()` to enable native `list[float]` ↔ `vector` type coercion
- No ORM needed — `VectorDBRepository` uses raw SQL for upsert operations (simple, explicit)

**Key packages**:
```
psycopg2-binary>=2.9
pgvector>=0.2
```

**Upsert pattern**:
```sql
INSERT INTO brochure_chunks (id, course_name, section_type, content, embedding, keywords)
VALUES (%s, %s, %s, %s, %s, %s)
ON CONFLICT (id) DO UPDATE SET
    content   = EXCLUDED.content,
    embedding = EXCLUDED.embedding,
    keywords  = EXCLUDED.keywords;
```

---

## Summary Table

| Decision | Choice | ENV |
|---|---|---|
| Vector DB (prod) | pgvector on Amazon RDS PostgreSQL | PRODUCTION |
| Vector DB (local) | pgvector on PostgreSQL via Docker | LOCAL |
| Pipeline execution | Parallel — ThreadPoolExecutor (default 4 workers) | Both |
| Pipeline trigger | Manual CLI script | Both |
| Logging | Structured stdout + log file in `reports/` | Both |
| DB client | psycopg2 + pgvector adapter | Both |
