# Build and Test Summary — ingestion-pipeline

**Fecha**: 2026-04-30
**Unit**: unit-1: ingestion-pipeline
**Scope**: unit-1 only (units 2–5 pending construction)

---

## Build Status

| Item | Status | Notes |
|---|---|---|
| Python 3.11+ | Required | `python --version` |
| Dependencies | `pip install -r requirements-dev.txt` | pdfplumber, psycopg2-binary, pgvector, boto3, hypothesis |
| Docker pgvector | `docker compose up -d` | auto-runs migration on first start |
| Ollama models | `ollama pull nomic-embed-text && ollama pull gemma3:4b` | LOCAL env only |
| Build artifacts | `services/ingestion/` | Python source tree, no compiled artifacts |

---

## Test Execution Summary

### Unit Tests

| Suite | Test File | Tests | Coverage Target |
|---|---|---|---|
| PDFParser | `test_pdf_parser.py` | 9 | Shape, content, validation |
| KeywordsExtractor | `test_keywords_extractor.py` | 8 | Success, retry, failure |
| EmbeddingGenerator | `test_embedding_generator.py` | 9 | Output, ID, enrich |
| Orchestrator | `test_orchestrator.py` | 5 | Totals, errors, report |
| **Total** | | **~31** | **≥ 80% `src/pipeline/`** |

Run: `make test-unit`

### Property-Based Tests (Hypothesis)

| Property | Rule | Category | Examples |
|---|---|---|---|
| Always 12 sections | BR-01 | Invariant | 100 |
| All SectionTypes represented | BR-01 | Invariant | 100 |
| `not present → content == ""` | BR-02 | Invariant | 100 |
| course_name preserved | — | Invariant | 100 |
| Chunk ID deterministic | BR-03 | Invariant | 200 |
| keywords ≤ 10 | BR-08 | Invariant | 100 |
| `processed + failed == total` | — | Invariant | 200 |
| **Total** | | | **~900 generated cases** |

Run: `make test-pbt`

### Integration Tests

| Scenario | Requires | Instructions |
|---|---|---|
| pgvector upsert + idempotency | Docker | `integration-test-instructions.md` Scenario 1 |
| Full pipeline run (mocked LLM) | Docker + sample PDFs | Scenario 2 |
| IngestionReport persistence | Docker | Scenario 3 |

### Performance Tests

| Test | Target | Instructions |
|---|---|---|
| Full catalog < 10 min | PERF-01 | `performance-test-instructions.md` Test 1 |
| Worker scaling | Linear I/O improvement | Test 2 |
| DB upsert throughput | 312 chunks < 2s | Test 3 |

### Security Tests

| Check | How |
|---|---|
| No hardcoded credentials | `grep -r "password\|secret\|key" src/` — should return no values |
| Dependency vulnerabilities | `pip-audit` or `safety check` |
| Input validation | Covered by unit tests (empty bytes, empty course_name) |

### Contract / E2E Tests

| Type | Status | Notes |
|---|---|---|
| Contract tests | N/A | No API exposed by unit-1 |
| E2E tests | Deferred | Requires units 2–5; integration point is pgvector (US-18) |

---

## Overall Status

| Category | Status |
|---|---|
| Build | Ready — instructions provided |
| Unit tests | Ready to run — `make test-unit` |
| PBT tests | Ready to run — `make test-pbt` |
| Integration tests | Ready — requires Docker + sample PDFs |
| Performance tests | Ready — requires full catalog |
| Operations readiness | unit-1 complete; full system readiness after units 2–5 |

---

## Quick Start

```bash
cd services/ingestion
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
docker compose up -d
make test          # unit + PBT (no Docker needed)
make test-unit     # unit tests only
make test-pbt      # Hypothesis PBT only
```
