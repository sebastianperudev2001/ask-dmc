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
