# Infrastructure Design Plan — ingestion-pipeline

**Fecha**: 2026-04-30

## Execution Checkboxes

- [x] Step 1: Analyze design artifacts
- [x] Step 2: Collect answers
- [x] Step 3: Generate infrastructure-design.md
- [x] Step 4: Generate deployment-architecture.md

---

## Questions

### Q1 — Production Execution Environment

When the pipeline is triggered manually in production, where does it actually run?

**A) Developer's local machine with AWS credentials configured**
Run `python ingest.py` locally; machine has an AWS profile or env vars with access to S3 + Bedrock + RDS.

**B) AWS ECS one-time task (Fargate)**
Package pipeline as a Docker image; run as an ECS task on-demand from CLI (`aws ecs run-task`). No persistent server needed.

**C) EC2 instance**
A dedicated or shared EC2 instance is SSH'd into to run the pipeline script.

[Answer]: Lambda. For now it will run locally. But in the future we could run it as a Lambda function.

---

### Q2 — AWS VPC / Network Setup

Is there an existing VPC (with private subnets) for this project, or is this a fresh AWS setup?

**A) Fresh setup — no existing VPC or AWS infrastructure**
Everything (VPC, subnets, security groups, RDS) needs to be provisioned from scratch.

**B) Existing VPC with private subnets**
The RDS instance and pipeline execution will be placed in an existing VPC. Subnets and security groups already exist or can be reused.

[Answer]: A "but for the future. Now i just want the scrip locally"

### Q3 — RDS Instance

Should a new RDS PostgreSQL instance be provisioned, or is there an existing one we can add pgvector to?

**A) New RDS instance**
Provision a fresh `db.t3.micro` or `db.t3.small` PostgreSQL instance with pgvector enabled.

**B) Existing RDS / PostgreSQL instance**
Add pgvector extension to an existing instance (`CREATE EXTENSION vector;`).

[Answer]: A
