# Repository/Adapter Layer — Code Generation Summary (agent-service, Incremento 1)

## Generado

- `src/adapters/connection_pool.py` — `ConnectionPool` (asyncpg, PATTERN-09), `min_size=1`/`max_size=10`, TLS forzado (`ssl="require"`).
- `src/adapters/postgres_course_repository.py` — `PostgresCourseRepository`: filtro+ranking en una sola query parametrizada (`price <= $2`, `duration_weeks <= $3`, `ORDER BY embedding <=> $1`, `LIMIT $4` — `NULL` en cualquiera de los tres deshabilita esa restricción, usado para BR-11). Nunca concatena SQL (SECURITY-05).
- `src/adapters/azure_openai_embedding.py` — `AzureOpenAIEmbeddingService` (`text-embedding-3-small`, Managed Identity vía `DefaultAzureCredential` + `get_bearer_token_provider`), envuelto en `RetryPolicy`; lanza `EmbeddingServiceUnavailableError` tras agotar reintentos.
- `src/adapters/foundry_agent_client.py` — `FoundryPersistentAgentClient` (Microsoft Agent Framework Python SDK: `agent_framework.foundry.FoundryChatClient` + `agent_framework.Agent` — **corregido en Build and Test**, ver nota abajo). El agente se crea una vez (cacheado en la instancia) y se invoca con `agent.run(prompt, stream=True)`, que es una llamada **síncrona** que retorna un `ResponseStream` directamente (no se espera antes del `async for`). El `RetryPolicy` envuelve solo la obtención del primer update del stream (donde de verdad ocurre la llamada de red), no el streaming ya iniciado (según NFR Design). Lanza `AgentUnavailableError`.
- `src/adapters/keyvault_secrets.py` — `KeyVaultSecretsProvider` (PATTERN-11).
- `src/adapters/retry_policy.py` — `RetryPolicy` genérico (PATTERN-01): 3 intentos, backoff exponencial + jitter.

## Tests generados

- `tests/unit/test_retry_policy.py` — éxito tras N fallos dentro del límite, excepción tras agotar intentos.
- `tests/conftest.py` — fixture `connection_pool` contra `TEST_DATABASE_URL`; marker `requires_postgres` que **skippea** los tests si no hay Postgres+pgvector real disponible (documentado en README, no oculto).
- `tests/unit/test_postgres_repository.py` — **P6** (oracle: ranking real de pgvector vs. similitud coseno de referencia en NumPy, sobre datos generados con Hypothesis) y re-verificación de **P1/P2** contra la base de datos real (no solo el fake en memoria).

## Nota importante sobre el SDK de Agent Framework/Foundry — corrección real (Build and Test, 2026-07-05)
Los imports originales de este archivo (`agent_framework.azure.AzureAIAgentsProvider` + `azure.ai.agents.aio.AgentsClient`) se basaron en un ADR/spec doc de `microsoft/agent-framework` (vía Context7) que **no corresponde a la superficie realmente publicada** del paquete `agent-framework-foundry` — verificado en esta sesión contra PyPI: ese paquete depende de `azure-ai-projects`, no de `azure-ai-agents`, y el módulo `agent_framework.azure` no existe en el paquete instalado. Corregido a `agent_framework.foundry.FoundryChatClient` + `agent_framework.Agent`, verificado con `uv sync` real (resolución de dependencias exitosa) y ejecución de la suite completa (22 tests, incluyendo los que requieren Postgres real) sin fallos tras el cambio. También se corrigió `pyproject.toml`: la dependencia `agent-framework` (que resuelve a `agent-framework-core[all]`, arrastrando integraciones no usadas como Redis/Copilot Studio/AG-UI con conflictos de versión reales) se reemplazó por `agent-framework-foundry` directamente — dependencias mínimas y consistentes.

## Cobertura de seguridad en esta capa
SECURITY-01 (TLS forzado en `ConnectionPool`), SECURITY-05 (queries parametrizadas), SECURITY-06 (Managed Identity, least-privilege delegado a Infrastructure Design), SECURITY-10 (dependencias con versión fijada en `pyproject.toml`, sin `latest`).
