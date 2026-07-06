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

---

# Performance Test Instructions — agent-service

## Performance Requirements (requirements.md §9.1, heredado — no específico de plataforma)

| Requirement | Target |
|---|---|
| Primer `recommendation_delta` | ≤ 3 segundos desde `recommendation_request` (o `relax_filters_response` confirmando) |
| Filtro SQL + embedding + ranking (pasos 2-7) | Debe dejar presupuesto suficiente del objetivo de 3s antes de invocar al agente |

## Prerequisites
- Recursos Azure reales desplegados (Container Apps + Postgres + Azure OpenAI + Foundry) — este test mide latencia de red real, no tiene sentido solo contra fakes locales.

## Test 1: Tiempo hasta el primer delta (end-to-end)

```python
import asyncio, json, time, websockets

async def main():
    async with websockets.connect("wss://<container-app-fqdn>/ws/recommendation") as ws:
        start = time.monotonic()
        await ws.send(json.dumps({
            "type": "recommendation_request", "budget": "3000.00", "max_duration_weeks": 10,
            "professional_background": "Data Engineer en Yape", "desired_stack": "Data Science",
        }))
        msg = json.loads(await ws.recv())
        elapsed = time.monotonic() - start
        print(f"Primer mensaje ({msg['type']}) en {elapsed:.2f}s")

asyncio.run(main())
```

**Expected**: `elapsed < 3.0` para el primer mensaje relevante (`relax_filters_offer`, `no_exact_match_showing_all`, o el primer `recommendation_delta`).

## Test 2: Impacto de cold start (PATTERN-04, min_replicas=1)

Con `min_replicas: 1` en Container Apps, no debería haber cold start en el flujo normal.
**Verificar en el portal de Azure** (Container Apps → Revisions → Replicas) que siempre hay
≥1 réplica activa; si `min_replicas` se reconfigura a 0 en algún momento, repetir Test 1
inmediatamente después de un período idle (>5 min) para confirmar si el objetivo de 3s se
incumple — este es precisamente el riesgo que `min_replicas=1` fue elegido para evitar.

## Test 3: Latencia del pipeline de filtro/ranking (sin el agente)

Aislar pasos 2-7 (sin invocar al agente) para saber cuánto presupuesto de los 3s consumen:

```python
import time
# dentro de un shell con acceso a PostgresCourseRepository ya configurado
start = time.monotonic()
candidates = await repo.find_ranked_candidates(query_embedding, max_price=3000, max_duration_weeks=10, limit=3)
print(f"Filtro + ranking pgvector: {time.monotonic() - start:.3f}s")
```

**Expected**: < 0.5s (dado el tamaño del catálogo — decenas de cursos, índices HNSW/B-tree en su lugar).

## Interpreting Results

| Outcome | Action |
|---|---|
| Primer delta > 3s con `min_replicas=1` | Perfilar latencia de red hacia Azure OpenAI/Foundry (región East US vs ubicación del cliente); considerar reducir el modelo de chat si la latencia del LLM domina |
| Filtro/ranking > 0.5s | Verificar que el índice HNSW existe (`\d courses` en psql) y que `ANALYZE courses;` se corrió tras el seed |
| Cold start incumple 3s con `min_replicas=0` | Confirmar que `min_replicas=1` está aplicado (PATTERN-04) — no se recomienda scale-to-zero para este servicio |
