# Code Generation Plan — agent-service (Azure) — Incremento 1

**Fecha**: 2026-07-05
**Workspace root**: `/Users/sebastianchavarry/Documents/ask-dmc` (proyecto Greenfield, multi-unit tipo microservicios — patrón ya usado por `services/ingestion/`)
**Código de aplicación**: `services/agent-service/` (directorio nuevo — NO se reutiliza `services/api/`, que es el stub AWS/Strands superseded por DIV-10, y se deja intacto como referencia histórica)
**Documentación de este stage**: `aidlc-docs/construction/agent-service/code/`

Este plan es la única fuente de verdad para la generación de código de este incremento. No hay pasos de frontend (fuera de alcance — ver Functional Design Sección 5).

## Contexto y trazabilidad

- **Unidad**: `agent-service` (redefinición Azure de `unit-2`, ver DIV-10 en aidlc-state.md)
- **Incremento**: 1 de N — catálogo de cursos + recomendación por perfil
- **Dependencias**: ninguna dependencia de otras unidades para este incremento (no depende de `unit-1`, cuyo Vector DB en AWS no se reutiliza — ver Functional Design, fuente de datos = seed manual)
- **Nota de trazabilidad**: este incremento NO mapea a las historias de usuario originales US-01..18 (`aidlc-docs/inception/user-stories/stories.md`), que fueron escritas para el flujo completo AWS/Strands. La trazabilidad de este incremento es contra las Business Rules (BR-01 a BR-11) y Testable Properties (P1-P8) de `aidlc-docs/construction/agent-service/functional-design/`.
- **Interfaces esperadas**: WebSocket público (contrato en `business-logic-model.md` Sección 3) — sin autenticación (SECURITY-08, excepción documentada).
- **Entidades de base de datos propiedad de esta unidad**: tabla `courses` (Postgres + pgvector).

---

## Pasos

### Project Structure Setup (Greenfield)
- [x] **Paso 1** — Crear estructura de directorios en `services/agent-service/`: `src/domain/`, `src/ports/`, `src/adapters/`, `src/api/`, `tests/unit/`, `tests/integration/`, `migrations/`. Archivos de proyecto: `pyproject.toml` (Python, dependencias: `fastapi`, `uvicorn`, `asyncpg`, `agent-framework`, `azure-identity`, `azure-keyvault-secrets`, `hypothesis`, `pytest`, `pytest-asyncio`), `.env.example`, `Dockerfile`.

### Business Logic Generation
- [x] **Paso 2** — Dominio (`src/domain/models.py`): `Course`, `RecommendationRequest`, `ProfileQuery`, `RecommendationCandidate`, `RecommendationResponse` (domain-entities.md) como `dataclass`/Pydantic models, sin dependencias de infraestructura.
- [x] **Paso 3** — Puertos (`src/ports/`): `CourseRepository`, `EmbeddingService`, `RecommendationAgentClient` como `Protocol` (logical-components.md).
- [x] **Paso 4** — `RecommendationOrchestrator` (`src/domain/orchestrator.py`): algoritmo completo de `business-logic-model.md` Sección 2 (pasos 1-9, incl. rama BR-03/BR-11), recibiendo los puertos inyectados. Traza: BR-01 a BR-11.

### Business Logic Unit Testing (PBT-01 a PBT-10)
- [x] **Paso 5** — Generadores de dominio con Hypothesis (`tests/unit/generators.py`) para `Course` y `RecommendationRequest` respetando constraints de negocio (PBT-07).
- [x] **Paso 6** — Tests de propiedades (`tests/unit/test_orchestrator_properties.py`) para P1-P8 (business-logic-model.md Sección 6): invariantes de filtro (P1), monotonicidad de relajación (P2), idempotencia del cálculo ampliado (P3), límite top-K (P4), orden por similarity_score (P5), oracle de similitud coseno vs NumPy (P6, diferido a Paso 18 contra Postgres real), contención de curriculum en embedding_text (P7), rango de similarity_score (P8).
- [x] **Paso 7** — Tests de ejemplo (`tests/unit/test_orchestrator_examples.py`, PBT-10) para escenarios críticos: filtro exacto con candidatos, relajación con confirmación aceptada/rechazada, catálogo completo (BR-11), catálogo vacío.
- [x] **Paso 8** — Documentar resumen de Business Logic (`aidlc-docs/construction/agent-service/code/business-logic-summary.md`): qué se generó, cobertura de BR/propiedades.

### API Layer Generation
- [x] **Paso 9** — `WebSocketConnectionHandler` (`src/api/websocket_handler.py`, FastAPI WS route): parseo de `recommendation_request`/`relax_filters_response`, invocación al orquestador, emisión de `recommendation_delta`/`recommendation_done`/`relax_filters_offer`/`no_exact_match_showing_all`/`no_recommendation`. Incluye el timeout de 5 min (PATTERN-02) y el manejador global de errores (PATTERN-03/SECURITY-15).
- [x] **Paso 10** — Validación de input (`src/api/schemas.py`, SECURITY-05): schemas Pydantic para los mensajes WS entrantes con bounds explícitos.
- [x] **Paso 11** — `main.py` / app FastAPI: wiring de dependencias (inyección de adaptadores concretos), logging estructurado (SECURITY-03), Managed Identity para auth con Azure OpenAI/Foundry/Key Vault.

