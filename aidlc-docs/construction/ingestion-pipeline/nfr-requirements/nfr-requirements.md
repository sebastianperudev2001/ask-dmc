# NFR Requirements — ingestion-pipeline

**Fecha**: 2026-04-30
**Unit**: unit-1: ingestion-pipeline
**Type**: Offline batch pipeline (manual CLI trigger)

---

## Performance

| ID | Requirement | Target |
|---|---|---|
| PERF-01 | Full catalog ingestion time | < 10 minutes for ~26 PDFs under normal conditions |
| PERF-02 | PDF parallel processing | Thread pool with configurable worker count (default: 4) |
| PERF-03 | LLM keyword extraction bottleneck | Mitigated by parallelism; per-PDF timeout bounded by BR-09 (max ~7s backoff) |
| PERF-04 | Vector DB upsert latency | Each upsert is a single row; pgvector at this scale has negligible latency |

**Notes**:
- The dominant bottleneck is LLM keyword extraction (network-bound). Parallelism across PDFs reduces wall-clock time proportionally to worker count.
- Thread count should be configurable via `INGESTION_WORKERS` env var. Default: `4`.

---

## Scalability

| ID | Requirement | Notes |
|---|---|---|
| SCAL-01 | Current catalog size | ~26 PDFs, ~312 max chunks (26 × 12 sections) |
| SCAL-02 | Growth expectation | Slow — new courses added infrequently (weeks/months) |
| SCAL-03 | Vector DB capacity | pgvector handles millions of rows; current scale is negligible |
| SCAL-04 | Thread pool scaling | Increasing `INGESTION_WORKERS` is sufficient to handle catalog growth |
| SCAL-05 | Future trigger migration | Manual CLI is current trigger; architecture must not prevent future migration to EventBridge scheduled trigger |

---

## Availability

| ID | Requirement | Notes |
|---|---|---|
| AVAIL-01 | Uptime SLA | None — offline batch pipeline, no always-on requirement |
| AVAIL-02 | Per-PDF fault isolation | A single PDF failure does not stop the pipeline (BR-06) |
| AVAIL-03 | Recovery mechanism | Manual re-run is acceptable; idempotent upserts (BR-03) make re-runs safe |
| AVAIL-04 | Total failure threshold | Pipeline completes even if some PDFs fail; `IngestionReport.failed` tracks count |

---

## Security

| ID | Requirement | Notes |
|---|---|---|
| SEC-01 | AWS credential management | Credentials via IAM role (production ECS/EC2) or AWS profile (local dev). Never hardcoded. |
| SEC-02 | S3 access control | S3 bucket restricted to pipeline IAM role via bucket policy; no public access |
| SEC-03 | RDS access control | PostgreSQL instance in private VPC subnet; accessible only from pipeline execution environment |
| SEC-04 | Secrets management | All sensitive config (DB connection string, S3 bucket name) loaded from environment variables |
| SEC-05 | Data sensitivity | PDF content is course marketing material — not PII, not confidential; standard data handling applies |
| SEC-06 | Bedrock API access | Bedrock access via IAM role with least-privilege policy scoped to required models only |

---

## Reliability

| ID | Requirement | Notes |
|---|---|---|
| REL-01 | LLM retry policy | 3 retries with exponential backoff (1s, 2s, 4s) on keyword extraction failure (BR-09) |
| REL-02 | Embedding failure handling | If embedding generation fails for a chunk, that chunk is NOT persisted and the error is recorded in IngestionReport |
| REL-03 | Idempotency | Re-running the pipeline on the same PDFs produces the same chunks (deterministic IDs, upsert semantics) |
| REL-04 | Report persistence | `IngestionReport` is always saved at end of run, even on partial failure (BR-11) |
| REL-05 | Thread safety | Each PDF is processed independently; no shared mutable state across threads |

---

## Observability

| ID | Requirement | Notes |
|---|---|---|
| OBS-01 | Log output | Structured stdout logs — progress per PDF, errors, final summary |
| OBS-02 | Log file | Log file written to `reports/pipeline_{timestamp}.log` alongside the JSON report |
| OBS-03 | Log format | `[ISO-timestamp] [LEVEL] [course_name] message` |
| OBS-04 | Log levels | INFO for normal progress; WARNING for recoverable errors (LLM retry, missing section); ERROR for PDF failures |
| OBS-05 | Report as audit trail | `IngestionReport` JSON provides per-run stats: total, processed, failed, errors, duration |
| OBS-06 | No CloudWatch | Cloud-based log aggregation not required at this stage |

---

## Maintainability

| ID | Requirement | Notes |
|---|---|---|
| MAINT-01 | Configuration via env vars | All environment-specific config (S3 bucket, DB URL, model names, worker count) in environment variables |
| MAINT-02 | ENV abstraction | Provider selection is centralized in ENV resolver (BR-12) — adding a new ENV requires only new provider implementations |
| MAINT-03 | Testability | Providers (StorageProvider, EmbeddingsProvider, etc.) behind interfaces, enabling unit test mocking |
| MAINT-04 | Dependency isolation | Each provider type is independently replaceable without modifying pipeline orchestration logic |
