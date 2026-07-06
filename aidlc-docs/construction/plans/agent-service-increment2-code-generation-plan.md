# Code Generation Plan — agent-service (Azure) — Incremento 2 + apps/chat

**Fecha**: 2026-07-06
**Workspace root**: `/Users/sebastianchavarry/Documents/ask-dmc`
**Código de aplicación (backend)**: `services/agent-service/` (brownfield — modificar en el lugar, no duplicar)
**Código de aplicación (frontend)**: `apps/chat/` (brownfield — modificar en el lugar)
**Documentación de este stage**: `aidlc-docs/construction/agent-service/code/` y `aidlc-docs/construction/apps-chat/code/`

Este plan es la única fuente de verdad para la generación de código de este incremento. Sigue el orden de dependencia decidido en Workflow Planning: **agent-service primero, apps/chat después** (el frontend consume el contrato del backend).

## Contexto y trazabilidad
- **Unidades**: `agent-service` (incremento 2) + `apps/chat` (formalizada como unidad, ex "frontend-widget")
- **Traza**: Business Rules BR-16 a BR-21, domain entities `Lead`/`ConversationSession`/`PaymentOrder`, componentes lógicos de `nfr-design/logical-components.md` (secciones Incremento 2)
- **Dependencias**: reutiliza `RecommendationOrchestrator`, `CourseRepository`, `EmbeddingService`, `RetryPolicy`, `ConnectionPool` de incremento 1 sin modificarlos
- **Interfaces nuevas**: `WS /ws/chat` (reemplaza `/ws/recommendation`), `HTTP POST /webhooks/mercadopago`
- **Entidades de BD nuevas**: `leads`, `conversation_sessions` (mismo Postgres de incremento 1)

---

## Pasos — Backend (`services/agent-service/`)

### Business Logic Generation
- [x] **Paso 1** — Dominio nuevo (`src/domain/models.py`, extendido): `Lead`, `LeadScore` (enum hot/warm/cold), `ConversationSession`, `PaymentOrder`, `PaymentStatus` (enum pending/approved/rejected) — dataclasses sin dependencias de infraestructura. Traza: domain-entities.md Incremento 2.
- [x] **Paso 2** — `src/domain/lead_scoring.py` (nuevo): función pura `score_lead(...)` implementando BR-17 (hot/warm/cold, dato completo obligatorio para hot).
- [x] **Paso 3** — `src/domain/pending_tool_calls.py` (nuevo): `PendingToolCallRegistry` — diccionario `{call_id: asyncio.Future}` con registro/resolución/cancelación (PATTERN-15).

### Business Logic Unit Testing
- [x] **Paso 4** — `tests/unit/test_lead_scoring.py`: tests de propiedad (Hypothesis) para BR-17 — determinismo (P9), invariante hot⟹datos completos (P10).
- [x] **Paso 5** — `tests/unit/test_pending_tool_calls.py`: registro/resolución/cancelación del `PendingToolCallRegistry`.
- [ ] **Paso 6** — Documentar `aidlc-docs/construction/agent-service/code/business-logic-summary-increment2.md`.

