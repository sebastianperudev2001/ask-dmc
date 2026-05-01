# Integration Test Instructions — ingestion-pipeline

## Purpose

Verify that the pipeline components work correctly together against real infrastructure (pgvector PostgreSQL). These tests require Docker running.

---

## Prerequisites

```bash
cd services/ingestion
docker compose up -d          # starts pgvector on localhost:5432
source .venv/bin/activate
```

Verify DB is ready:
```bash
docker compose exec postgres psql -U ask_dmc -d ask_dmc -c "\dt"
# Expected: brochure_chunks table listed
```

---

## Scenario 1: VectorDBRepository — upsert and idempotency

**What is tested**: `PgVectorRepository.upsert()` writes chunks to the real pgvector DB. Re-upserting the same chunk ID produces the same row (no duplicates).

```python
# tests/integration/test_pgvector_repository.py (manual run)
import os, psycopg2
from pgvector.psycopg2 import register_vector
from src.domain.entities import EmbeddedChunk, SectionType
from src.infrastructure.vector_db.pgvector_repository import PgVectorRepository

conn = psycopg2.connect(os.environ["VECTOR_DB_URL"])
register_vector(conn)
repo = PgVectorRepository(conn)

chunk = EmbeddedChunk(
    id="test-course_objetivo",
    course_name="test-course",
    section_type=SectionType.OBJETIVO,
    content="Test content.",
    embedding=[0.1] * 1536,
    keywords=["test", "content"],
)

# First upsert
repo.upsert([chunk])

# Verify row exists
with conn.cursor() as cur:
    cur.execute("SELECT id FROM brochure_chunks WHERE id = %s", ("test-course_objetivo",))
    assert cur.fetchone() is not None

# Second upsert (same ID, updated content)
chunk.content = "Updated content."
repo.upsert([chunk])

# Verify still one row
with conn.cursor() as cur:
    cur.execute("SELECT COUNT(*) FROM brochure_chunks WHERE id = %s", ("test-course_objetivo",))
    count = cur.fetchone()[0]
    assert count == 1, f"Expected 1 row, got {count}"

# Cleanup
with conn.cursor() as cur:
    cur.execute("DELETE FROM brochure_chunks WHERE id = %s", ("test-course_objetivo",))
conn.commit()
conn.close()
print("✓ Upsert idempotency verified")
```

Run:
```bash
PYTHONPATH=. VECTOR_DB_URL=postgresql://ask_dmc:ask_dmc@localhost:5432/ask_dmc python -c "
exec(open('tests/integration/test_pgvector_repository.py').read())
"
```

---

## Scenario 2: Full pipeline run (LOCAL env, sample PDFs)

**What is tested**: End-to-end run of `IngestionOrchestrator` with real pgvector, real pdfplumber parsing, and mocked LLM/embeddings (to avoid Ollama dependency in CI).

**Setup**:
```bash
mkdir -p knowledge_source reports
# Add 1-2 sample PDF brochures to knowledge_source/
```

**Run with mocked LLM and embeddings** (no Ollama needed):
```bash
INGESTION_ENV=local \
VECTOR_DB_URL=postgresql://ask_dmc:ask_dmc@localhost:5432/ask_dmc \
LOCAL_KNOWLEDGE_DIR=knowledge_source \
LOCAL_REPORTS_DIR=reports \
PYTHONPATH=. python -c "
from unittest.mock import MagicMock, patch
from src.config import load_config
from src.pipeline.orchestrator import IngestionOrchestrator
from src.pipeline.provider_factory import create_providers

config = load_config()
providers = create_providers(config)

# Mock LLM and embeddings to avoid Ollama
providers.llm.complete = MagicMock(return_value='[\"kw1\", \"kw2\", \"kw3\"]')
providers.embeddings.embed = MagicMock(return_value=[0.1] * 1536)

report = IngestionOrchestrator(config, providers).run()
print(f'Processed: {report.processed}, Failed: {report.failed}')
print(f'Chunks upserted: {report.total_chunks_upserted}')
assert report.processed + report.failed == report.total_pdfs
providers.close()
"
```

**Expected output**:
```
Processed: N, Failed: 0
Chunks upserted: M
```

**Verify chunks in DB**:
```bash
docker compose exec postgres psql -U ask_dmc -d ask_dmc \
  -c "SELECT id, course_name, section_type FROM brochure_chunks LIMIT 10;"
```

---

## Scenario 3: IngestionReport persisted to filesystem

**What is tested**: After a run, `reports/report_<timestamp>.json` and `reports/pipeline_<timestamp>.log` exist and are valid.

```bash
ls reports/
# Expected: report_YYYYMMDDTHHMMSSZ.json  pipeline_YYYYMMDDTHHMMSSZ.log

python -c "
import json, glob
reports = sorted(glob.glob('reports/report_*.json'))
assert reports, 'No report file found'
report = json.load(open(reports[-1]))
assert 'processed' in report
assert 'failed' in report
assert report['processed'] + report['failed'] == report['total_pdfs']
print(f'✓ Report valid: {report}')
"
```

---

## Cleanup

```bash
# Remove test chunks from DB
docker compose exec postgres psql -U ask_dmc -d ask_dmc \
  -c "TRUNCATE TABLE brochure_chunks;"

# Remove test reports
rm -rf reports/

# Stop Docker
docker compose down
```
