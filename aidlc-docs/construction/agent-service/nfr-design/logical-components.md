# Logical Components — agent-service (Azure) — Incremento 1

**Fecha**: 2026-07-05

Componentes lógicos (tecnología-agnósticos en su rol, con la implementación Azure ya decidida entre paréntesis) que materializan los patrones de `nfr-design-patterns.md` sobre el algoritmo de `business-logic-model.md`.

---

## `WebSocketConnectionHandler`
Acepta y mantiene la conexión WS por visitante (FastAPI WebSocket route en Container Apps). Responsable de: parsear `recommendation_request`/`relax_filters_response`, invocar al `RecommendationOrchestrator`, y transmitir `recommendation_delta`/`recommendation_done`/`relax_filters_offer`/`no_exact_match_showing_all` de vuelta. Mantiene el estado `awaiting_relax_confirmation` en memoria local (PATTERN-05) con su timeout asociado (PATTERN-02).

## `RecommendationOrchestrator`
Componente de dominio puro (sin dependencias de infraestructura directas — recibe `ports` inyectados) que implementa el algoritmo completo de `business-logic-model.md` Sección 2: valida el request (BR-09), aplica filtro duro, decide la rama de relajación (BR-03/BR-11), construye el `ProfileQuery`, y arma el `RecommendationCandidate[]` final. Es el componente principal de cobertura Hypothesis (PBT-01 a PBT-10, propiedades P1-P8 de business-logic-model.md §6).

## `CourseRepository` (puerto) / `PostgresCourseRepository` (adaptador)
Encapsula el acceso a `courses` en Postgres: filtro duro (`price`/`duration_weeks`, PATTERN-08) y ranking pgvector (PATTERN-06/07). Usa el `ConnectionPool` (PATTERN-09). Es el único componente con SQL directo — parametrizado siempre (SECURITY-05).

## `ConnectionPool`
Pool de conexiones a Azure Database for PostgreSQL (`asyncpg`), inicializado una vez al arrancar el contenedor (PATTERN-09). Autenticación vía Managed Identity/Azure AD si disponible, o secret de Key Vault (PATTERN-10/11).

## `EmbeddingService` (puerto) / `AzureOpenAIEmbeddingService` (adaptador)
Genera el embedding de `ProfileQuery.query_text` (paso 5) llamando a Azure OpenAI `text-embedding-3-small`. Envuelto por el `RetryPolicy` (PATTERN-01). Mismo componente/modelo se reutiliza para generar los embeddings del catálogo en el proceso de carga offline (Sección 1 de business-logic-model.md).

## `RecommendationAgentClient` (puerto) / `FoundryPersistentAgentClient` (adaptador)
Invoca al Persistent Agent de Azure AI Foundry (`gpt-5.4-nano`) vía Microsoft Agent Framework SDK (`agent.run(..., stream=True)`, paso 8), pasando `candidates` + `profile_text` + flag de rama (exacta/ampliada/catálogo completo). Traduce cada `AgentRunResponseUpdate.text` a un evento `recommendation_delta` hacia el `WebSocketConnectionHandler`. Envuelto por el `RetryPolicy` (PATTERN-01) — el retry aplica a la invocación inicial, no a mitad de un stream ya iniciado (un stream interrumpido a medias se trata como `agent_unavailable`, no se reintenta parcialmente).

## `RetryPolicy`
Componente transversal (decorator/wrapper) que implementa PATTERN-01 (3 intentos, backoff exponencial + jitter) — usado por `EmbeddingService` y `RecommendationAgentClient`.

## `StructuredLogger`
Logging JSON con request/connection ID, timestamp, level — sin PII (SECURITY-03). Usado por todos los componentes anteriores. Envía a Azure Monitor/Log Analytics.

## `SecretsProvider`
Resuelve credenciales (connection string de Postgres si no hay Azure AD auth disponible, cualquier clave de API) desde Container Apps secrets respaldados por Key Vault (PATTERN-11) — nunca desde variables de entorno en texto plano ni hardcodeadas.

---

## Diagrama de dependencias

```
WebSocketConnectionHandler
        │
        ▼
RecommendationOrchestrator ──► CourseRepository ──► ConnectionPool ──► (Postgres + pgvector)
        │                              │
        │                              └──► SecretsProvider (credenciales)
        │
        ├──► EmbeddingService ──► RetryPolicy ──► (Azure OpenAI text-embedding-3-small)
        │
        └──► RecommendationAgentClient ──► RetryPolicy ──► (Foundry Persistent Agent, gpt-5.4-nano)

Todos los componentes ──► StructuredLogger ──► (Azure Monitor / Log Analytics)
```

