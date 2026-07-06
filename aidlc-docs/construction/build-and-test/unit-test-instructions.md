# Unit Test Execution — ingestion-pipeline

## Overview

Unit tests use `pytest` with `unittest.mock` for isolation. No Docker, no Ollama, no real PDFs required — all external dependencies are mocked.

PBT tests use `hypothesis` to generate random inputs and verify invariants.

---

## Run All Tests

```bash
cd services/ingestion
source .venv/bin/activate

# All tests (unit + PBT)
make test
# or manually:
PYTHONPATH=. pytest tests/ -v --tb=short
```

---

## Run Unit Tests Only

```bash
make test-unit
# or:
PYTHONPATH=. pytest tests/unit/ -v --tb=short
```

Expected output:
```
tests/unit/test_pdf_parser.py::TestPDFParserOutputShape::test_always_returns_12_sections PASSED
tests/unit/test_pdf_parser.py::TestPDFParserOutputShape::test_all_12_section_types_present PASSED
... (20+ tests)
======= X passed in Xs =======
```

---

## Run Property-Based Tests Only

```bash
make test-pbt
# or:
PYTHONPATH=. pytest tests/pbt/ -v --tb=short
```

Hypothesis runs each property 100–200 times with generated inputs. Expected output:
```
tests/pbt/test_pdf_parser_properties.py::test_always_produces_exactly_12_sections PASSED
tests/pbt/test_chunk_properties.py::test_chunk_id_is_deterministic PASSED
... (7 properties)
======= X passed in Xs =======
```

---

## Run with Coverage

```bash
PYTHONPATH=. pytest tests/unit/ --cov=src --cov-report=term-missing
```

Target coverage: **≥ 80%** for `src/pipeline/` modules.

---

## Test Files Reference

| File | Components Tested | Key Assertions |
|---|---|---|
| `tests/unit/test_pdf_parser.py` | PDFParser | Always 12 sections, present/absent logic, input validation |
| `tests/unit/test_keywords_extractor.py` | KeywordsExtractor | Retry logic, graceful failure → `[]`, truncation to 10 |
| `tests/unit/test_embedding_generator.py` | EmbeddingGenerator | Deterministic ID, enrich text format, keyword truncation |
| `tests/unit/test_orchestrator.py` | IngestionOrchestrator | `processed + failed == total`, error accumulation, report saved |
| `tests/pbt/test_pdf_parser_properties.py` | PDFParser | BR-01, BR-02 invariants over 100 generated inputs |
| `tests/pbt/test_chunk_properties.py` | EmbeddingGenerator, IngestionReport | BR-03, BR-08 determinism, report totals invariant |

---

## Fixing Failing Tests

1. Read the full pytest output — it prints the failing assertion and the generated input (for PBT, the shrunk minimal case)
2. For PBT failures, Hypothesis prints the seed: `Falsifying example: ...` — replay with `--hypothesis-seed=<seed>`
3. Fix the source code, not the tests, unless the test expectation itself is wrong

---

# Unit Test Execution — agent-service

## Overview

Tests use `pytest` + `hypothesis` + `pytest-asyncio`. Most tests need **no external services** —
`RecommendationOrchestrator` and `WebSocketConnectionHandler` are tested against
`InMemoryCourseRepository` and fake ports (`tests/unit/fakes.py`, `tests/integration/fakes.py`).
Only `tests/unit/test_postgres_repository.py` needs a real Postgres+pgvector instance.

## Run All Tests

```bash
cd services/agent-service
source .venv/bin/activate
pytest -v
```

**Resultado verificado en esta sesión** (sin `TEST_DATABASE_URL`, dependencias Azure-specific no instaladas):
```
20 passed, 2 skipped in 1.35s
```
Los 2 `SKIPPED` son `test_p6_pgvector_ranking_matches_numpy_oracle` y
`test_p1_p2_filter_and_relaxation_against_real_db` — se activan con `TEST_DATABASE_URL` (ver abajo).

## Run With Real Postgres (incluye P6 — oracle pgvector vs NumPy)

```bash
docker run -d -p 5432:5432 -e POSTGRES_PASSWORD=test pgvector/pgvector:pg16
psql "postgresql://postgres:test@localhost:5432/postgres" -f migrations/001_create_courses.sql
TEST_DATABASE_URL=postgresql://postgres:test@localhost:5432/postgres pytest tests/unit/test_postgres_repository.py -v
```

## Run With Coverage

```bash
pytest --cov=src --cov-report=term-missing
```

## Test Files Reference

| File | Componente | Propiedades/Escenarios clave |
|---|---|---|
| `tests/unit/test_orchestrator_properties.py` | `RecommendationOrchestrator` + `InMemoryCourseRepository` | P1 (filtro), P2 (monotonicidad relajación), P3 (determinismo), P4 (top-K), P5 (orden), P7 (embedding_text), P8 (rango similarity) |
| `tests/unit/test_orchestrator_examples.py` | `RecommendationOrchestrator` | Match exacto, relajación confirmada/rechazada, relajación también vacía, catálogo vacío, validación BR-09 |
| `tests/unit/test_retry_policy.py` | `RetryPolicy` | Éxito tras N fallos, excepción tras agotar intentos |
| `tests/unit/test_postgres_repository.py` | `PostgresCourseRepository` | **P6** (oracle real vs NumPy), P1/P2 contra DB real — requiere `TEST_DATABASE_URL` |
| `tests/integration/test_websocket_flow.py` | `WebSocketConnectionHandler` | Flujo completo WS: match exacto, relajación confirmada/declinada, catálogo vacío, request inválido |

## Fixing Failing Tests

1. Un test de `test_orchestrator_examples.py`/`test_websocket_flow.py` falla por datos de fixture (precio/duración) que no ejercitan la rama esperada del algoritmo BR-03 → revisar los comentarios junto a cada `Course` de prueba antes de asumir que es un bug de `orchestrator.py` (ya ocurrió una vez en esta sesión, ver audit.md).
2. Para fallas de Hypothesis, replay con el seed impreso en la salida (`Falsifying example: ...`).
