# Performance Test Instructions — ingestion-pipeline

## Performance Requirements (from NFR PERF-01 to PERF-04)

| Requirement | Target |
|---|---|
| Full catalog ingestion time | < 10 minutes for ~26 PDFs |
| Worker throughput | Linear improvement with INGESTION_WORKERS |
| DB upsert latency | Negligible at current scale (~312 chunks) |

---

## Prerequisites

- Docker running (`docker compose up -d`)
- `knowledge_source/` populated with real PDF brochures (or a representative sample)
- `time` command available (macOS/Linux built-in)

---

## Test 1: End-to-end wall-clock time

Measure total pipeline duration for the full catalog.

```bash
cd services/ingestion
source .venv/bin/activate

# With real Ollama (most accurate)
time PYTHONPATH=. python cli.py

# Check IngestionReport for pipeline-measured duration
cat reports/$(ls -t reports/report_*.json | head -1) | python -c "
import json, sys
r = json.load(sys.stdin)
print(f'Pipeline duration: {r[\"duration_seconds\"]:.2f}s')
print(f'PDFs: {r[\"total_pdfs\"]}, Processed: {r[\"processed\"]}, Failed: {r[\"failed\"]}')
print(f'Chunks: {r[\"total_chunks_upserted\"]}')
"
```

**Expected**: `duration_seconds < 600` (10 minutes)

---

## Test 2: Worker count vs. throughput

Measure how wall-clock time scales with `INGESTION_WORKERS`.

```bash
for workers in 1 2 4 8; do
  echo "--- INGESTION_WORKERS=$workers ---"
  INGESTION_WORKERS=$workers PYTHONPATH=. python -c "
import time
from src.config import load_config
from src.pipeline.orchestrator import IngestionOrchestrator
from src.pipeline.provider_factory import create_providers

config = load_config()
providers = create_providers(config)
start = time.monotonic()
report = IngestionOrchestrator(config, providers).run()
elapsed = time.monotonic() - start
providers.close()
print(f'Workers={config.ingestion_workers} | Time={elapsed:.1f}s | Processed={report.processed}')
"
done
```

**Expected**: Time decreases as workers increase (I/O-bound workload). Diminishing returns above 4 workers for ~26 PDFs.

---

## Test 3: DB upsert performance

Verify upsert throughput is not a bottleneck.

```bash
PYTHONPATH=. python -c "
import time, psycopg2, os
from pgvector.psycopg2 import register_vector
from src.domain.entities import EmbeddedChunk, SectionType
from src.infrastructure.vector_db.pgvector_repository import PgVectorRepository

conn = psycopg2.connect(os.environ['VECTOR_DB_URL'])
register_vector(conn)
repo = PgVectorRepository(conn)

chunks = [
    EmbeddedChunk(
        id=f'perf-test_{i}',
        course_name='perf-test',
        section_type=SectionType.OBJETIVO,
        content=f'Content {i}',
        embedding=[float(i % 10) / 10] * 1536,
        keywords=['test'],
    )
    for i in range(312)
]

start = time.monotonic()
repo.upsert(chunks)
elapsed = time.monotonic() - start
print(f'Upserted 312 chunks in {elapsed:.3f}s ({312/elapsed:.0f} chunks/s)')

# Cleanup
with conn.cursor() as cur:
    cur.execute(\"DELETE FROM brochure_chunks WHERE id LIKE 'perf-test_%'\")
conn.commit()
conn.close()
" VECTOR_DB_URL=postgresql://ask_dmc:ask_dmc@localhost:5432/ask_dmc
```

**Expected**: 312 chunks upserted in < 2 seconds.

---

## Interpreting Results

| Outcome | Action |
|---|---|
| Pipeline > 10 min | Increase `INGESTION_WORKERS` or profile LLM call latency |
| DB upsert slow | Check pgvector index — run `ANALYZE brochure_chunks;` |
| LLM bottleneck | Confirm retry backoff is not inflating time; check Ollama/Bedrock latency |
| Workers don't help | Check if GIL is a bottleneck on CPU-bound steps (unlikely for this I/O-heavy pipeline) |