### API Layer Generation
- [x] **Paso 7** — `src/api/schemas.py` (extendido): `UserMessageIn`, `ProfileDataSubmittedIn`, `ProfileDataRequestedOut`, `PaymentLinkCreatedOut`, `SessionCreatedOut` (business-logic-model.md Sección 9), + schema del payload de webhook de Mercado Pago.
- [x] **Paso 8** — `src/adapters/mercadopago_client.py` (nuevo): `MercadoPagoPaymentClient` — `create_preference(amount, description, client_details, external_reference)` (API de Preferencias) y `get_payment(payment_id) -> PaymentDetails` (`GET /v1/payments/{id}`), envuelto en `RetryPolicy` (PATTERN-14). `external_reference`/`PaymentDetails` agregados durante generación (no estaban en el plan original) para poder correlacionar el webhook con el `Lead` — ver nota al final de este documento.
- [x] **Paso 9** — `src/adapters/mercadopago_signature.py` (nuevo): `SignatureVerifier` — valida `x-signature`/`x-request-id` (HMAC) contra el secreto (PATTERN-17).
- [x] **Paso 10** — `src/adapters/chat_agent_client.py` (nuevo, junto a `foundry_agent_client.py` sin modificarlo): `ChatAgentClient` — construye el `Agent` con **3 tools** (`collect_profile_data`, `get_course_recommendations`, `create_payment_link`) + system prompt de asesor de ventas (BR-16), expone `create_session`/`get_session` (PATTERN-20) y un método de streaming que traduce eventos a `TextDelta`/`ProfileDataRequested`/`PaymentLinkCreated`/`RecommendationsReady`. El tool `get_course_recommendations` (no estaba en el plan original) se agregó durante generación — ver nota al final de este documento.
- [x] **Paso 11** — `src/api/chat_websocket_handler.py` (nuevo): `ChatWebSocketHandler` para `/ws/chat` — recibe `user_message`, gestiona el receptor concurrente de `profile_data_submitted` (resuelve `PendingToolCallRegistry`), emite `recommendation_delta`/`profile_data_requested`/`payment_link_created`/`recommendation_done`/`session_created`.
- [x] **Paso 12** — `src/api/webhook_handler.py` (nuevo): lógica de `POST /webhooks/mercadopago` — verifica firma (Paso 9), idempotencia (PATTERN-16), re-consulta `GET /v1/payments/{id}` (Paso 8), correlaciona por `external_reference` (=`service_session_id`), actualiza `Lead` vía `LeadRepository` (Paso 18).
- [x] **Paso 13** — `main.py` (modificado): reemplaza `@app.websocket("/ws/recommendation")` por `@app.websocket("/ws/chat")`, agrega `@app.post("/webhooks/mercadopago")`, wiring de los nuevos adaptadores/secrets. `src/api/websocket_handler.py` (incremento 1) se deja intacto como referencia histórica, ya no enrutado desde `main.py` — análogo a `services/api/` tras DIV-10.

### API Layer Unit Testing
- [x] **Paso 14** — `tests/unit/test_mercadopago_signature.py`: verificación de firma válida/inválida/manipulada.
- [x] **Paso 15** — `tests/integration/test_chat_websocket_flow.py`: flujo de chat libre con tool-call simulado (`FakeChatAgentClient`, usando el `PendingToolCallRegistry` real) — `profile_data_requested` → `profile_data_submitted` → continúa; evento `payment_link_created`; sesión nueva vs. retomada.
- [x] **Paso 16** — `tests/integration/test_webhook_flow.py`: webhook válido confirma pago; firma inválida rechazada (401); webhook repetido idempotente (no reprocesa); evento no-`payment` ignorado.
- [ ] **Paso 17** — Documentar `aidlc-docs/construction/agent-service/code/api-layer-summary-increment2.md`.

### Repository Layer Generation
- [x] **Paso 18** — `src/ports/lead_repository.py` (nuevo, `Protocol`) + `src/adapters/postgres_lead_repository.py` (nuevo): persistencia de `Lead`/`ConversationSession` en Postgres, queries parametrizadas (SECURITY-05). Campo `mercadopago_payment_id` agregado a `Lead` durante generación (trazabilidad del pago confirmado).
- [x] **Paso 19** — `src/adapters/keyvault_secrets.py`: sin cambios de código — es un adapter genérico (`get_secret(name)`) ya reutilizable; los 2 secrets nuevos se resuelven vía `config.py` en local dev (mismo patrón que incremento 1, que tampoco invoca Key Vault en runtime local).
- [x] **Paso 20** — `src/config.py` (extendido): `mercadopago_access_token`, `mercadopago_webhook_secret`, `mercadopago_base_url` (default sandbox `https://api.mercadopago.com`).

### Repository Layer Unit Testing
- [x] **Paso 21** — `tests/unit/test_postgres_lead_repository.py`: contra Postgres de test real (mismo patrón que `test_postgres_repository.py` de incremento 1, skip si `TEST_DATABASE_URL` no está configurada). Skipeado en esta sesión (sin Postgres real levantado) — pendiente de verificación real en Build and Test.
- [x] **Paso 22** — Documentado `aidlc-docs/construction/agent-service/code/repository-layer-summary-increment2.md`.

