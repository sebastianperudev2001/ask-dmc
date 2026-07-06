# Business Logic — Code Generation Summary (agent-service, Incremento 1)

## Generado

- **Dominio** (`services/agent-service/src/domain/models.py`): `Course` (con `embedding_text()`), `RecommendationRequest` (valida BR-09 en `__post_init__`), `ProfileQuery`, `RecommendationCandidate`, `RecommendationResponse`, `RecommendationBranch` (exact/relaxed/full_catalog).
- **Puertos** (`services/agent-service/src/ports/`): `CourseRepository` (filtro+ranking combinados, ver business-logic-model.md paso 6), `EmbeddingService`, `RecommendationAgentClient`.
- **Orquestador** (`services/agent-service/src/domain/orchestrator.py`): `RecommendationOrchestrator.start()` (pasos 2-3) y `.resolve_after_confirmation()` (paso 3d) — implementa BR-01 a BR-11 sin dependencias de infraestructura.

## Tests generados

- `tests/unit/generators.py` — generadores Hypothesis de `Course`/`RecommendationRequest` (PBT-07).
- `tests/unit/fakes.py` — `InMemoryCourseRepository` (ranking vía NumPy cosine similarity) para tests rápidos sin DB.
- `tests/unit/test_orchestrator_properties.py` — P1, P2, P3, P4, P5, P7, P8 (business-logic-model.md §6). **P6 (oracle pgvector vs NumPy) se difiere a `tests/unit/test_postgres_repository.py`** (Paso 18) — solo verificable contra Postgres real.
- `tests/unit/test_orchestrator_examples.py` — PBT-10: match exacto, oferta de relajación confirmada/rechazada, relajación también vacía (salta a catálogo completo), catálogo vacío, validación de `RecommendationRequest`.

## Cobertura de Business Rules

| BR | Cubierta en |
|---|---|
| BR-01, BR-02 | `orchestrator.start()` paso 2 (filtro exacto) + P1 |
| BR-03 | `orchestrator.start()`/`resolve_after_confirmation()` + P2, P3 + ejemplos de relajación |
| BR-04 | Ranking delegado a `CourseRepository` (ver Paso 14) |
| BR-05 | `TOP_K = 3` en `orchestrator.py` + P4 |
| BR-06 | Embeddings de catálogo se generan offline (ver Paso 21, seed script) — no en el orquestador |
| BR-07 | Se aplica en `RecommendationAgentClient`/prompt (Paso 16), no en el orquestador |
| BR-08 | Ninguna entidad de este módulo se persiste — solo `Course` vía `CourseRepository` |
| BR-09 | `RecommendationRequest.__post_init__` |
| BR-10 | No implementado (fuera de alcance de este incremento) |
| BR-11 | `orchestrator._full_catalog()` + ejemplo de catálogo vacío/relajación vacía |

Pendiente de otras capas (no de este stage): P6 real (Paso 18), guardrail BR-07 en el prompt del agente (Paso 16), embeddings de catálogo (Paso 21).
