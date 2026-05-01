# NFR Design Plan — ingestion-pipeline

**Fecha**: 2026-04-30

## Execution Checkboxes

- [x] Step 1: Analyze NFR requirements artifacts
- [x] Step 2: Identify applicable design patterns
- [x] Step 3: Generate nfr-design-patterns.md
- [x] Step 4: Generate logical-components.md

---

## Questions Assessment

No questions required — all NFR design decisions are fully derivable from functional design artifacts and NFR requirements:
- Concurrency model: ThreadPoolExecutor (TSD-03)
- Vector DB: pgvector + psycopg2 (TSD-06) — connection pooling pattern implied by parallel threads
- Retry strategy: defined in BR-09
- ENV-based provider selection: defined in BR-12
- Logging: dual handler (stdout + file) per OBS-01/OBS-02
- Security: IAM + env vars per SEC-01–SEC-06

## Patterns to Document

1. Thread-per-PDF Isolation
2. Provider Factory (ENV-based)
3. Retry with Exponential Backoff
4. Idempotent Upsert
5. Thread-Safe Result Aggregation
6. Threaded Connection Pool (PostgreSQL)
7. Dual-Handler Structured Logging