## Nota de testabilidad
`RecommendationOrchestrator` no depende directamente de `asyncpg`, del SDK de Azure OpenAI ni del SDK de Agent Framework — recibe `CourseRepository`, `EmbeddingService` y `RecommendationAgentClient` como puertos (Protocol/interfaces), permitiendo que los tests de Hypothesis (PBT-01 a PBT-10) ejerciten el algoritmo completo con fakes en memoria, sin levantar Postgres ni llamar a Azure OpenAI real — mismo patrón de puertos/adaptadores ya usado en `unit-1: ingestion-pipeline`.

---

# Incremento 2 — Componentes nuevos

**Fecha**: 2026-07-06

## `ChatWebSocketHandler` (reemplaza/extiende `WebSocketConnectionHandler`)
Acepta la conexión en `/ws/chat` (renombrado). Además de los mensajes de incremento 1, parsea `user_message` y `profile_data_submitted`, y despacha al `ChatOrchestrator`. Mantiene la tarea concurrente de recepción (PATTERN-15) que resuelve los `Future`s del `PendingToolCallRegistry`.

## `ChatOrchestrator`
Envuelve al `Agent` de Microsoft Agent Framework (system prompt de asesor de ventas + los 2 tools). Traduce `Content` del stream (`text`, `function_call`, `function_result`) a los eventos WS correspondientes (`recommendation_delta`, `profile_data_requested`, `payment_link_created`). Reutiliza `RecommendationOrchestrator` (incremento 1) como lógica interna cuando el flujo de recomendación estructurada aplica.

## `PendingToolCallRegistry`
Diccionario en memoria `{call_id: asyncio.Future}` (PATTERN-15), anclado al ciclo de vida de la conexión WS — sin estado distribuido, mismo principio que PATTERN-05.

## `CollectProfileDataTool`
Implementación del tool `collect_profile_data` (business-logic-model.md Sección 8.1): envía `profile_data_requested`, registra el `Future` en `PendingToolCallRegistry`, hace `await`, retorna el resultado al `Agent`.

## `CreatePaymentLinkTool` / `MercadoPagoPaymentClient` (puerto/adaptador)
El tool invoca al `MercadoPagoPaymentClient` (API de Preferencias, PATTERN-14 retry) y retorna `init_point`/`sandbox_init_point` como resultado.

## `WebhookHandler`
Ruta HTTP `POST /webhooks/mercadopago` (no WS). Verifica firma (PATTERN-17), aplica idempotencia (PATTERN-16), re-consulta `GET /v1/payments/{id}` (PATTERN-18), y delega en `LeadRepository` la actualización del estado de pago.

## `LeadRepository` (puerto) / `PostgresLeadRepository` (adaptador)
Persiste `Lead` y `ConversationSession` en las nuevas tablas Postgres (mismo motor que `CourseRepository`, nueva migración). Calcula/almacena `LeadScore` (BR-17).

## `ConversationSessionStore`
Envuelve `Agent.create_session()`/`Agent.get_session(service_session_id)` (PATTERN-20) — resuelve la sesión a usar en cada conexión nueva, según si el cliente envía un `service_session_id` previo (retomar) o no (crear).

## `SignatureVerifier`
Verifica HMAC (`x-signature`/`x-request-id`) contra el secreto de Key Vault (PATTERN-17) — componente puro, sin dependencias de infraestructura directas más allá de recibir el secreto ya resuelto por `SecretsProvider`.

---

## Diagrama de dependencias — Incremento 2

```
ChatWebSocketHandler ──► ChatOrchestrator ──► Agent (Microsoft Agent Framework)
        │                       │                    │
        │                       │                    ├──► CollectProfileDataTool ──► PendingToolCallRegistry
        │                       │                    └──► CreatePaymentLinkTool ──► MercadoPagoPaymentClient ──► RetryPolicy
        │                       │
        │                       └──► RecommendationOrchestrator (incremento 1, reutilizado)
        │
        └──► ConversationSessionStore ──► Agent.create_session/get_session (Foundry Memory)

WebhookHandler ──► SignatureVerifier ──► SecretsProvider (secreto Key Vault)
        │
        ├──► MercadoPagoPaymentClient (GET /v1/payments/{id}, PATTERN-18)
        └──► LeadRepository ──► ConnectionPool ──► (Postgres, mismas tablas que CourseRepository)

Todos los componentes ──► StructuredLogger (sin PII, SECURITY-03 reforzado)
```