### Database Migration Scripts
- [x] **Paso 23** — `migrations/002_create_leads_and_sessions.sql`: tablas `leads` y `conversation_sessions` (domain-entities.md Incremento 2).

### Scripts de verificación manual (patrón ya establecido en incremento 1)
- [x] **Paso 24** — `scripts/manual_chat_check.py` (nuevo): cliente WS real contra `/ws/chat` ejercitando chat libre + tool-calling, análogo a `manual_ws_check.py`.
- [x] **Paso 25** — `scripts/simulate_mercadopago_webhook.py` (nuevo): firma y envía un payload realista contra `localhost:8000/webhooks/mercadopago` (decisión de NFR Requirements — sin exposición pública real en este incremento).

### Documentation Generation
- [x] **Paso 26** — `services/agent-service/README.md` (actualizado): incremento 2, nuevas variables de entorno, migración 002, cómo correr los scripts de verificación manual. `.env.example` también actualizado.

### Deployment Artifacts Generation
- [x] **Paso 27** — `pyproject.toml` (modificado): agregado `httpx` (ya estaba disponible transitivamente, ahora es dependencia directa).
- [x] **Paso 28** — `infra/agent-service/{variables.tf,main.tf}` (modificado, workspace root): 2 variables sensibles + 2 `azurerm_key_vault_secret` en el Key Vault ya existente + `secret{}`/`env{secret_name=...}` en el Container App ya existente — sin nuevos recursos de cómputo/red. **No se corrió `terraform plan`/`apply`** (instrucción explícita del usuario: el objetivo de esta sesión es probar la integración local, no desplegar) — sigue sin aplicarse, mismo estado que incremento 1.

---

## Pasos — Frontend (`apps/chat/`)

### Frontend Components Generation
- [x] **Paso 29** — `types/chat.ts` (reescrito): `ChatPhase` (`streaming`/`awaitingProfileData`/`done`), `ToolCallInfo`, `BotMsg` extendido (`recommendations`, `toolCalls`, `profileRequest`), `ProfileData`/`ProfileDataPrefill`, `CourseRecommendation` (reemplaza `Source`).
- [x] **Paso 30** — `lib/ChatService.ts` (interfaz rediseñada) + `lib/WsChatService.ts` (nuevo): `ChatEvent` unión discriminada (`delta`/`profileDataRequested`/`recommendationsReady`/`paymentLinkCreated`/`turnDone`/`sessionCreated`), `events: Stream` + `sendMessage`/`submitProfileData` como efectos sobre un WebSocket persistente (`Stream.asyncPush`, gate de apertura del socket antes de aceptar envíos). Persiste `service_session_id` en `localStorage` internamente al recibir `session_created`.
- [x] **Paso 31** — `lib/runtime.ts` (modificado): usa `WsChatServiceLive` en vez de `HttpChatService`.
- [x] **Paso 32** — `hooks/useChat.ts` (reescrito): un solo listener del stream persistente por el ciclo de vida del componente (no uno por mensaje); despacha por `_tag` a los helpers puros; dispara `sendMessage`/`submitProfileData`.
- [x] **Paso 33** — `components/ProfileDataWidget.tsx` (nuevo): formulario inline (presupuesto, duración, background, stack) con prefill, `data-testid` por campo y por el botón de submit.
- [x] **Paso 34** — `components/CourseRecommendationCard.tsx` (nuevo, reemplaza `SourceChips`): lista de tarjetas de curso recomendado (nombre + % de match), deduplicada por `courseId`.
- [x] **Paso 35** — `components/BotMessage.tsx` (modificado): renderiza `ProfileDataWidget` cuando `msg.profileRequest` está presente, `CourseRecommendationCard` para `msg.recommendations`, reutiliza `ToolCallBlock` (ya existente, antes con datos falsos de `search_brochures`) ahora con datos reales de `create_payment_link`. `components/MessageList.tsx`/`ChatApp.tsx` actualizados para pasar `onSubmitProfileData`.

