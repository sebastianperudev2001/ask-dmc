# NFR Requirements Plan — ingestion-pipeline

**Fecha**: 2026-04-29

## Execution Checkboxes
- [ ] Step 1: Analyze functional design artifacts
- [ ] Step 2: Generate NFR questions
- [ ] Step 3: Collect answers
- [ ] Step 4: Generate nfr-requirements.md
- [ ] Step 5: Generate tech-stack-decisions.md

---

## Context Summary

- **Type**: Offline batch pipeline (not a service — runs on-demand or triggered)
- **Scale**: ~26 PDFs currently, grows slowly as new courses are added
- **ENV split**: LOCAL (filesystem + Ollama + local vector DB) / PRODUCTION (S3 + Bedrock + cloud vector DB)
- **Critical TBD from requirements**: Vector DB technology not yet decided (candidates: OpenSearch Serverless, pgvector, Bedrock KB)
- **Functional design already handles**: error handling per PDF, retries for LLM calls, IngestionReport persistence

---

## NFR Questions

### Q1 — Vector DB (Production)

The requirements identified three candidates for the production vector DB. Which do you prefer?

**A) Amazon OpenSearch Serverless**
Fully managed, native AWS, supports metadata filtering, higher cost at low scale.

**B) pgvector on Amazon RDS (PostgreSQL)**
Familiar SQL interface, cost-effective at low scale, metadata filtering via SQL WHERE clauses, requires managing an RDS instance.

**C) Amazon Bedrock Knowledge Base**
Native Bedrock integration, fully serverless, limited control over chunking and retrieval logic since we have a custom pipeline.

[Answer]:

---

### Q2 — Vector DB (Local)

For the local ENV (development), which vector DB should we use?

**A) ChromaDB** — most common for local dev, runs in-process or as a local server, Python-native.

**B) pgvector on local PostgreSQL** — same tech as production (pgvector), requires Docker. Reduces prod/local divergence.

**C) Qdrant** — lightweight local server via Docker, good metadata filtering support.

[Answer]:

---

### Q3 — Pipeline Execution Mode

Should PDF processing be sequential or parallel?

**A) Sequential** — one PDF at a time, simpler error handling, easier to debug, sufficient for ~26 PDFs.

**B) Parallel (thread pool)** — process N PDFs concurrently, faster but more complex. Useful if the pipeline will run frequently or the catalog grows significantly.

[Answer]:

---

### Q4 — Pipeline Trigger Mechanism

How should the ingestion pipeline be triggered?

**A) Manual CLI script** — developer runs `python ingest.py` locally or via SSH/ECS task. No automation.

**B) S3 event trigger** — Lambda triggered automatically when a new PDF is uploaded to the S3 bucket. Fully automated.

**C) Scheduled (EventBridge)** — runs on a fixed schedule (e.g., nightly). Good if PDFs are updated in batch.

[Answer]:

---

### Q5 — Logging / Observability

What level of observability is needed for the pipeline?

**A) Structured stdout logs only** — print pipeline progress and errors to stdout. Simple, no infrastructure needed.

**B) Structured logs + CloudWatch** — emit structured logs to CloudWatch Logs in production for persistence and alerting.

[Answer]:
