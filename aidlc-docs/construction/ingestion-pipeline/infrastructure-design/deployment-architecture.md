# Deployment Architecture — ingestion-pipeline

**Fecha**: 2026-04-30
**Unit**: unit-1: ingestion-pipeline

---

## LOCAL Architecture

```
Developer Machine
┌─────────────────────────────────────────────────────────┐
│                                                         │
│  $ python -m ingestion.cli                              │
│         │                                               │
│         ▼                                               │
│  IngestionOrchestrator                                  │
│    ├── FilesystemStorageProvider                        │
│    │         └── knowledge_source/*.pdf                 │
│    ├── PDFParser (pdfplumber + regex)                   │
│    ├── KeywordsExtractor                                │
│    │         └──► Ollama :11434 (gemma3:4b)             │
│    ├── EmbeddingGenerator                               │
│    │         └──► Ollama :11434 (nomic-embed-text)      │
│    ├── VectorDBRepository                               │
│    │         └──► PostgreSQL :5432 (Docker)             │
│    │                   pgvector extension               │
│    └── FilesystemReportRepository                       │
│              └── reports/report_{ts}.json               │
│              └── reports/pipeline_{ts}.log              │
│                                                         │
└─────────────────────────────────────────────────────────┘

Docker Compose services:
  postgres (ankane/pgvector) → localhost:5432

Ollama (local process or Docker):
  → localhost:11434
```

---

## PRODUCTION Architecture (Future)

```
Manual Trigger                    EventBridge (future)
aws lambda invoke                 Scheduled rule
        │                                │
        └──────────────┬─────────────────┘
                       ▼
              ┌─────────────────┐
              │  AWS Lambda     │  Container image
              │  1024 MB / 15m  │  INGESTION_ENV=production
              │  VPC: private   │  INGESTION_WORKERS=4
              └────────┬────────┘
                       │
         ┌─────────────┼─────────────┐
         ▼             ▼             ▼
   ┌──────────┐  ┌──────────┐  ┌──────────────────┐
   │ Amazon   │  │ Amazon   │  │ Amazon RDS        │
   │    S3    │  │ Bedrock  │  │ PostgreSQL 15+    │
   │          │  │          │  │ pgvector          │
   │brochures/│  │titan-    │  │ db.t3.micro       │
   │reports/  │  │embed-v2  │  │ private subnet    │
   └──────────┘  │haiku-4-5 │  └──────────────────┘
                 └──────────┘

VPC Layout:
┌─────────────────────────────────────────┐
│  VPC (10.0.0.0/16)                      │
│                                         │
│  ┌──────────────┐  ┌──────────────┐     │
│  │ Private AZ-a │  │ Private AZ-b │     │
│  │ Lambda ENI   │  │              │     │
│  │ RDS (primary)│  │ RDS subnet   │     │
│  └──────────────┘  └──────────────┘     │
│                                         │
│  VPC Endpoints:                         │
│  → bedrock-runtime (Interface)          │
│  → s3 (Gateway — free)                  │
└─────────────────────────────────────────┘

Security Groups:
  lambda-sg  → outbound 5432 → rds-sg
             → outbound 443  → VPC endpoints (Bedrock, S3)
  rds-sg     → inbound  5432 ← lambda-sg only
```

---

## Migration Path: LOCAL → PRODUCTION

No code changes required. The ENV abstraction (PATTERN-02, BR-12) means the same pipeline binary runs in both environments. Only environment variables change:

| Step | Action |
|---|---|
| 1 | Build Docker container image with pipeline dependencies |
| 2 | Push image to Amazon ECR |
| 3 | Provision VPC + private subnets + VPC endpoints |
| 4 | Provision RDS PostgreSQL + enable pgvector extension |
| 5 | Create S3 bucket (`ask-dmc-knowledge`) + upload brochure PDFs |
| 6 | Create Lambda function from ECR image + configure env vars + attach VPC |
| 7 | Attach IAM role with S3 + Bedrock + VPC permissions |
| 8 | Test: `aws lambda invoke --function-name ask-dmc-ingestion-pipeline` |
| 9 | (Optional) Add EventBridge scheduled rule → Lambda |

---

## Dockerfile (Production Container)

```dockerfile
FROM public.ecr.aws/lambda/python:3.11

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY src/ ${LAMBDA_TASK_ROOT}/src/

CMD ["src.ingestion.lambda_handler.handler"]
```

**Lambda handler entry point**:
```python
def handler(event, context):
    config = IngestionConfig.from_env()
    orchestrator = IngestionOrchestrator(config)
    report = orchestrator.run()
    return {"processed": report.processed, "failed": report.failed}
```
