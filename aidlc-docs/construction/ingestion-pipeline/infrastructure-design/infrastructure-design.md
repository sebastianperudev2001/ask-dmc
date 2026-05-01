# Infrastructure Design — ingestion-pipeline

**Fecha**: 2026-04-30
**Unit**: unit-1: ingestion-pipeline

---

## Overview

The pipeline has two distinct infrastructure profiles:

| Aspect | LOCAL (now) | PRODUCTION (future) |
|---|---|---|
| Execution | Python script on developer machine | AWS Lambda (container image) |
| Storage | Filesystem (`knowledge_source/`) | Amazon S3 |
| Vector DB | pgvector on PostgreSQL via Docker | pgvector on Amazon RDS PostgreSQL |
| Embeddings | Ollama (local) | Amazon Bedrock |
| Keywords LLM | Ollama (local) | Amazon Bedrock (claude-haiku-4-5) |
| Reports | Filesystem (`reports/`) | Amazon S3 |
| Trigger | `python -m ingestion.cli` | `aws lambda invoke` (manual) → EventBridge (future) |
| Networking | Localhost | AWS VPC (private subnet) |

---

## LOCAL Environment

### Components

**1. Docker Compose — pgvector PostgreSQL**
- Image: `ankane/pgvector`
- Port: `5432` (localhost)
- Database: `ask_dmc`
- Volume: `pgdata` (persistent across restarts)
- pgvector extension enabled at container startup

**2. Ollama**
- Runs as a local process or Docker container
- Port: `11434` (localhost)
- Models required:
  - Embeddings: `nomic-embed-text` (or equivalent)
  - Keywords: `gemma3:4b` (or `llama3.2:3b`)
- Pull before first run: `ollama pull nomic-embed-text && ollama pull gemma3:4b`

**3. Filesystem**
- `knowledge_source/` — PDF brochures input directory
- `reports/` — IngestionReport JSON + pipeline log output

**4. Environment Variables (`.env`)**
```env
INGESTION_ENV=local
INGESTION_WORKERS=4
VECTOR_DB_URL=postgresql://ask_dmc:ask_dmc@localhost:5432/ask_dmc
OLLAMA_BASE_URL=http://localhost:11434
KEYWORDS_MODEL=gemma3:4b
LOCAL_KNOWLEDGE_DIR=knowledge_source/
LOCAL_REPORTS_DIR=reports/
```

### Prerequisites for Local Run
1. Docker Desktop running
2. `docker compose up -d` (starts pgvector PostgreSQL)
3. Ollama running with required models pulled
4. `knowledge_source/` directory populated with PDF brochures
5. Python virtualenv with dependencies installed

---

## PRODUCTION Environment (Future)

### Compute — AWS Lambda (Container Image)

**Rationale**: Lambda is the natural fit for an infrequently-triggered batch pipeline — zero idle cost, scales automatically, and integrates cleanly with both manual invocation and future EventBridge scheduling.

**Configuration**:
- Runtime: Container image (required for pdfplumber, psycopg2, pgvector Python deps)
- Memory: 1024 MB
- Timeout: 900 seconds (15 min max — sufficient for ~26 PDFs at ~4 workers)
- Architecture: x86_64
- VPC: Yes — must be placed in private subnet to access RDS

**Invocation (manual)**:
```bash
aws lambda invoke \
  --function-name ask-dmc-ingestion-pipeline \
  --payload '{}' \
  response.json
```

**Future trigger**: EventBridge rule → Lambda (no code changes needed — same handler)

**IAM Role permissions**:
- `s3:GetObject`, `s3:ListBucket` on brochures bucket/prefix
- `s3:PutObject` on reports prefix
- `bedrock:InvokeModel` for `amazon.titan-embed-text-v2:0` and `claude-haiku-4-5`
- VPC network interface permissions (auto-attached by Lambda VPC config)

---

### Storage — Amazon S3

**Bucket**: `ask-dmc-knowledge` (single bucket, prefixed)

| Prefix | Purpose |
|---|---|
| `brochures/` | Input PDF brochures |
| `reports/` | IngestionReport JSON output |

**Access**: Private bucket, accessible only via IAM role attached to Lambda.

---

### Vector DB — Amazon RDS PostgreSQL with pgvector

**Instance**: New `db.t3.micro` (sufficient for ~312 chunks at current scale)

**Configuration**:
- Engine: PostgreSQL 15+
- Extension: `pgvector` (available on RDS PostgreSQL 15+)
- Placement: Private VPC subnet (no public access)
- Security group: Allow inbound `5432` from Lambda security group only
- Storage: 20 GB gp3 (more than sufficient)
- Multi-AZ: No (batch pipeline, downtime during maintenance acceptable)

**Connection**: Lambda connects via `VECTOR_DB_URL` environment variable (stored in Lambda config, not in code).

---

### Networking — AWS VPC

**Setup**: Fresh VPC provisioned for this project.

| Resource | Spec |
|---|---|
| VPC | `/16` CIDR |
| Private subnets | 2 AZs (required for RDS subnet group) |
| RDS subnet group | Both private subnets |
| Lambda VPC config | Same private subnets |
| Security group: Lambda | Outbound: 5432 to RDS SG, 443 to AWS services |
| Security group: RDS | Inbound: 5432 from Lambda SG only |

**Note**: Lambda needs internet access for Bedrock API calls. Since it's in a private subnet with no NAT gateway, a **VPC Endpoint** for Bedrock is required (or add a NAT gateway).

Recommended: VPC Interface Endpoints for:
- `com.amazonaws.[region].bedrock-runtime`
- `com.amazonaws.[region].s3` (Gateway endpoint — free)

---

### Environment Variables (Lambda)

```
INGESTION_ENV=production
INGESTION_WORKERS=4
VECTOR_DB_URL=<RDS connection string — from Secrets Manager or Lambda env>
S3_BUCKET=ask-dmc-knowledge
S3_BROCHURES_PREFIX=brochures/
S3_REPORTS_PREFIX=reports/
BEDROCK_EMBEDDINGS_MODEL=amazon.titan-embed-text-v2:0
KEYWORDS_MODEL=claude-haiku-4-5
```