### API Layer Unit Testing
- [x] **Paso 12** — Tests de integración WS (`tests/integration/test_websocket_flow.py`) con adaptadores fake: flujo completo request→respuesta, flujo con oferta de relajación aceptada/rechazada, catálogo vacío, request inválido. Timeout real de relajación no automatizado (ver gap documentado en api-layer-summary.md).
- [x] **Paso 13** — Documentar resumen de API Layer (`aidlc-docs/construction/agent-service/code/api-layer-summary.md`).

### Repository Layer Generation
- [x] **Paso 14** — `PostgresCourseRepository` (`src/adapters/postgres_course_repository.py`): queries parametrizadas para filtro duro (BR-01/02) y ranking pgvector (BR-04/BR-11, PATTERN-06/07), usando `ConnectionPool` (`src/adapters/connection_pool.py`, `asyncpg`, PATTERN-09).
- [x] **Paso 15** — `AzureOpenAIEmbeddingService` (`src/adapters/azure_openai_embedding.py`): llamada a `text-embedding-3-small` envuelta en `RetryPolicy` (`src/adapters/retry_policy.py`, PATTERN-01).
- [x] **Paso 16** — `FoundryPersistentAgentClient` (`src/adapters/foundry_agent_client.py`): invocación al Persistent Agent vía Agent Framework SDK (`agent.run(..., stream=True)`), traduciendo `AgentRunResponseUpdate.text` a eventos de dominio, envuelto en `RetryPolicy`.
- [x] **Paso 17** — `SecretsProvider` (`src/adapters/keyvault_secrets.py`): resolución de secrets vía Key Vault (PATTERN-11).

### Repository Layer Unit Testing
- [x] **Paso 18** — Tests unitarios de adaptadores (`tests/unit/test_postgres_repository.py`, `test_retry_policy.py`) — `RetryPolicy` testeado con Hypothesis. Tests de repositorio (P1/P2/P6) contra una instancia de Postgres de test real (fixture `TEST_DATABASE_URL`, skip si no está configurada — no mock de SQL).
- [x] **Paso 19** — Documentar resumen de Repository Layer (`aidlc-docs/construction/agent-service/code/repository-layer-summary.md`).

### Database Migration Scripts
- [x] **Paso 20** — `migrations/001_create_courses.sql`: tabla `courses` (domain-entities.md: `course_id`, `name`, `description`, `category`, `curriculum` como `text[]` o `jsonb`, `price`, `duration_weeks`, `embedding vector(1536)`), extensión `pgvector` (`CREATE EXTENSION IF NOT EXISTS vector`), índice HNSW sobre `embedding`, índices B-tree sobre `price`/`duration_weeks` (PATTERN-07/08).
- [x] **Paso 21** — Script Python de carga (`scripts/seed_catalog.py` + `scripts/catalog_seed_data.json`, 10 programas reales de DMC referenciados en requirements.md §8.3): seed data manual de cursos + generación de embeddings vía `AzureOpenAIEmbeddingService` al momento de la carga (Sección 1 de business-logic-model.md).

### Documentation Generation
- [x] **Paso 22** — `services/agent-service/README.md`: cómo correr localmente, variables de entorno, cómo ejecutar tests y el seed del catálogo.

### Deployment Artifacts Generation
- [x] **Paso 23** — Terraform (`infra/agent-service/*.tf`, workspace root — no anidado en `services/`): recursos de `infrastructure-design.md` (Container App con min_replicas=1, Postgres Flexible Server B1ms + firewall rule restringido a la IP del Container Apps Environment, Azure OpenAI + deployment de embeddings, Key Vault, Log Analytics 90 días, role assignments least-privilege) en el resource group único `rg-dmc-agent-service`. Nota: el proyecto/agente de Azure AI Foundry no tiene soporte maduro en el provider `azurerm` — documentado como paso manual/`azd` pendiente, ver comentario en `main.tf`.
- [x] **Paso 24** — `Dockerfile` para `agent-service` (imagen base con tag fijado `python:3.11.10-slim-bookworm`, sin `latest` — SECURITY-10).

---

## Nota sobre alcance de PBT/Security en Code Generation
Este plan cubre PBT-02 a PBT-10 (Pasos 5-8, 18) y aplica SECURITY-05/06/10/11(pendiente)/15 según lo definido en NFR Requirements/Design. El hallazgo SECURITY-11 (rate limiting) permanece sin resolver en este incremento — no se genera código de rate limiting (riesgo aceptado, ver nfr-requirements.md).