### Frontend Components Unit Testing
- [x] **Paso 36** — `lib/ChatService.test.ts` (reescrito, contrato nuevo) + `lib/WsChatService.test.ts` (nuevo, reemplaza `HttpChatService.test.ts`): traducción del protocolo de wire (`toChatEvent`, exportado para test directo) para los 6 tipos de evento + tipos desconocidos → `null`; gate de apertura del socket antes de enviar (con `FakeWebSocket` + `vi.waitFor`, dado que `environment: 'node'` en vitest no tiene `WebSocket` global).
- [x] **Paso 37** — `hooks/useChat.test.ts` (reescrito): los 7 helpers puros nuevos (`applyDelta`, `applyRecommendations`, `applyProfileRequest`/`clearProfileRequest`, `applyPaymentLink`, `markTurnDone`).
- [x] **Paso 38** — Documentado `aidlc-docs/construction/apps-chat/code/frontend-components-summary.md`.

### Limpieza de código muerto (brownfield)
- [x] **Paso 39** — Eliminados `lib/HttpChatService.ts`, `lib/HttpChatService.test.ts`, `app/api/ask/route.ts`, `components/SourceChips.tsx` (ya no aplican — protocolo HTTP reemplazado por WS directo, RF-I01). Verificado: `npx tsc --noEmit` limpio, `npx vitest run` 19/19 verdes, `npx next build` exitoso.

## Gap de diseño adicional encontrado durante la generación del frontend

El chat libre no tenía ninguna señal explícita de "el agente terminó de responder a este mensaje" (a diferencia de incremento 1, donde `recommendation_done`/`no_recommendation` cerraban el turno). Se agregó al backend (retroactivo a Paso 11/13) el evento `turn_done` (`TurnDoneOut`, `src/api/schemas.py` y `chat_websocket_handler.py`), emitido tras cada `agent_client.stream(...)` — sin esto, el frontend no tendría forma confiable de re-habilitar el input. Tests de integración del backend actualizados y verificados en verde.

---

## Nota sobre alcance
- Sin cambios a `RecommendationOrchestrator`, `CourseRepository`, `EmbeddingService`, `FoundryPersistentAgentClient` (incremento 1) — se reutilizan tal cual.
- Sin exposición pública del webhook (Paso 25 lo prueba contra `localhost`, no contra Mercado Pago real) — consistente con NFR Requirements.
- Sin páginas de checkout propias (Mercado Pago Checkout Pro no las requiere).
- Sin Backoffice Portal (fuera de alcance, RF-I18).

## Nota sobre gaps de diseño encontrados durante Code Generation

Durante la generación se detectaron 2 huecos reales en el Functional Design aprobado, corregidos en el código (no solo documentados) y anotados aquí para trazabilidad:

1. **Tool faltante para recomendación**: Functional Design (business-logic-model.md Incremento 2) solo especificaba 2 tools (`collect_profile_data`, `create_payment_link`), pero el agente no tiene acceso directo a Postgres — sin una tercera tool, nunca podría invocar `RecommendationOrchestrator` para realmente recomendar cursos. Se agregó `get_course_recommendations` (Paso 10), reutilizando `RecommendationOrchestrator`/`CourseRepository`/`EmbeddingService` de incremento 1 sin modificarlos. Cuando no hay match exacto, la tool retorna texto para que el agente ofrezca conversacionalmente el rango ampliado (Clarification 4 = A) — si el usuario acepta, el agente vuelve a invocar la misma tool con `accept_relaxed_filters=true`, evitando necesitar una pausa tipo widget para este caso.
2. **Correlación webhook↔lead**: el webhook de Mercado Pago entrega un `payment_id`, no el `preference_id` que ya teníamos — sin un campo de correlación, no había forma de saber a qué `Lead` pertenece un pago confirmado. Se agregó `external_reference` (seteado al `service_session_id` de la conversación al crear la preferencia) y `PaymentDetails.external_reference` (retornado por `get_payment`), usado por el webhook handler para encontrar el `Lead` correcto. Limitación conocida, documentada en el código: si el usuario pide pagar antes de que `session_created` se haya emitido alguna vez, `external_reference` queda `None` y el webhook no puede auto-correlacionar — aceptable para el alcance de esta demo.
